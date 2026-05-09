"""
tasks/appointment_tasks.py
Celery tasks for appointment reminders, follow-up alerts, and queue management.
"""

import structlog
from celery import shared_task
from django.utils import timezone

logger = structlog.get_logger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
    name="tasks.send_appointment_reminder",
)
def send_appointment_reminder(self, appointment_id: str, hours_before: int):
    """
    Send appointment reminder SMS/WhatsApp/email.
    Triggered automatically when appointment is booked.
    """
    from apps.appointments.models import Appointment, AppointmentStatus
    from apps.notifications.services import NotificationService

    try:
        appointment = Appointment.objects.select_related(
            "patient", "doctor", "clinic", "clinic__settings"
        ).get(id=appointment_id)

        # Skip if cancelled or already sent
        if appointment.status in [AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED]:
            return {"skipped": True, "reason": f"Appointment is {appointment.status}"}

        if hours_before == 24 and appointment.reminder_24h_sent:
            return {"skipped": True, "reason": "24h reminder already sent"}
        if hours_before == 2 and appointment.reminder_2h_sent:
            return {"skipped": True, "reason": "2h reminder already sent"}

        service = NotificationService(appointment.clinic)
        context = {
            "patient_name": appointment.patient.full_name,
            "doctor_name": f"Dr. {appointment.doctor.full_name}",
            "clinic_name": appointment.clinic.name,
            "appointment_date": appointment.appointment_date.strftime("%d %B %Y"),
            "appointment_time": appointment.appointment_time.strftime("%I:%M %p"),
            "token_number": appointment.token_number,
            "hours_before": hours_before,
        }

        # Send based on clinic settings
        results = service.send_appointment_reminder(appointment, context, hours_before)

        # Mark as sent
        if hours_before == 24:
            Appointment.objects.filter(id=appointment_id).update(reminder_24h_sent=True)
        elif hours_before == 2:
            Appointment.objects.filter(id=appointment_id).update(reminder_2h_sent=True)

        logger.info(
            "reminder_sent",
            appointment_id=appointment_id,
            hours_before=hours_before,
            results=results,
        )
        return {"success": True, "results": results}

    except Appointment.DoesNotExist:
        logger.warning("appointment_not_found", appointment_id=appointment_id)
        return {"error": "Appointment not found"}
    except Exception as exc:
        logger.error("reminder_task_failed", appointment_id=appointment_id, error=str(exc))
        raise self.retry(exc=exc)


@shared_task(name="tasks.send_follow_up_alerts")
def send_follow_up_alerts():
    """
    Periodic task (daily) — finds prescriptions with upcoming follow-up dates
    and sends reminders to patients.
    """
    from apps.prescriptions.models import Prescription
    from apps.notifications.services import NotificationService
    from datetime import date, timedelta

    tomorrow = date.today() + timedelta(days=1)

    prescriptions = Prescription.objects.filter(
        next_visit_date=tomorrow,
        deleted_at__isnull=True,
    ).select_related("patient", "doctor", "clinic")

    sent_count = 0
    for rx in prescriptions:
        try:
            service = NotificationService(rx.clinic)
            context = {
                "patient_name": rx.patient.full_name,
                "doctor_name": f"Dr. {rx.doctor.full_name}",
                "clinic_name": rx.clinic.name,
                "follow_up_date": tomorrow.strftime("%d %B %Y"),
            }
            service.send_follow_up_reminder(rx.patient, context)
            sent_count += 1
        except Exception as e:
            logger.error("follow_up_alert_failed", prescription_id=str(rx.id), error=str(e))

    logger.info("follow_up_alerts_sent", count=sent_count, date=str(tomorrow))
    return {"sent": sent_count}


@shared_task(name="tasks.check_subscription_expiry")
def check_subscription_expiry():
    """
    Periodic task — checks for expiring/expired subscriptions and
    sends alerts to clinic admins.
    """
    from apps.clinics.models import Clinic, ClinicStatus
    from apps.notifications.services import NotificationService
    from datetime import date, timedelta

    today = date.today()
    expiring_soon = today + timedelta(days=7)

    # Clinics expiring in 7 days
    expiring_clinics = Clinic.objects.filter(
        subscription_end__lte=expiring_soon,
        subscription_end__gte=today,
        status=ClinicStatus.ACTIVE,
        deleted_at__isnull=True,
    )

    for clinic in expiring_clinics:
        days_left = (clinic.subscription_end - today).days
        # Email clinic admin
        admin_profile = clinic.user_profiles.filter(role="clinic_admin", is_active=True).first()
        if admin_profile:
            NotificationService(clinic).send_subscription_expiry_warning(
                admin_profile.user, days_left
            )

    # Mark expired clinics
    expired = Clinic.objects.filter(
        subscription_end__lt=today,
        status=ClinicStatus.ACTIVE,
        deleted_at__isnull=True,
    )
    count = expired.update(status=ClinicStatus.EXPIRED)
    if count:
        logger.info("clinics_marked_expired", count=count)

    return {"expiring_soon": expiring_clinics.count(), "expired": count}


@shared_task(name="tasks.cleanup_old_sessions")
def cleanup_old_sessions():
    """Weekly cleanup of inactive login sessions older than 30 days."""
    from apps.accounts.models import LoginSession
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(days=30)
    deleted, _ = LoginSession.objects.filter(
        is_active=False, logged_out_at__lt=cutoff
    ).delete()
    logger.info("old_sessions_cleaned", deleted=deleted)
    return {"deleted": deleted}


@shared_task(name="tasks.compute_queue_wait_times")
def compute_queue_wait_times():
    """
    Every 5 minutes — recalculates average wait times for active queues
    and broadcasts updates via WebSocket.
    """
    from apps.appointments.models import Appointment, AppointmentQueue, AppointmentStatus
    from utils.websocket_utils import broadcast_queue_update
    from datetime import date

    today = date.today()
    active_queues = AppointmentQueue.objects.filter(
        queue_date=today, is_accepting=True, deleted_at__isnull=True
    ).select_related("clinic", "doctor")

    for queue in active_queues:
        # Compute average consultation time from completed appointments today
        completed = Appointment.objects.filter(
            clinic=queue.clinic,
            doctor=queue.doctor,
            appointment_date=today,
            status=AppointmentStatus.COMPLETED,
            consultation_started_at__isnull=False,
            consultation_ended_at__isnull=False,
        )

        if completed.exists():
            total_minutes = sum(
                (a.consultation_ended_at - a.consultation_started_at).total_seconds() / 60
                for a in completed
            )
            avg = int(total_minutes / completed.count())
            queue.average_wait_minutes = max(avg, 5)  # Minimum 5 minutes
            queue.save(update_fields=["average_wait_minutes"])

        broadcast_queue_update(str(queue.clinic_id), str(queue.doctor_id), str(today))
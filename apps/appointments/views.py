"""
apps/appointments/views.py
Appointment management with booking, scheduling, queue management,
and real-time WebSocket notifications.
"""

import structlog
from datetime import date, datetime, timedelta
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.appointments.models import (
    Appointment, AppointmentQueue, AppointmentStatus, DoctorSchedule, DoctorLeave
)
from apps.appointments.serializers import (
    AppointmentListSerializer,
    AppointmentDetailSerializer,
    AppointmentCreateSerializer,
    AppointmentRescheduleSerializer,
    AppointmentQueueSerializer,
    DoctorScheduleSerializer,
    AvailableSlotsSerializer,
)
from apps.appointments.filters import AppointmentFilter
from utils.mixins import TenantMixin, AuditMixin
from utils.permissions import IsClinicMember, IsReceptionistOrAbove
from utils.websocket_utils import broadcast_queue_update

logger = structlog.get_logger(__name__)


class AppointmentViewSet(TenantMixin, AuditMixin, ModelViewSet):
    """
    Full appointment lifecycle management with queue support.
    """

    queryset = Appointment.objects.select_related(
        "patient", "doctor", "clinic", "booked_by", "rescheduled_from"
    )
    permission_classes = [IsAuthenticated, IsClinicMember, IsReceptionistOrAbove]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    filterset_class = AppointmentFilter
    search_fields = ["patient__first_name", "patient__last_name", "patient__phone"]
    ordering_fields = ["appointment_date", "appointment_time", "token_number", "created_at"]
    ordering = ["appointment_date", "appointment_time"]

    def get_serializer_class(self):
        if self.action == "list":
            return AppointmentListSerializer
        if self.action == "create":
            return AppointmentCreateSerializer
        return AppointmentDetailSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        clinic = self.get_clinic_or_404()
        appointment_date = serializer.validated_data["appointment_date"]
        doctor = serializer.validated_data["doctor"]

        # Assign token number for the day
        existing_count = Appointment.objects.filter(
            clinic=clinic,
            doctor=doctor,
            appointment_date=appointment_date,
            status__in=[
                AppointmentStatus.SCHEDULED,
                AppointmentStatus.CONFIRMED,
                AppointmentStatus.CHECKED_IN,
            ],
        ).count()
        token = existing_count + 1

        appointment = serializer.save(
            clinic=clinic,
            booked_by=self.request.user,
            token_number=token,
            queue_position=token,
        )

        # Update queue
        self._update_queue(clinic, doctor, appointment_date)

        # Schedule reminder tasks
        from tasks.appointment_tasks import send_appointment_reminder
        send_appointment_reminder.apply_async(
            args=[str(appointment.id), 24],
            eta=datetime.combine(appointment_date, appointment.appointment_time) - timedelta(hours=24),
        )

        # Notify WebSocket clients
        broadcast_queue_update(str(clinic.id), str(doctor.id), str(appointment_date))
        logger.info("appointment_booked", appointment_id=str(appointment.id))

    @action(detail=True, methods=["post"], url_path="reschedule")
    @transaction.atomic
    def reschedule(self, request, pk=None):
        """POST /api/v1/appointments/{id}/reschedule/"""
        appointment = self.get_object()

        if appointment.status in [AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED]:
            return Response(
                {"error": f"Cannot reschedule a {appointment.status} appointment."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AppointmentRescheduleSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Create new appointment
        new_appointment = Appointment.objects.create(
            clinic=appointment.clinic,
            patient=appointment.patient,
            doctor=serializer.validated_data.get("doctor", appointment.doctor),
            appointment_date=serializer.validated_data["new_date"],
            appointment_time=serializer.validated_data["new_time"],
            appointment_type=appointment.appointment_type,
            chief_complaint=appointment.chief_complaint,
            booked_by=request.user,
            rescheduled_from=appointment,
        )

        # Mark original as rescheduled
        appointment.status = AppointmentStatus.RESCHEDULED
        appointment.save(update_fields=["status"])

        return Response(
            AppointmentDetailSerializer(new_appointment).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        """POST /api/v1/appointments/{id}/cancel/"""
        appointment = self.get_object()

        if appointment.status in [AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED]:
            return Response(
                {"error": f"Cannot cancel a {appointment.status} appointment."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reason = request.data.get("reason", "")
        appointment.cancel(cancelled_by=request.user, reason=reason)

        # Notify via WebSocket
        broadcast_queue_update(
            str(request.clinic.id),
            str(appointment.doctor_id),
            str(appointment.appointment_date),
        )

        return Response({"message": "Appointment cancelled.", "status": appointment.status})

    @action(detail=True, methods=["post"], url_path="check-in")
    def check_in(self, request, pk=None):
        """POST /api/v1/appointments/{id}/check-in/"""
        appointment = self.get_object()
        appointment.check_in()
        broadcast_queue_update(
            str(request.clinic.id), str(appointment.doctor_id), str(appointment.appointment_date)
        )
        return Response({"message": "Patient checked in.", "checked_in_at": appointment.checked_in_at})

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        """POST /api/v1/appointments/{id}/complete/"""
        appointment = self.get_object()
        appointment.complete()
        broadcast_queue_update(
            str(request.clinic.id), str(appointment.doctor_id), str(appointment.appointment_date)
        )
        return Response({"message": "Consultation completed.", "duration_minutes": appointment.actual_duration_minutes})

    @action(detail=False, methods=["get"], url_path="queue")
    def queue(self, request):
        """
        GET /api/v1/appointments/queue/
        Today's appointment queue (cached 30 seconds for real-time feel).
        Optional: ?doctor_id=<uuid>
        """
        today = date.today()
        doctor_id = request.query_params.get("doctor_id")
        cache_key = f"queue:{request.clinic_id}:{doctor_id or 'all'}:{today}"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        qs = Appointment.objects.filter(
            clinic=request.clinic,
            appointment_date=today,
            status__in=[
                AppointmentStatus.SCHEDULED,
                AppointmentStatus.CONFIRMED,
                AppointmentStatus.CHECKED_IN,
                AppointmentStatus.IN_PROGRESS,
            ],
        ).select_related("patient", "doctor").order_by("token_number")

        if doctor_id:
            qs = qs.filter(doctor_id=doctor_id)

        data = {
            "date": str(today),
            "total": qs.count(),
            "waiting": qs.filter(status__in=[AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED, AppointmentStatus.CHECKED_IN]).count(),
            "in_progress": qs.filter(status=AppointmentStatus.IN_PROGRESS).count(),
            "queue": AppointmentListSerializer(qs, many=True).data,
        }
        cache.set(cache_key, data, timeout=30)  # 30 seconds only
        return Response(data)

    @action(detail=False, methods=["post"], url_path="queue/next")
    def next_patient(self, request):
        """POST /api/v1/appointments/queue/next/ — Call next patient."""
        from utils.permissions import IsDoctorOrAbove
        doctor_id = request.data.get("doctor_id", str(request.user.id))
        today = date.today()

        next_apt = Appointment.objects.filter(
            clinic=request.clinic,
            doctor_id=doctor_id,
            appointment_date=today,
            status=AppointmentStatus.CHECKED_IN,
        ).order_by("token_number").first()

        if not next_apt:
            return Response({"message": "No more patients in queue."})

        next_apt.start_consultation()
        broadcast_queue_update(str(request.clinic.id), doctor_id, str(today))
        return Response(AppointmentDetailSerializer(next_apt).data)

    @action(detail=False, methods=["get"], url_path="slots")
    def available_slots(self, request):
        """
        GET /api/v1/appointments/slots/?doctor_id=<uuid>&date=2025-01-01
        Returns available booking slots.
        """
        doctor_id = request.query_params.get("doctor_id")
        slot_date_str = request.query_params.get("date")

        if not doctor_id or not slot_date_str:
            return Response(
                {"error": "doctor_id and date are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            slot_date = date.fromisoformat(slot_date_str)
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=400)

        # Get doctor schedule for this weekday
        schedules = DoctorSchedule.objects.filter(
            clinic=request.clinic,
            doctor_id=doctor_id,
            day_of_week=slot_date.weekday(),
            is_active=True,
        )

        # Check for leaves
        on_leave = DoctorLeave.objects.filter(
            clinic=request.clinic,
            doctor_id=doctor_id,
            leave_date=slot_date,
        ).exists()

        if on_leave or not schedules.exists():
            return Response({"slots": [], "message": "Doctor not available on this date."})

        # Get booked appointments
        booked_times = set(
            Appointment.objects.filter(
                clinic=request.clinic,
                doctor_id=doctor_id,
                appointment_date=slot_date,
                status__in=[
                    AppointmentStatus.SCHEDULED,
                    AppointmentStatus.CONFIRMED,
                    AppointmentStatus.CHECKED_IN,
                ],
            ).values_list("appointment_time", flat=True)
        )

        # Generate available slots
        all_slots = []
        for schedule in schedules:
            current = datetime.combine(slot_date, schedule.start_time)
            end = datetime.combine(slot_date, schedule.end_time)
            while current < end:
                slot_time = current.time()
                all_slots.append({
                    "time": slot_time.strftime("%H:%M"),
                    "available": slot_time not in booked_times,
                    "booked": slot_time in booked_times,
                })
                current += timedelta(minutes=schedule.slot_duration_minutes)

        return Response({"date": str(slot_date), "doctor_id": doctor_id, "slots": all_slots})

    def _update_queue(self, clinic, doctor, appointment_date):
        """Update the queue count after a new booking."""
        queue, _ = AppointmentQueue.objects.get_or_create(
            clinic=clinic, doctor=doctor, queue_date=appointment_date
        )
        queue.total_tokens = Appointment.objects.filter(
            clinic=clinic, doctor=doctor, appointment_date=appointment_date
        ).count()
        queue.save(update_fields=["total_tokens"])
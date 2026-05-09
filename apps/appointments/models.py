"""
apps/appointments/models.py
Appointment scheduling, queue management, and doctor slot management.
"""

from django.db import models
from django.utils import timezone

from apps.core.models import TenantModel, UUIDModel, TimeStampedModel


class AppointmentStatus(models.TextChoices):
    SCHEDULED = "scheduled", "Scheduled"
    CONFIRMED = "confirmed", "Confirmed"
    CHECKED_IN = "checked_in", "Checked In"
    IN_PROGRESS = "in_progress", "In Progress"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"
    NO_SHOW = "no_show", "No Show"
    RESCHEDULED = "rescheduled", "Rescheduled"


class AppointmentType(models.TextChoices):
    NEW_PATIENT = "new", "New Patient"
    FOLLOW_UP = "followup", "Follow-Up"
    EMERGENCY = "emergency", "Emergency"
    TELECONSULT = "teleconsult", "Tele-Consultation"


class DoctorSchedule(TenantModel):
    """
    Weekly recurring schedule for a doctor at a clinic.
    Slots are generated from this schedule.
    """

    doctor = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="schedules"
    )
    day_of_week = models.IntegerField(
        choices=[(i, d) for i, d in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])]
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_duration_minutes = models.PositiveIntegerField(default=30)
    max_patients_per_slot = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "doctor_schedules"
        unique_together = [("clinic", "doctor", "day_of_week", "start_time")]
        indexes = [
            models.Index(fields=["clinic", "doctor", "day_of_week"]),
        ]


class DoctorLeave(TenantModel):
    """Block out dates for a doctor (vacation, holiday, etc.)."""

    doctor = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="leaves"
    )
    leave_date = models.DateField(db_index=True)
    leave_type = models.CharField(
        max_length=20,
        choices=[("full", "Full Day"), ("morning", "Morning"), ("evening", "Evening"), ("emergency", "Emergency")],
        default="full",
    )
    reason = models.CharField(max_length=300, blank=True)

    class Meta:
        db_table = "doctor_leaves"
        unique_together = [("clinic", "doctor", "leave_date")]


class Appointment(TenantModel):
    """
    Core appointment entity with full lifecycle tracking.
    """

    # Participants
    patient = models.ForeignKey(
        "patients.Patient", on_delete=models.CASCADE, related_name="appointments"
    )
    doctor = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="appointments"
    )

    # Scheduling
    appointment_date = models.DateField(db_index=True)
    appointment_time = models.TimeField()
    end_time = models.TimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(default=30)
    appointment_type = models.CharField(
        max_length=20, choices=AppointmentType.choices, default=AppointmentType.FOLLOW_UP
    )

    # Queue
    token_number = models.PositiveIntegerField(null=True, blank=True)
    queue_position = models.PositiveIntegerField(null=True, blank=True)

    # Status
    status = models.CharField(
        max_length=20, choices=AppointmentStatus.choices, default=AppointmentStatus.SCHEDULED
    )

    # Clinical
    chief_complaint = models.TextField(blank=True)
    notes = models.TextField(blank=True)  # Doctor notes post-visit

    # Tracking
    booked_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="booked_appointments"
    )
    checked_in_at = models.DateTimeField(null=True, blank=True)
    consultation_started_at = models.DateTimeField(null=True, blank=True)
    consultation_ended_at = models.DateTimeField(null=True, blank=True)

    # Cancellation
    cancelled_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    cancellation_reason = models.CharField(max_length=300, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    # Rescheduled from
    rescheduled_from = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="rescheduled_to"
    )

    # Reminders sent
    reminder_24h_sent = models.BooleanField(default=False)
    reminder_2h_sent = models.BooleanField(default=False)

    class Meta:
        db_table = "appointments"
        indexes = [
            models.Index(fields=["clinic", "appointment_date"]),
            models.Index(fields=["clinic", "doctor", "appointment_date"]),
            models.Index(fields=["clinic", "patient"]),
            models.Index(fields=["clinic", "status"]),
            models.Index(fields=["clinic", "appointment_date", "status"]),
        ]

    def __str__(self):
        return f"APT-{self.id} | {self.patient} → Dr.{self.doctor.last_name} | {self.appointment_date}"

    def cancel(self, cancelled_by, reason=""):
        self.status = AppointmentStatus.CANCELLED
        self.cancelled_by = cancelled_by
        self.cancellation_reason = reason
        self.cancelled_at = timezone.now()
        self.save(update_fields=["status", "cancelled_by", "cancellation_reason", "cancelled_at"])

    def check_in(self):
        self.status = AppointmentStatus.CHECKED_IN
        self.checked_in_at = timezone.now()
        self.save(update_fields=["status", "checked_in_at"])

    def start_consultation(self):
        self.status = AppointmentStatus.IN_PROGRESS
        self.consultation_started_at = timezone.now()
        self.save(update_fields=["status", "consultation_started_at"])

    def complete(self):
        self.status = AppointmentStatus.COMPLETED
        self.consultation_ended_at = timezone.now()
        self.save(update_fields=["status", "consultation_ended_at"])

    @property
    def actual_duration_minutes(self):
        if self.consultation_started_at and self.consultation_ended_at:
            delta = self.consultation_ended_at - self.consultation_started_at
            return int(delta.total_seconds() / 60)
        return None


class AppointmentQueue(TenantModel):
    """
    Daily queue state for a doctor.
    Tracks current position, wait time estimates.
    """

    doctor = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="queues"
    )
    queue_date = models.DateField(db_index=True)
    current_token = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)
    average_wait_minutes = models.PositiveIntegerField(default=30)
    is_accepting = models.BooleanField(default=True)
    queue_started_at = models.DateTimeField(null=True, blank=True)
    queue_paused_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "appointment_queues"
        unique_together = [("clinic", "doctor", "queue_date")]
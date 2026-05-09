"""
apps/activity_logs/models.py
Immutable audit log for every significant action in the system.
"""

from django.db import models
from apps.core.models import UUIDModel


class ActivityAction(models.TextChoices):
    # Auth
    LOGIN = "login", "Login"
    LOGOUT = "logout", "Logout"
    LOGIN_FAILED = "login_failed", "Login Failed"
    PASSWORD_CHANGED = "password_changed", "Password Changed"
    PASSWORD_RESET = "password_reset", "Password Reset"
    # CRUD
    CREATE = "create", "Create"
    READ = "read", "Read"
    UPDATE = "update", "Update"
    DELETE = "delete", "Delete"
    RESTORE = "restore", "Restore"
    # Appointments
    APPOINTMENT_BOOKED = "appointment_booked", "Appointment Booked"
    APPOINTMENT_CANCELLED = "appointment_cancelled", "Appointment Cancelled"
    APPOINTMENT_RESCHEDULED = "appointment_rescheduled", "Appointment Rescheduled"
    APPOINTMENT_COMPLETED = "appointment_completed", "Appointment Completed"
    # Billing
    INVOICE_CREATED = "invoice_created", "Invoice Created"
    PAYMENT_RECORDED = "payment_recorded", "Payment Recorded"
    # Prescription
    PRESCRIPTION_CREATED = "prescription_created", "Prescription Created"
    PRESCRIPTION_UPDATED = "prescription_updated", "Prescription Updated"
    PRESCRIPTION_PDF = "prescription_pdf", "Prescription PDF Downloaded"
    # Staff
    STAFF_ADDED = "staff_added", "Staff Added"
    STAFF_ROLE_CHANGED = "staff_role_changed", "Staff Role Changed"
    STAFF_DEACTIVATED = "staff_deactivated", "Staff Deactivated"
    # Export
    DATA_EXPORTED = "data_exported", "Data Exported"


class ActivityLog(UUIDModel):
    """
    Immutable audit log record.
    NEVER UPDATE or DELETE records in this table.
    No SoftDelete — this is permanent audit history.
    """

    # Who
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="activity_logs",
        db_index=True,
    )
    user_email = models.EmailField(blank=True)  # Snapshot in case user is deleted
    user_role = models.CharField(max_length=20, blank=True)

    # Where (tenant)
    clinic = models.ForeignKey(
        "clinics.Clinic",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
        db_index=True,
    )
    clinic_name = models.CharField(max_length=200, blank=True)  # Snapshot

    # What
    action = models.CharField(max_length=50, choices=ActivityAction.choices, db_index=True)
    resource_type = models.CharField(max_length=50, db_index=True)  # "Patient", "Appointment"
    resource_id = models.CharField(max_length=100, blank=True, db_index=True)
    resource_repr = models.CharField(max_length=300, blank=True)  # Human-readable

    # Detail
    description = models.TextField(blank=True)
    changes = models.JSONField(null=True, blank=True)  # {"field": {"old": X, "new": Y}}
    metadata = models.JSONField(default=dict)  # Extra context

    # Request context
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    request_path = models.CharField(max_length=500, blank=True)
    request_method = models.CharField(max_length=10, blank=True)

    # Timing
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "activity_logs"
        indexes = [
            models.Index(fields=["clinic", "timestamp"]),
            models.Index(fields=["user", "timestamp"]),
            models.Index(fields=["action", "timestamp"]),
            models.Index(fields=["resource_type", "resource_id"]),
            models.Index(fields=["clinic", "action", "timestamp"]),
        ]
        ordering = ["-timestamp"]

    def __str__(self):
        return f"[{self.timestamp}] {self.user_email} — {self.action} {self.resource_type}"

    # Make this model completely immutable
    def save(self, *args, **kwargs):
        # Allow insert only; block updates
        if not self._state.adding:
            raise ValueError(
                "ActivityLog records are immutable and cannot be modified."
            )

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("ActivityLog records cannot be deleted.")
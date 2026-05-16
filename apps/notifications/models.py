from django.db import models
from apps.core.models import TenantModel, UUIDModel, TimeStampedModel

class NotificationType(models.TextChoices):
    SMS = "sms", "SMS"
    EMAIL = "email", "Email"
    WHATSAPP = "whatsapp", "WhatsApp"
    PUSH = "push", "Push Notification"

class NotificationTemplate(TenantModel):
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=10, choices=NotificationType.choices)
    subject = models.CharField(max_length=200, blank=True) # For emails
    body = models.TextField() # Template with placeholders like {{patient_name}}
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "notification_templates"
        unique_together = [("clinic", "name", "type")]

class Notification(TenantModel):
    """User-specific notifications (In-app alerts)."""
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    link = models.CharField(max_length=500, blank=True) # Frontend URL to navigate to

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]

class NotificationLog(TenantModel):
    """Log of all sent SMS/Email/WhatsApp messages."""
    recipient_name = models.CharField(max_length=200)
    recipient_contact = models.CharField(max_length=100) # Email or Phone
    type = models.CharField(max_length=10, choices=NotificationType.choices)
    template = models.ForeignKey(NotificationTemplate, on_delete=models.SET_NULL, null=True)
    subject = models.CharField(max_length=200, blank=True)
    body = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=[("pending", "Pending"), ("sent", "Sent"), ("failed", "Failed")],
        default="pending"
    )
    error_message = models.TextField(blank=True)
    external_id = models.CharField(max_length=255, blank=True) # Twilio/SendGrid ID

    class Meta:
        db_table = "notification_logs"

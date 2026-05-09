"""
apps/clinics/models.py
Clinic entity — the top-level tenant in the system.
"""

from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel, SoftDeleteModel


class SubscriptionPlan(models.TextChoices):
    TRIAL = "trial", "Trial"
    STARTER = "starter", "Starter (3 Doctors)"
    PROFESSIONAL = "professional", "Professional (10 Doctors)"
    ENTERPRISE = "enterprise", "Enterprise (Unlimited)"


class ClinicStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    TRIAL = "trial", "Trial"
    EXPIRED = "expired", "Expired"


class Clinic(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """
    Root tenant entity. All data in the system is scoped to a Clinic.
    """

    # Identity
    name = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(max_length=100, unique=True)
    logo = models.ImageField(upload_to="clinics/logos/", null=True, blank=True)
    tagline = models.CharField(max_length=300, blank=True)

    # Contact
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    website = models.URLField(blank=True)

    # Address
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, db_index=True)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100, default="India")
    pincode = models.CharField(max_length=20)

    # Settings
    timezone = models.CharField(max_length=50, default="Asia/Kolkata")
    currency = models.CharField(max_length=3, default="INR")
    language = models.CharField(max_length=10, default="en")

    # Business hours stored as JSON
    # Format: {"monday": {"open": "09:00", "close": "18:00", "is_closed": false}, ...}
    business_hours = models.JSONField(default=dict)

    # Subscription
    subscription_plan = models.CharField(
        max_length=20, choices=SubscriptionPlan.choices, default=SubscriptionPlan.TRIAL
    )
    subscription_start = models.DateField(null=True, blank=True)
    subscription_end = models.DateField(null=True, blank=True)
    max_doctors = models.PositiveIntegerField(default=1)
    max_patients = models.PositiveIntegerField(default=500)

    # Status
    status = models.CharField(max_length=20, choices=ClinicStatus.choices, default=ClinicStatus.TRIAL)

    # Registration
    registration_number = models.CharField(max_length=100, blank=True)
    gstin = models.CharField(max_length=15, blank=True)  # GST number for India

    # Owner
    owner = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="owned_clinics",
        null=True,
    )

    class Meta:
        db_table = "clinics"
        verbose_name = "Clinic"
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["status"]),
            models.Index(fields=["city"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.city})"

    @property
    def is_subscription_active(self):
        from django.utils import timezone
        if self.subscription_end is None:
            return self.status == ClinicStatus.ACTIVE
        return timezone.now().date() <= self.subscription_end


class ClinicSettings(UUIDModel, TimeStampedModel):
    """Per-clinic configurable settings."""

    clinic = models.OneToOneField(Clinic, on_delete=models.CASCADE, related_name="settings")

    # Appointment settings
    appointment_duration_minutes = models.PositiveIntegerField(default=30)
    advance_booking_days = models.PositiveIntegerField(default=30)
    allow_walk_ins = models.BooleanField(default=True)
    queue_enabled = models.BooleanField(default=True)
    auto_confirm_appointments = models.BooleanField(default=False)

    # Notification settings
    sms_enabled = models.BooleanField(default=False)
    whatsapp_enabled = models.BooleanField(default=False)
    email_enabled = models.BooleanField(default=True)
    reminder_hours_before = models.JSONField(default=list)  # [24, 2]

    # Branding
    primary_color = models.CharField(max_length=7, default="#2D6A4F")  # HEX
    invoice_prefix = models.CharField(max_length=10, default="INV")
    prescription_header = models.TextField(blank=True)
    prescription_footer = models.TextField(blank=True)

    # SMS/WhatsApp credentials (per clinic)
    twilio_sid = models.CharField(max_length=100, blank=True)
    twilio_token = models.CharField(max_length=100, blank=True)
    whatsapp_api_key = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = "clinic_settings"
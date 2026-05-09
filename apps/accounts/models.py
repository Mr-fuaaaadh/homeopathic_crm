"""
apps/accounts/models.py
Custom User model with Role-Based Access Control and multi-clinic support.
"""

import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel, UUIDModel


class UserRole(models.TextChoices):
    SUPER_ADMIN = "super_admin", "Super Admin"
    CLINIC_ADMIN = "clinic_admin", "Clinic Admin"
    DOCTOR = "doctor", "Doctor"
    RECEPTIONIST = "receptionist", "Receptionist"
    PATIENT = "patient", "Patient"


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", UserRole.SUPER_ADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(email, password, **extra_fields)


class User(UUIDModel, AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    """
    Central User entity.
    A single user can be linked to multiple clinics via UserClinicProfile.
    The `role` here is their global/default role; per-clinic role is in UserClinicProfile.
    """

    email = models.EmailField(unique=True, db_index=True)
    phone = models.CharField(max_length=20, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.RECEPTIONIST)

    # Profile
    avatar = models.ImageField(upload_to="avatars/%Y/%m/", null=True, blank=True)
    designation = models.CharField(max_length=100, blank=True)  # "Dr.", "Mr.", etc.
    qualification = models.CharField(max_length=200, blank=True)
    specialization = models.CharField(max_length=200, blank=True)  # For doctors
    registration_number = models.CharField(max_length=100, blank=True)  # Medical reg

    # Status
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)
    is_phone_verified = models.BooleanField(default=False)

    # Tracking
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    last_login_at = models.DateTimeField(null=True, blank=True)
    login_count = models.PositiveIntegerField(default=0)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    class Meta:
        db_table = "users"
        verbose_name = "User"
        verbose_name_plural = "Users"
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["role"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.full_name} <{self.email}> [{self.role}]"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_clinic_role(self, clinic_id):
        """Return the user's role within a specific clinic."""
        profile = self.clinic_profiles.filter(clinic_id=clinic_id, is_active=True).first()
        return profile.role if profile else None

    def has_clinic_access(self, clinic_id):
        """Check if user has access to a specific clinic."""
        if self.role == UserRole.SUPER_ADMIN:
            return True
        return self.clinic_profiles.filter(
            clinic_id=clinic_id, is_active=True
        ).exists()

    def record_login(self, ip_address=None):
        self.last_login_at = timezone.now()
        self.last_login_ip = ip_address
        self.login_count += 1
        self.save(update_fields=["last_login_at", "last_login_ip", "login_count"])


class UserClinicProfile(UUIDModel, TimeStampedModel):
    """
    Many-to-many through table: a user can belong to multiple clinics
    with different roles in each.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="clinic_profiles")
    clinic = models.ForeignKey("clinics.Clinic", on_delete=models.CASCADE, related_name="user_profiles")
    role = models.CharField(max_length=20, choices=UserRole.choices)
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    invited_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        db_table = "user_clinic_profiles"
        unique_together = [("user", "clinic")]
        indexes = [
            models.Index(fields=["clinic", "role"]),
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self):
        return f"{self.user.email} @ {self.clinic.name} [{self.role}]"


class PasswordResetToken(UUIDModel, TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reset_tokens")
    token = models.CharField(max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        db_table = "password_reset_tokens"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at


class LoginSession(UUIDModel, TimeStampedModel):
    """Tracks active JWT sessions for audit and forced logout."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")
    clinic = models.ForeignKey(
        "clinics.Clinic", null=True, blank=True, on_delete=models.SET_NULL
    )
    jti = models.CharField(max_length=255, unique=True, db_index=True)  # JWT ID
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    logged_out_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "login_sessions"
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["jti"]),
        ]
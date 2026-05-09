"""
apps/patients/models.py
Patient management with medical history, visit timeline, and file attachments.
All records are scoped to clinic_id via TenantModel.
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

from apps.core.models import TenantModel, UUIDModel, TimeStampedModel


class BloodGroup(models.TextChoices):
    A_POS = "A+", "A+"
    A_NEG = "A-", "A-"
    B_POS = "B+", "B+"
    B_NEG = "B-", "B-"
    AB_POS = "AB+", "AB+"
    AB_NEG = "AB-", "AB-"
    O_POS = "O+", "O+"
    O_NEG = "O-", "O-"
    UNKNOWN = "unknown", "Unknown"


class Gender(models.TextChoices):
    MALE = "male", "Male"
    FEMALE = "female", "Female"
    OTHER = "other", "Other"
    PREFER_NOT = "prefer_not_to_say", "Prefer not to say"


class Patient(TenantModel):
    """
    Core patient entity. Strict clinic_id isolation via TenantModel.
    patient_id is a human-readable sequential ID per clinic (e.g. P-0001).
    """

    # Human-readable ID (auto-generated per clinic)
    patient_code = models.CharField(max_length=20, blank=True, db_index=True)

    # Demographics
    first_name = models.CharField(max_length=100, db_index=True)
    last_name = models.CharField(max_length=100, db_index=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, choices=Gender.choices)
    blood_group = models.CharField(max_length=10, choices=BloodGroup.choices, default=BloodGroup.UNKNOWN)

    # Contact
    phone = models.CharField(max_length=20, db_index=True)
    alternate_phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True, db_index=True)
    whatsapp_number = models.CharField(max_length=20, blank=True)

    # Address
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=20, blank=True)

    # Medical basics
    occupation = models.CharField(max_length=100, blank=True)
    marital_status = models.CharField(
        max_length=20,
        choices=[("single", "Single"), ("married", "Married"), ("divorced", "Divorced"), ("widowed", "Widowed")],
        blank=True,
    )
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)

    # Homeopathy-specific
    constitution = models.CharField(max_length=200, blank=True)  # e.g. Psoric/Sycotic/Syphilitic
    miasm = models.CharField(max_length=200, blank=True)
    thermal = models.CharField(max_length=50, blank=True)  # Hot/Cold/Chilly
    diathesis = models.CharField(max_length=200, blank=True)

    # Registration
    registered_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="+"
    )
    primary_doctor = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="primary_patients",
    )
    source = models.CharField(
        max_length=50,
        choices=[("walk_in", "Walk-in"), ("referral", "Referral"), ("online", "Online"), ("other", "Other")],
        default="walk_in",
    )
    referral_by = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)

    # Consent
    consent_given = models.BooleanField(default=False)
    consent_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "patients"
        indexes = [
            models.Index(fields=["clinic", "phone"]),
            models.Index(fields=["clinic", "email"]),
            models.Index(fields=["clinic", "first_name", "last_name"]),
            models.Index(fields=["clinic", "patient_code"]),
            models.Index(fields=["primary_doctor"]),
        ]
        unique_together = [("clinic", "patient_code")]

    def __str__(self):
        return f"{self.patient_code} — {self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def age(self):
        if self.date_of_birth:
            from django.utils import timezone
            today = timezone.now().date()
            dob = self.date_of_birth
            return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        return None

    def save(self, *args, **kwargs):
        if not self.patient_code:
            self.patient_code = self._generate_patient_code()
        super().save(*args, **kwargs)

    def _generate_patient_code(self):
        last = (
            Patient.all_objects.filter(clinic=self.clinic)
            .order_by("-created_at")
            .values_list("patient_code", flat=True)
            .first()
        )
        if last:
            try:
                num = int(last.split("-")[1]) + 1
            except (IndexError, ValueError):
                num = 1
        else:
            num = 1
        return f"P-{num:05d}"


class MedicalHistory(TenantModel):
    """
    Structured medical history entry for a patient.
    Each entry is a specific complaint/condition record.
    """

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="medical_history")

    # Complaint
    chief_complaint = models.TextField()
    history_of_present_illness = models.TextField(blank=True)
    onset = models.CharField(max_length=200, blank=True)  # "3 months ago", "sudden"
    duration = models.CharField(max_length=100, blank=True)
    modalities = models.TextField(blank=True)  # Better/Worse factors

    # Past history
    past_medical_history = models.TextField(blank=True)
    past_surgical_history = models.TextField(blank=True)
    family_history = models.TextField(blank=True)
    personal_history = models.TextField(blank=True)  # Diet, habits, sleep
    drug_history = models.TextField(blank=True)  # Previous medications

    # Allergies
    allergies = models.JSONField(default=list)  # [{"substance": "Penicillin", "reaction": "Rash"}]

    # Systemic review
    systemic_review = models.JSONField(default=dict)

    # Homeopathic generals
    appetite = models.CharField(max_length=200, blank=True)
    thirst = models.CharField(max_length=200, blank=True)
    sleep_pattern = models.TextField(blank=True)
    dreams = models.TextField(blank=True)
    perspiration = models.TextField(blank=True)
    stool_urine = models.TextField(blank=True)
    menstrual_history = models.TextField(blank=True)  # For female patients

    # Mind/Mental generals
    mental_generals = models.TextField(blank=True)
    emotional_state = models.TextField(blank=True)

    # Physical examination
    physical_examination = models.TextField(blank=True)
    vitals = models.JSONField(default=dict)  # BP, pulse, temp, weight, height

    # Recorded by
    recorded_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        db_table = "medical_histories"
        indexes = [
            models.Index(fields=["clinic", "patient"]),
        ]


class PatientAttachment(TenantModel):
    """Files uploaded for a patient (reports, scans, old prescriptions)."""

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="patients/attachments/%Y/%m/")
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=100)  # MIME type
    file_size = models.PositiveIntegerField()  # bytes
    description = models.CharField(max_length=300, blank=True)
    category = models.CharField(
        max_length=50,
        choices=[
            ("report", "Lab Report"),
            ("scan", "Scan/X-Ray"),
            ("prescription", "Old Prescription"),
            ("identity", "ID Document"),
            ("other", "Other"),
        ],
        default="other",
    )
    uploaded_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        db_table = "patient_attachments"
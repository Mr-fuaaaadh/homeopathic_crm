"""
apps/prescriptions/models.py
Homeopathic prescription system with remedy repertorisation, case notes, and PDF support.
"""

from django.db import models
from apps.core.models import TenantModel


class PotencyScale(models.TextChoices):
    X = "X", "X (Decimal)"
    C = "C", "C (Centesimal)"
    M = "M", "M (Milliesimal)"
    LM = "LM", "LM/Q (Fifty Millesimal)"
    CM = "CM", "CM"


class Prescription(TenantModel):
    """
    A consultation visit generates one Prescription.
    Contains case analysis, selected remedy, and follow-up plan.
    """

    # Links
    appointment = models.OneToOneField(
        "appointments.Appointment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prescription",
    )
    patient = models.ForeignKey(
        "patients.Patient", on_delete=models.CASCADE, related_name="prescriptions"
    )
    doctor = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="prescriptions"
    )

    # Visit details
    visit_date = models.DateField(db_index=True)
    visit_number = models.PositiveIntegerField(default=1)  # Sequential per patient

    # Case Analysis
    chief_complaint = models.TextField()
    history_of_present_illness = models.TextField(blank=True)
    generals = models.TextField(blank=True)  # Generals from intake
    particulars = models.TextField(blank=True)
    mentals = models.TextField(blank=True)
    physical_generals = models.TextField(blank=True)
    modalities = models.TextField(blank=True)
    miasmatic_analysis = models.TextField(blank=True)

    # Totality / Repertorisation
    totality_of_symptoms = models.TextField(blank=True)
    repertorisation_notes = models.TextField(blank=True)
    rubrics = models.JSONField(default=list)  # [{rubric: "...", grade: 3, source: "Kent"}]

    # Examination findings
    examination_findings = models.TextField(blank=True)
    vitals = models.JSONField(default=dict)  # BP, weight, etc.

    # Diagnosis
    provisional_diagnosis = models.CharField(max_length=300, blank=True)
    differential_diagnosis = models.TextField(blank=True)

    # Follow-up
    next_visit_date = models.DateField(null=True, blank=True)
    follow_up_instructions = models.TextField(blank=True)
    dietary_advice = models.TextField(blank=True)
    lifestyle_advice = models.TextField(blank=True)

    # Doctor's case notes (internal)
    internal_notes = models.TextField(blank=True)

    class Meta:
        db_table = "prescriptions"
        indexes = [
            models.Index(fields=["clinic", "patient"]),
            models.Index(fields=["clinic", "doctor", "visit_date"]),
            models.Index(fields=["clinic", "visit_date"]),
        ]

    def __str__(self):
        return f"Rx-{self.id} | {self.patient} | {self.visit_date}"


class Remedy(TenantModel):
    """
    Master remedy list. Shared (clinic=None) for global remedies,
    or clinic-scoped for custom additions.
    """

    clinic = models.ForeignKey(
        "clinics.Clinic",
        on_delete=models.CASCADE,
        null=True,
        blank=True,  # null = global remedy
        related_name="custom_remedies",
    )
    name = models.CharField(max_length=200, db_index=True)
    abbreviation = models.CharField(max_length=20, blank=True, db_index=True)
    full_name = models.CharField(max_length=300, blank=True)
    source = models.CharField(max_length=100, blank=True)  # Plant, mineral, animal
    kingdom = models.CharField(
        max_length=20,
        choices=[("plant", "Plant"), ("mineral", "Mineral"), ("animal", "Animal"), ("nosode", "Nosode"), ("other", "Other")],
        blank=True,
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "remedies"
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["abbreviation"]),
        ]

    def __str__(self):
        return f"{self.abbreviation or self.name}"


class PrescriptionRemedy(UUIDModel := __import__('apps.core.models', fromlist=['UUIDModel']).UUIDModel, TimeStampedModel := __import__('apps.core.models', fromlist=['TimeStampedModel']).TimeStampedModel):
    """
    A specific remedy line in a prescription.
    Supports multiple remedies (intercurrent, concomitant, etc.).
    """

    prescription = models.ForeignKey(
        Prescription, on_delete=models.CASCADE, related_name="remedies"
    )
    remedy = models.ForeignKey(
        Remedy, on_delete=models.PROTECT, related_name="prescription_uses"
    )

    # Potency
    potency = models.CharField(max_length=20)  # "30", "200", "1M", "10M"
    potency_scale = models.CharField(
        max_length=5, choices=PotencyScale.choices, default=PotencyScale.C
    )

    # Dosage
    dose = models.CharField(max_length=100)  # "4 pills", "10 drops"
    frequency = models.CharField(max_length=100)  # "Once daily", "TDS", "SOS"
    duration = models.CharField(max_length=100)  # "7 days", "2 weeks"
    route = models.CharField(
        max_length=20,
        choices=[("oral", "Oral"), ("sublingual", "Sublingual"), ("olfaction", "Olfaction")],
        default="sublingual",
    )

    # Type of remedy in this prescription
    remedy_type = models.CharField(
        max_length=30,
        choices=[
            ("constitutional", "Constitutional"),
            ("acute", "Acute"),
            ("intercurrent", "Intercurrent"),
            ("organ_remedy", "Organ Remedy"),
            ("drainage", "Drainage"),
            ("nosode", "Nosode"),
            ("other", "Other"),
        ],
        default="constitutional",
    )

    instructions = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "prescription_remedies"
        ordering = ["sort_order"]
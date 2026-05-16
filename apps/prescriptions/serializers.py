from rest_framework import serializers
from apps.prescriptions.models import Prescription, PrescriptionRemedy, Remedy

class RemedySerializer(serializers.ModelSerializer):
    class Meta:
        model = Remedy
        fields = "__all__"

class PrescriptionRemedySerializer(serializers.ModelSerializer):
    remedy_name = serializers.ReadOnlyField(source="remedy.name")
    
    class Meta:
        model = PrescriptionRemedy
        fields = [
            "id", "prescription", "remedy", "remedy_name", "potency",
            "form", "dosage", "frequency", "duration", "instruction"
        ]
        read_only_fields = ["id", "prescription"]

class PrescriptionListSerializer(serializers.ModelSerializer):
    patient_name = serializers.ReadOnlyField(source="patient.full_name")
    doctor_name = serializers.ReadOnlyField(source="doctor.full_name")
    
    class Meta:
        model = Prescription
        fields = [
            "id", "patient", "patient_name", "doctor", "doctor_name",
            "visit_date", "visit_number", "chief_complaint", "status", "created_at"
        ]

class PrescriptionDetailSerializer(serializers.ModelSerializer):
    patient_name = serializers.ReadOnlyField(source="patient.full_name")
    doctor_name = serializers.ReadOnlyField(source="doctor.full_name")
    remedies = PrescriptionRemedySerializer(many=True, read_only=True)
    
    class Meta:
        model = Prescription
        fields = "__all__"

class PrescriptionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prescription
        exclude = ["clinic", "doctor", "visit_number"]

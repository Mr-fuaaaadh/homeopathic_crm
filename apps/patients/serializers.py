from rest_framework import serializers
from apps.patients.models import Patient, MedicalHistory, PatientAttachment

class PatientListSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    
    class Meta:
        model = Patient
        fields = [
            "id", "patient_code", "first_name", "last_name", "full_name",
            "gender", "date_of_birth", "phone", "email", "created_at"
        ]

class PatientAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientAttachment
        fields = "__all__"

class MedicalHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalHistory
        fields = "__all__"

class PatientDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    medical_history = MedicalHistorySerializer(many=True, read_only=True)
    attachments = PatientAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = Patient
        fields = "__all__"

class PatientCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        exclude = ["clinic", "registered_by", "patient_code"]

    def create(self, validated_data):
        return Patient.objects.create(**validated_data)

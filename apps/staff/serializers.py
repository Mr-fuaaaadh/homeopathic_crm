from rest_framework import serializers
from apps.accounts.models import User, UserClinicProfile, UserRole

class StaffProfileSerializer(serializers.ModelSerializer):
    email = serializers.ReadOnlyField(source="user.email")
    first_name = serializers.ReadOnlyField(source="user.first_name")
    last_name = serializers.ReadOnlyField(source="user.last_name")
    full_name = serializers.ReadOnlyField(source="user.full_name")

    class Meta:
        model = UserClinicProfile
        fields = [
            "id", "user", "email", "first_name", "last_name", "full_name",
            "role", "is_active", "joined_at"
        ]
        read_only_fields = ["id", "joined_at"]

class StaffInviteSerializer(serializers.Serializer):
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    role = serializers.ChoiceField(choices=[
        (UserRole.DOCTOR, "Doctor"),
        (UserRole.RECEPTIONIST, "Receptionist"),
        (UserRole.CLINIC_ADMIN, "Clinic Admin")
    ])

class StaffRoleUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserClinicProfile
        fields = ["role", "is_active"]

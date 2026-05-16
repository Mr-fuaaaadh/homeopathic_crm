"""
apps/accounts/serializers.py
Authentication serializers with custom JWT claims, user registration, and profile management.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import UserRole, UserClinicProfile

User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Extended JWT serializer.
    Injects clinic_id, role, and user metadata into the token payload.
    Also handles login tracking and session creation.
    """

    # Accept clinic slug/id for multi-clinic users
    clinic_id = serializers.UUIDField(required=False, allow_null=True)

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Standard claims
        token["email"] = user.email
        token["role"] = user.role
        token["full_name"] = user.full_name
        return token

    def validate(self, attrs):
        clinic_id = attrs.pop("clinic_id", None)
        data = super().validate(attrs)

        user = self.user
        request = self.context.get("request")

        # Resolve clinic for this session
        active_clinic = None
        if user.role != UserRole.SUPER_ADMIN:
            if clinic_id:
                profile = user.clinic_profiles.filter(
                    clinic_id=clinic_id, is_active=True
                ).first()
                if not profile:
                    raise serializers.ValidationError(
                        {"clinic_id": "You do not have access to this clinic."}
                    )
                active_clinic = profile.clinic
            else:
                # Auto-select if user belongs to only one clinic
                profiles = user.clinic_profiles.filter(is_active=True)
                if profiles.count() == 1:
                    active_clinic = profiles.first().clinic
                elif profiles.count() > 1:
                    raise serializers.ValidationError(
                        {"clinic_id": "Multiple clinics found. Please specify clinic_id."}
                    )

        # Inject clinic_id into token payload
        refresh = RefreshToken(data["refresh"])
        access = refresh.access_token
        if active_clinic:
            refresh["clinic_id"] = str(active_clinic.id)
            access["clinic_id"] = str(active_clinic.id)
            access["clinic_name"] = active_clinic.name
            # Update effective role for this clinic
            if user.role != UserRole.SUPER_ADMIN:
                clinic_role = user.get_clinic_role(active_clinic.id)
                if clinic_role:
                    access["role"] = clinic_role

        # Record login
        ip = self._get_ip(request)
        user.record_login(ip_address=ip)

        # Create session record
        from apps.accounts.models import LoginSession
        LoginSession.objects.create(
            user=user,
            clinic=active_clinic,
            jti=str(access["jti"]),
            ip_address=ip,
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:500] if request else "",
        )

        # Build response
        data["refresh"] = str(refresh)
        data["access"] = str(access)
        data["user"] = UserProfileSerializer(user).data
        if active_clinic:
            data["clinic"] = {
                "id": str(active_clinic.id),
                "name": active_clinic.name,
                "slug": active_clinic.slug,
            }

        return data

    def _get_ip(self, request):
        if not request:
            return None
        x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded:
            return x_forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")


class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    """Refresh token with updated clinic context."""
    pass


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "email", "password", "password_confirm",
            "first_name", "last_name", "phone",
            "role", "designation", "qualification", "specialization",
        ]
        extra_kwargs = {
            "role": {"default": UserRole.RECEPTIONIST},
        }

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError({"password": "Passwords do not match."})
        # Only super admin can create super admin accounts
        request = self.context.get("request")
        if attrs.get("role") == UserRole.SUPER_ADMIN:
            if not request or not request.user.is_authenticated or request.user.role != UserRole.SUPER_ADMIN:
                raise serializers.ValidationError(
                    {"role": "Only Super Admins can create Super Admin accounts."}
                )
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    clinics = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "full_name",
            "phone", "role", "designation", "qualification",
            "specialization", "registration_number", "avatar",
            "is_active", "is_email_verified", "last_login_at",
            "login_count", "clinics", "created_at",
        ]
        read_only_fields = ["id", "email", "is_active", "last_login_at", "login_count", "created_at"]

    def get_clinics(self, obj):
        profiles = obj.clinic_profiles.filter(is_active=True).select_related("clinic")
        return [
            {
                "id": str(p.clinic.id),
                "name": p.clinic.name,
                "slug": p.clinic.slug,
                "role": p.role,
            }
            for p in profiles
        ]

class UserListSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "full_name", "role", "avatar", "is_active"]



class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError({"new_password": "Passwords do not match."})
        return attrs

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value
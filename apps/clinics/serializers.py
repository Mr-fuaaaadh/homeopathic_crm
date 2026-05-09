import re
from rest_framework import serializers
import structlog
from django.utils import timezone

# pyrefly: ignore [missing-import]
from apps.clinics.models import Clinic, SubscriptionPlan, ClinicStatus

logger = structlog.get_logger(__name__)

# -------------------- Validations -------------------- #

PHONE_REGEX = re.compile(r'^\+?1?\d{9,15}$')
GSTIN_REGEX = re.compile(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$')

def validate_phone_number(value):
    if value and not PHONE_REGEX.match(value):
        raise serializers.ValidationError("Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.")
    return value

def validate_gstin_number(value):
    if value and not GSTIN_REGEX.match(value):
        raise serializers.ValidationError("Invalid GSTIN format.")
    return value

def validate_business_hours_json(value):
    if not isinstance(value, dict):
        raise serializers.ValidationError("Business hours must be a valid JSON dictionary.")
    
    valid_days = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
    for day, schedule in value.items():
        if day.lower() not in valid_days:
            raise serializers.ValidationError(f"Invalid day in business hours: {day}")
        if not isinstance(schedule, dict):
            raise serializers.ValidationError(f"Schedule for {day} must be a dictionary.")
        if "is_closed" not in schedule:
            raise serializers.ValidationError(f"'is_closed' boolean is required for {day}.")
        if not schedule.get("is_closed"):
            if "open" not in schedule or "close" not in schedule:
                raise serializers.ValidationError(f"'open' and 'close' times are required for {day} if not closed.")
    return value


# -------------------- Serializers -------------------- #

class ClinicListSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source="owner.full_name", read_only=True)

    class Meta:
        model = Clinic
        fields = [
            "id",
            "name",
            "slug",
            "email",
            "phone",
            "city",
            "state",
            "status",
            "subscription_plan",
            "owner_name",
            "created_at",
        ]


class ClinicDetailSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source="owner.full_name", read_only=True)
    owner_email = serializers.EmailField(source="owner.email", read_only=True)
    is_subscription_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = Clinic
        fields = [
            "id",
            "name",
            "slug",
            "logo",
            "tagline",
            "email",
            "phone",
            "website",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "country",
            "pincode",
            "timezone",
            "currency",
            "language",
            "business_hours",
            "subscription_plan",
            "subscription_start",
            "subscription_end",
            "max_doctors",
            "max_patients",
            "status",
            "registration_number",
            "gstin",
            "owner",
            "owner_name",
            "owner_email",
            "is_subscription_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class ClinicCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Clinic
        fields = [
            "name",
            "slug",
            "logo",
            "tagline",
            "email",
            "phone",
            "website",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "country",
            "pincode",
            "timezone",
            "currency",
            "language",
            "business_hours",
            "subscription_plan",
            "subscription_start",
            "subscription_end",
            "max_doctors",
            "max_patients",
            "status",
            "registration_number",
            "gstin",
            "owner",
        ]

    def validate_phone(self, value):
        return validate_phone_number(value)

    def validate_gstin(self, value):
        return validate_gstin_number(value)

    def validate_business_hours(self, value):
        return validate_business_hours_json(value)

    def validate_pincode(self, value):
        if value and not value.isalnum():
            raise serializers.ValidationError("Pincode must be alphanumeric.")
        if value and len(value) < 4:
            raise serializers.ValidationError("Pincode is too short.")
        return value

    def validate(self, data):
        # Validate subscription dates
        sub_start = data.get("subscription_start", getattr(self.instance, "subscription_start", None))
        sub_end = data.get("subscription_end", getattr(self.instance, "subscription_end", None))
        
        if sub_start and sub_end and sub_end < sub_start:
            raise serializers.ValidationError({"subscription_end": "Subscription end date must be after start date."})
        
        # Ensure slug is lowercase and doesn't contain spaces
        slug = data.get("slug")
        if slug and not re.match(r'^[-a-zA-Z0-9_]+$', slug):
            raise serializers.ValidationError({"slug": "Slug can only contain alphanumeric characters, hyphens, and underscores."})
            
        return data


class ClinicSubscriptionSerializer(serializers.Serializer):
    subscription_plan = serializers.ChoiceField(choices=SubscriptionPlan.choices)
    subscription_start = serializers.DateField(required=False, allow_null=True)
    subscription_end = serializers.DateField(required=False, allow_null=True)
    max_doctors = serializers.IntegerField(min_value=1, required=False)
    max_patients = serializers.IntegerField(min_value=1, required=False)
    status = serializers.ChoiceField(choices=ClinicStatus.choices, required=False)

    def validate(self, data):
        sub_start = data.get("subscription_start")
        sub_end = data.get("subscription_end")

        if sub_start and sub_end and sub_end < sub_start:
            raise serializers.ValidationError({"subscription_end": "Subscription end date must be after start date."})

        return data
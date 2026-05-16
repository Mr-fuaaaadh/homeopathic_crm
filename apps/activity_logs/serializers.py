from rest_framework import serializers
from apps.activity_logs.models import ActivityLog

class ActivityLogSerializer(serializers.ModelSerializer):
    user_name = serializers.ReadOnlyField(source="user.full_name")
    clinic_name = serializers.ReadOnlyField(source="clinic.name")

    class Meta:
        model = ActivityLog
        fields = "__all__"
        read_only_fields = ["id", "timestamp"]

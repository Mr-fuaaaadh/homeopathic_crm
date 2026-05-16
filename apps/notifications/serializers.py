from rest_framework import serializers
from apps.notifications.models import Notification, NotificationTemplate, NotificationLog

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "title", "message", "is_read", "read_at", "link", "created_at"]
        read_only_fields = ["id", "created_at", "read_at"]

class NotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplate
        fields = ["id", "name", "type", "subject", "body", "is_active"]
        read_only_fields = ["id"]

class NotificationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationLog
        fields = "__all__"
        read_only_fields = ["id", "created_at"]

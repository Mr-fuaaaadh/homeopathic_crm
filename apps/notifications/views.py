import structlog
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.notifications.models import Notification, NotificationTemplate, NotificationLog
from apps.notifications.serializers import (
    NotificationSerializer, NotificationTemplateSerializer, NotificationLogSerializer
)
from utils.mixins import TenantMixin, AuditMixin
from utils.permissions import IsClinicMember, IsClinicAdminOrAbove

logger = structlog.get_logger(__name__)

class NotificationViewSet(TenantMixin, viewsets.ModelViewSet):
    """
    Manage user-specific in-app notifications.
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated, IsClinicMember]

    def get_queryset(self):
        return Notification.objects.filter(
            clinic=self.request.clinic,
            user=self.request.user
        )

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        """Mark a notification as read."""
        notification = self.get_object()
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
        return Response({"status": "read"})

    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        """Mark all notifications as read."""
        self.get_queryset().filter(is_read=False).update(
            is_read=True, read_at=timezone.now()
        )
        return Response({"status": "all read"})

class NotificationTemplateViewSet(TenantMixin, AuditMixin, viewsets.ModelViewSet):
    """
    Manage message templates for SMS/Email/WhatsApp.
    """
    queryset = NotificationTemplate.objects.all()
    serializer_class = NotificationTemplateSerializer
    permission_classes = [IsAuthenticated, IsClinicMember, IsClinicAdminOrAbove]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["type", "is_active"]
    search_fields = ["name", "subject", "body"]

    def perform_create(self, serializer):
        serializer.save(clinic=self.request.clinic)

class NotificationLogViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """
    View history of sent messages.
    """
    queryset = NotificationLog.objects.all()
    serializer_class = NotificationLogSerializer
    permission_classes = [IsAuthenticated, IsClinicMember, IsClinicAdminOrAbove]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["type", "status"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]

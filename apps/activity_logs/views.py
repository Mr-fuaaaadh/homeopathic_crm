import structlog
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.activity_logs.models import ActivityLog
from apps.activity_logs.serializers import ActivityLogSerializer
from utils.mixins import TenantMixin
from utils.permissions import IsClinicMember, IsClinicAdminOrAbove

logger = structlog.get_logger(__name__)

class ActivityLogViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """
    View audit logs for the clinic.
    Only Clinic Admins can view logs.
    """
    queryset = ActivityLog.objects.select_related("user", "clinic")
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAuthenticated, IsClinicMember, IsClinicAdminOrAbove]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["action", "resource_type", "user"]
    search_fields = ["user_email", "resource_id", "description"]
    ordering_fields = ["timestamp"]
    ordering = ["-timestamp"]

"""
utils/mixins.py
Tenant-aware ViewSet mixin — automatically filters querysets by clinic_id.
This is the SECOND line of defense for data isolation (middleware is first).

All ViewSets that handle tenant data MUST inherit from TenantMixin.
"""

import structlog
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import UserRole

logger = structlog.get_logger(__name__)


class TenantMixin:
    """
    Mixin for all tenant-scoped ViewSets.
    
    - Automatically filters get_queryset() by clinic
    - Automatically injects clinic into serializer context
    - Automatically sets clinic on new objects
    - Validates tenant context exists

    Usage:
        class PatientViewSet(TenantMixin, ModelViewSet):
            queryset = Patient.objects.all()
            serializer_class = PatientSerializer
    """

    def get_queryset(self):
        """
        Returns queryset filtered to current clinic.
        Super Admin without X-Clinic-ID sees all records.
        """
        queryset = super().get_queryset()

        user = self.request.user
        clinic = getattr(self.request, "clinic", None)

        # Super admin with no specific clinic: see everything
        if user.role == UserRole.SUPER_ADMIN and clinic is None:
            return queryset

        # All other cases: scope to clinic
        if clinic is None:
            logger.warning(
                "tenant_queryset_no_clinic",
                user_id=str(user.id),
                path=self.request.path,
            )
            # Return empty queryset rather than exposing all data
            return queryset.none()

        return queryset.filter(clinic=clinic)

    def get_serializer_context(self):
        """Inject clinic into serializer context for nested creation."""
        context = super().get_serializer_context()
        context["clinic"] = getattr(self.request, "clinic", None)
        context["request"] = self.request
        return context

    def perform_create(self, serializer):
        """Auto-inject clinic on creation."""
        clinic = getattr(self.request, "clinic", None)
        if clinic is None and self.request.user.role != UserRole.SUPER_ADMIN:
            raise PermissionDenied("Clinic context is required to create records.")
        serializer.save(clinic=clinic)

    def get_clinic_or_404(self):
        """Helper to get current clinic or raise error."""
        clinic = getattr(self.request, "clinic", None)
        if clinic is None:
            raise ValidationError({"clinic": "Clinic context required."})
        return clinic


class AuditMixin:
    """
    Mixin that provides easy audit logging from views.
    """

    def log_action(self, action, resource_type, resource_id="", description="", changes=None):
        from apps.activity_logs.models import ActivityLog
        try:
            ActivityLog.objects.create(
                user=self.request.user,
                user_email=self.request.user.email,
                user_role=self.request.user.role,
                clinic=getattr(self.request, "clinic", None),
                clinic_name=getattr(getattr(self.request, "clinic", None), "name", ""),
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id),
                description=description,
                changes=changes,
                ip_address=self._get_ip(),
                request_path=self.request.path,
                request_method=self.request.method,
            )
        except Exception as e:
            logger.error("manual_audit_log_failed", error=str(e))

    def _get_ip(self):
        x_forwarded = self.request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded:
            return x_forwarded.split(",")[0].strip()
        return self.request.META.get("REMOTE_ADDR")


class CacheMixin:
    """
    Per-clinic caching helper for ViewSets.
    """

    cache_key_prefix = ""
    cache_timeout = 300

    def get_cache_key(self, suffix=""):
        clinic_id = getattr(self.request, "clinic_id", "global")
        return f"{self.cache_key_prefix}:{clinic_id}:{suffix}"

    def invalidate_clinic_cache(self):
        from django.core.cache import cache
        clinic_id = getattr(self.request, "clinic_id", None)
        if clinic_id and self.cache_key_prefix:
            pattern = f"{self.cache_key_prefix}:{clinic_id}:*"
            cache.delete_pattern(pattern)
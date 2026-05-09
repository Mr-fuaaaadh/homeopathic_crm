"""
middleware/audit.py
Automatic audit logging middleware.
Logs every mutating API call (POST/PUT/PATCH/DELETE) to ActivityLog.
"""

import json
import time
import structlog

logger = structlog.get_logger(__name__)

AUDITED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
SKIP_PATHS = ["/silk/", "/static/", "/media/", "/admin/"]

# Maps URL patterns to resource types
RESOURCE_MAP = {
    "/api/v1/patients": "Patient",
    "/api/v1/appointments": "Appointment",
    "/api/v1/prescriptions": "Prescription",
    "/api/v1/staff": "Staff",
    "/api/v1/billing/invoices": "Invoice",
    "/api/v1/billing/payments": "Payment",
    "/api/v1/clinics": "Clinic",
    "/api/v1/auth": "Auth",
    "/api/v1/notifications": "Notification",
}

METHOD_ACTION_MAP = {
    "POST": "create",
    "PUT": "update",
    "PATCH": "update",
    "DELETE": "delete",
}


def _get_resource_type(path):
    for prefix, resource in RESOURCE_MAP.items():
        if path.startswith(prefix):
            return resource
    return "Unknown"


def _get_client_ip(request):
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class AuditLogMiddleware:
    """
    Automatically creates ActivityLog entries for all mutating requests.
    Runs AFTER the view so it can capture the response status.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if any(request.path.startswith(p) for p in SKIP_PATHS):
            return self.get_response(request)

        start_time = time.monotonic()
        response = self.get_response(request)
        duration_ms = int((time.monotonic() - start_time) * 1000)

        # Only audit mutating requests that succeeded
        if request.method in AUDITED_METHODS and response.status_code < 400:
            self._create_log(request, response, duration_ms)

        return response

    def _create_log(self, request, response, duration_ms):
        from django.contrib.auth.models import AnonymousUser
        from apps.activity_logs.models import ActivityLog, ActivityAction

        try:
            user = getattr(request, "user", None)
            if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
                return

            clinic = getattr(request, "clinic", None)
            action = METHOD_ACTION_MAP.get(request.method, "unknown")
            resource_type = _get_resource_type(request.path)

            # Special case: auth actions
            if request.path.startswith("/api/v1/auth/login"):
                action = ActivityAction.LOGIN
            elif request.path.startswith("/api/v1/auth/logout"):
                action = ActivityAction.LOGOUT

            # Extract resource_id from response if available
            resource_id = ""
            try:
                if hasattr(response, "data") and isinstance(response.data, dict):
                    resource_id = str(response.data.get("id", ""))
            except Exception:
                pass

            ActivityLog.objects.create(
                user=user,
                user_email=user.email,
                user_role=user.role,
                clinic=clinic,
                clinic_name=clinic.name if clinic else "",
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                description=f"{user.full_name} {action}d {resource_type}",
                metadata={
                    "duration_ms": duration_ms,
                    "status_code": response.status_code,
                },
                ip_address=_get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
                request_path=request.path,
                request_method=request.method,
            )
        except Exception as e:
            # Audit log MUST NOT break the main request
            logger.error("audit_log_failed", error=str(e), path=request.path)
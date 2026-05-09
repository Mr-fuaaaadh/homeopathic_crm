"""
middleware/tenant.py
Multi-Tenant Middleware — enforces clinic isolation on every request.

How tenant resolution works:
  1. JWT token contains clinic_id claim (set at login)
  2. Header X-Clinic-ID overrides (for super admin switching)
  3. Attaches `request.clinic` for use in all views

This middleware is the FOUNDATION of data isolation.
"""

import structlog
from django.http import JsonResponse
from django.core.cache import cache
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

logger = structlog.get_logger(__name__)


class TenantMiddleware:
    """
    Resolves the active tenant clinic for every authenticated request.
    
    Sets:
        request.clinic      — Active Clinic ORM instance (or None for super admin)
        request.clinic_id   — Active clinic UUID string
        request.is_super_admin — Boolean
    """

    EXEMPT_PATHS = [
        "/admin/",
        "/api/v1/auth/login/",
        "/api/v1/auth/register/",
        "/api/v1/auth/token/refresh/",
        "/api/v1/auth/password/reset/",
        "/api/v1/auth/password/reset/confirm/",
        "/silk/",
        "/static/",
        "/media/",
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Initialize defaults
        request.clinic = None
        request.clinic_id = None
        request.is_super_admin = False

        # Skip auth-exempt paths
        if any(request.path.startswith(p) for p in self.EXEMPT_PATHS):
            return self.get_response(request)

        # Attempt JWT authentication
        user = self._get_user_from_jwt(request)
        if not user:
            return self.get_response(request)

        from apps.accounts.models import UserRole
        request.is_super_admin = (user.role == UserRole.SUPER_ADMIN)

        # Super admin: allow X-Clinic-ID header to scope a specific clinic
        clinic_id = request.headers.get("X-Clinic-ID") or self._get_clinic_id_from_token(request)

        if clinic_id:
            clinic = self._resolve_clinic(clinic_id, request)
            if clinic is None:
                return JsonResponse(
                    {"error": "Clinic not found or access denied", "code": "CLINIC_NOT_FOUND"},
                    status=403,
                )
            if not request.is_super_admin and not user.has_clinic_access(clinic_id):
                logger.warning(
                    "unauthorized_clinic_access",
                    user_id=str(user.id),
                    clinic_id=str(clinic_id),
                    path=request.path,
                )
                return JsonResponse(
                    {"error": "You do not have access to this clinic", "code": "ACCESS_DENIED"},
                    status=403,
                )
            request.clinic = clinic
            request.clinic_id = str(clinic.id)
        elif not request.is_super_admin:
            # Non-super-admin must always have a clinic context
            # (unless they're accessing global endpoints)
            pass

        return self.get_response(request)

    def _get_user_from_jwt(self, request):
        """Extract and validate JWT, return User or None."""
        try:
            auth = JWTAuthentication()
            result = auth.authenticate(request)
            if result:
                user, token = result
                return user
        except (InvalidToken, TokenError):
            pass
        return None

    def _get_clinic_id_from_token(self, request):
        """Extract clinic_id from JWT payload."""
        try:
            auth = JWTAuthentication()
            result = auth.authenticate(request)
            if result:
                _, token = result
                return token.payload.get("clinic_id")
        except Exception:
            pass
        return None

    def _resolve_clinic(self, clinic_id, request):
        """Resolve clinic from cache or DB."""
        cache_key = f"clinic:{clinic_id}"
        clinic = cache.get(cache_key)
        if clinic is None:
            from apps.clinics.models import Clinic, ClinicStatus
            try:
                clinic = Clinic.objects.get(id=clinic_id, status=ClinicStatus.ACTIVE)
                cache.set(cache_key, clinic, timeout=3600)  # Cache 1 hour
            except Clinic.DoesNotExist:
                return None
        return clinic
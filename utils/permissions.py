"""
utils/permissions.py
Role-Based Access Control (RBAC) permission classes for DRF.

Usage in views:
    permission_classes = [IsAuthenticated, IsClinicAdmin]
    permission_classes = [IsAuthenticated, IsDoctorOrAbove]
    permission_classes = [IsAuthenticated, IsSuperAdmin]
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS
from apps.accounts.models import UserRole


# ─── Role Hierarchy ───────────────────────────────────────────────────────────
# super_admin > clinic_admin > doctor > receptionist > patient

ROLE_HIERARCHY = {
    UserRole.SUPER_ADMIN: 5,
    UserRole.CLINIC_ADMIN: 4,
    UserRole.DOCTOR: 3,
    UserRole.RECEPTIONIST: 2,
    UserRole.PATIENT: 1,
}


def _get_clinic_role(user, clinic):
    """Get user's effective role for the current clinic."""
    if user.role == UserRole.SUPER_ADMIN:
        return UserRole.SUPER_ADMIN
    if clinic:
        profile = user.clinic_profiles.filter(clinic=clinic, is_active=True).first()
        if profile:
            return profile.role
    return user.role  # Fallback to global role


def _has_min_role(user, clinic, min_role):
    role = _get_clinic_role(user, clinic)
    return ROLE_HIERARCHY.get(role, 0) >= ROLE_HIERARCHY.get(min_role, 99)


class IsSuperAdmin(BasePermission):
    """Only Super Admins can access."""
    message = "Only Super Admins can perform this action."

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role == UserRole.SUPER_ADMIN
        )


class IsClinicAdminOrAbove(BasePermission):
    """Clinic Admin or Super Admin."""
    message = "Only Clinic Admins or Super Admins can perform this action."

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        clinic = getattr(request, "clinic", None)
        return _has_min_role(request.user, clinic, UserRole.CLINIC_ADMIN)


class IsDoctorOrAbove(BasePermission):
    """Doctor, Clinic Admin, or Super Admin."""
    message = "Only Doctors or above can perform this action."

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        clinic = getattr(request, "clinic", None)
        return _has_min_role(request.user, clinic, UserRole.DOCTOR)


class IsReceptionistOrAbove(BasePermission):
    """Any authenticated clinic staff."""
    message = "Only clinic staff can perform this action."

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        clinic = getattr(request, "clinic", None)
        return _has_min_role(request.user, clinic, UserRole.RECEPTIONIST)


class IsClinicMember(BasePermission):
    """User must belong to the current clinic."""
    message = "You do not have access to this clinic."

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.role == UserRole.SUPER_ADMIN:
            return True
        clinic = getattr(request, "clinic", None)
        if not clinic:
            return False
        return request.user.has_clinic_access(clinic.id)


class IsDoctorOrReadOnly(BasePermission):
    """Doctors can write; others can read only."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            clinic = getattr(request, "clinic", None)
            return _has_min_role(request.user, clinic, UserRole.RECEPTIONIST)
        clinic = getattr(request, "clinic", None)
        return _has_min_role(request.user, clinic, UserRole.DOCTOR)


class IsOwnerOrClinicAdmin(BasePermission):
    """
    Object-level permission: owner of the record or clinic admin.
    Use with has_object_permission.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.user.role == UserRole.SUPER_ADMIN:
            return True
        clinic = getattr(request, "clinic", None)
        if _has_min_role(request.user, clinic, UserRole.CLINIC_ADMIN):
            return True
        # Check if user is the owner/creator
        owner_fields = ["user", "created_by", "doctor", "registered_by"]
        for field in owner_fields:
            if hasattr(obj, field) and getattr(obj, field) == request.user:
                return True
        return False


# ─── Convenience Combinations ─────────────────────────────────────────────────

class PatientPermission(BasePermission):
    """
    Receptionist+ can create/read patients.
    Doctor+ can update.
    ClinicAdmin can delete (soft).
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        clinic = getattr(request, "clinic", None)
        if request.method in SAFE_METHODS:
            return _has_min_role(request.user, clinic, UserRole.RECEPTIONIST)
        if request.method == "DELETE":
            return _has_min_role(request.user, clinic, UserRole.CLINIC_ADMIN)
        return _has_min_role(request.user, clinic, UserRole.RECEPTIONIST)


class PrescriptionPermission(BasePermission):
    """Only doctors can create/edit prescriptions."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        clinic = getattr(request, "clinic", None)
        if request.method in SAFE_METHODS:
            return _has_min_role(request.user, clinic, UserRole.RECEPTIONIST)
        return _has_min_role(request.user, clinic, UserRole.DOCTOR)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if request.user.role == UserRole.SUPER_ADMIN:
            return True
        clinic = getattr(request, "clinic", None)
        if _has_min_role(request.user, clinic, UserRole.CLINIC_ADMIN):
            return True
        # Only the prescribing doctor can edit their own prescriptions
        return obj.doctor == request.user
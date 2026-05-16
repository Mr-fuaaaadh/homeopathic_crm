import structlog
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import User, UserClinicProfile, UserRole
from apps.staff.serializers import (
    StaffProfileSerializer, StaffInviteSerializer, StaffRoleUpdateSerializer
)
from utils.mixins import TenantMixin, AuditMixin
from utils.permissions import IsClinicMember, IsClinicAdminOrAbove

logger = structlog.get_logger(__name__)

class StaffViewSet(TenantMixin, AuditMixin, viewsets.ModelViewSet):
    """
    Manage clinic staff members.
    Only Clinic Admins can invite or change roles.
    """
    queryset = UserClinicProfile.objects.select_related("user", "clinic")
    serializer_class = StaffProfileSerializer
    permission_classes = [IsAuthenticated, IsClinicMember, IsClinicAdminOrAbove]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["role", "is_active"]
    search_fields = ["user__first_name", "user__last_name", "user__email"]

    def get_queryset(self):
        # Already filtered by TenantMixin to the current clinic
        return super().get_queryset()

    @action(detail=False, methods=["post"])
    @transaction.atomic
    def invite(self, request):
        """Invite a new staff member to the clinic."""
        serializer = StaffInviteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"]
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "first_name": serializer.validated_data["first_name"],
                "last_name": serializer.validated_data["last_name"],
                "role": serializer.validated_data["role"], # Default global role
            }
        )

        if UserClinicProfile.objects.filter(user=user, clinic=request.clinic).exists():
            return Response(
                {"error": "User is already a member of this clinic."},
                status=status.HTTP_400_BAD_REQUEST
            )

        profile = UserClinicProfile.objects.create(
            user=user,
            clinic=request.clinic,
            role=serializer.validated_data["role"],
            invited_by=request.user
        )

        # In real scenario, send invitation email here
        
        return Response(StaffProfileSerializer(profile).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"], url_path="update-role")
    def update_role(self, request, pk=None):
        """Update a staff member's role or active status."""
        profile = self.get_object()
        serializer = StaffRoleUpdateSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"])
    def doctors(self, request):
        """List all doctors in the clinic."""
        doctors = self.get_queryset().filter(role=UserRole.DOCTOR, is_active=True)
        return Response(StaffProfileSerializer(doctors, many=True).data)

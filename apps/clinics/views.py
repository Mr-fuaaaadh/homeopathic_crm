"""
apps/clinics/views.py
Clinic management APIs: list/create/detail/update/delete + stats + subscription update.
"""

import structlog
from django.db import transaction, IntegrityError
from django.db.models import Count, Q
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from apps.accounts.models import UserClinicProfile, UserRole
from apps.clinics.models import Clinic, ClinicSettings, ClinicStatus, SubscriptionPlan
from utils.permissions import IsClinicAdminOrAbove, IsClinicMember, IsSuperAdmin

from apps.clinics.serializers import (
    ClinicCreateUpdateSerializer,
    ClinicDetailSerializer,
    ClinicListSerializer,
    ClinicSubscriptionSerializer,
)

logger = structlog.get_logger(__name__)


# -------------------- ViewSet -------------------- #

class ClinicViewSet(ModelViewSet):
    """
    GET    /api/v1/clinics/
    POST   /api/v1/clinics/
    GET    /api/v1/clinics/{id}/
    PUT    /api/v1/clinics/{id}/
    PATCH  /api/v1/clinics/{id}/
    DELETE /api/v1/clinics/{id}/
    GET    /api/v1/clinics/{id}/stats/
    POST   /api/v1/clinics/{id}/subscription/
    """

    queryset = Clinic.objects.select_related("owner")
    lookup_field = "id"
    
    # Production-ready filtering, searching, and ordering
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status", "subscription_plan", "city", "state"]
    search_fields = ["name", "email", "phone", "city", "slug"]
    ordering_fields = ["created_at", "updated_at", "name", "city"]
    ordering = ["-created_at"]

    def get_permissions(self):
        # Super admin only for global list/create/delete
        if self.action in ["list", "create", "destroy"]:
            permission_classes = [IsAuthenticated, IsSuperAdmin]
        # Subscription update reserved to clinic admin+
        elif self.action == "subscription":
            permission_classes = [IsAuthenticated, IsClinicAdminOrAbove]
        else:
            permission_classes = [IsAuthenticated, IsClinicMember]
        return [p() for p in permission_classes]

    def get_queryset(self):
        user = self.request.user
        if user.role == UserRole.SUPER_ADMIN:
            return self.queryset

        # For normal users, only return clinics they are active members of
        clinic_ids = UserClinicProfile.objects.filter(
            user=user, is_active=True
        ).values_list("clinic_id", flat=True)
        return self.queryset.filter(id__in=clinic_ids)

    def get_serializer_class(self):
        if self.action == "list":
            return ClinicListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return ClinicCreateUpdateSerializer
        return ClinicDetailSerializer

    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                clinic = serializer.save()
                
                # Create default settings
                ClinicSettings.objects.get_or_create(clinic=clinic)
                
                logger.info("clinic_created", clinic_id=str(clinic.id), by=str(self.request.user.id))
        except IntegrityError as e:
            logger.error("clinic_creation_integrity_error", error=str(e), by=str(self.request.user.id))
            raise serializers.ValidationError({"detail": "Integrity error, possibly a duplicate slug or email."})
        except Exception as e:
            logger.exception("clinic_creation_failed", error=str(e), by=str(self.request.user.id))
            raise serializers.ValidationError({"detail": "An error occurred while creating the clinic."})

    def perform_destroy(self, instance):
        try:
            # Soft delete from SoftDeleteModel
            instance.delete(deleted_by=self.request.user)
            logger.info("clinic_deleted", clinic_id=str(instance.id), by=str(self.request.user.id))
        except Exception as e:
            logger.exception("clinic_deletion_failed", clinic_id=str(instance.id), error=str(e))
            raise serializers.ValidationError({"detail": "Failed to delete the clinic."})

    @action(detail=True, methods=["get"], url_path="stats")
    def stats(self, request, id=None):
        clinic = self.get_object()

        try:
            # Lazy imports to avoid circular load issues
            from apps.appointments.models import Appointment
            from apps.patients.models import Patient
            from apps.prescriptions.models import Prescription

            patient_count = Patient.objects.filter(clinic=clinic).count()
            appointment_qs = Appointment.objects.filter(clinic=clinic)
            prescription_count = Prescription.objects.filter(clinic=clinic).count()
            staff_count = UserClinicProfile.objects.filter(clinic=clinic, is_active=True).count()

            appointment_summary = appointment_qs.aggregate(
                total=Count("id"),
                scheduled=Count("id", filter=Q(status="scheduled")),
                completed=Count("id", filter=Q(status="completed")),
                cancelled=Count("id", filter=Q(status="cancelled")),
            )

            return Response(
                {
                    "clinic_id": str(clinic.id),
                    "clinic_name": clinic.name,
                    "patients": patient_count,
                    "staff": staff_count,
                    "prescriptions": prescription_count,
                    "appointments": appointment_summary,
                    "subscription": {
                        "plan": clinic.subscription_plan,
                        "status": clinic.status,
                        "is_active": clinic.is_subscription_active,
                        "start": clinic.subscription_start,
                        "end": clinic.subscription_end,
                    },
                }
            )
        except ObjectDoesNotExist as e:
            logger.error("clinic_stats_missing_model", clinic_id=str(clinic.id), error=str(e))
            return Response({"detail": "Related data not found."}, status=status.HTTP_404_NOT_FOUND)
        except ImportError as e:
            logger.error("clinic_stats_import_error", error=str(e))
            return Response({"detail": "Server configuration error."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.exception("clinic_stats_error", clinic_id=str(clinic.id), error=str(e))
            return Response({"detail": "Failed to retrieve stats."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=["post"], url_path="subscription")
    def subscription(self, request, id=None):
        clinic = self.get_object()
        serializer = ClinicSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        
        try:
            with transaction.atomic():
                for field in [
                    "subscription_plan",
                    "subscription_start",
                    "subscription_end",
                    "max_doctors",
                    "max_patients",
                    "status",
                ]:
                    if field in data:
                        setattr(clinic, field, data[field])

                clinic.save(
                    update_fields=[
                        f
                        for f in [
                            "subscription_plan",
                            "subscription_start",
                            "subscription_end",
                            "max_doctors",
                            "max_patients",
                            "status",
                            "updated_at",
                        ]
                        if hasattr(clinic, f)
                    ]
                )

            logger.info(
                "clinic_subscription_updated",
                clinic_id=str(clinic.id),
                by=str(request.user.id),
                plan=clinic.subscription_plan,
                status=clinic.status,
            )

            return Response(
                {
                    "message": "Subscription updated successfully.",
                    "clinic_id": str(clinic.id),
                    "subscription_plan": clinic.subscription_plan,
                    "subscription_start": clinic.subscription_start,
                    "subscription_end": clinic.subscription_end,
                    "max_doctors": clinic.max_doctors,
                    "max_patients": clinic.max_patients,
                    "status": clinic.status,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.exception("clinic_subscription_update_failed", clinic_id=str(clinic.id), error=str(e))
            return Response({"detail": "Failed to update subscription."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
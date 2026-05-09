"""
apps/patients/views.py
Patient management ViewSet — full CRUD with tenant isolation,
search/filter, history timeline, and attachment upload.
"""

import structlog
from django.core.cache import cache
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, serializers, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.patients.models import Patient, MedicalHistory, PatientAttachment
from apps.patients.serializers import (
    PatientListSerializer,
    PatientDetailSerializer,
    PatientCreateUpdateSerializer,
    MedicalHistorySerializer,
    PatientAttachmentSerializer,
)
from apps.patients.filters import PatientFilter
from utils.mixins import TenantMixin, AuditMixin, CacheMixin
from utils.permissions import PatientPermission, IsClinicMember
from config.settings import CACHE_TTL, MAX_ATTACHMENT_SIZE_MB, ALLOWED_ATTACHMENT_TYPES

logger = structlog.get_logger(__name__)


class PatientViewSet(TenantMixin, AuditMixin, CacheMixin, ModelViewSet):
    """
    GET    /api/v1/patients/                    — List (search/filter/sort)
    POST   /api/v1/patients/                    — Create patient
    GET    /api/v1/patients/{id}/               — Patient detail
    PUT    /api/v1/patients/{id}/               — Full update
    PATCH  /api/v1/patients/{id}/               — Partial update
    DELETE /api/v1/patients/{id}/               — Soft delete
    GET    /api/v1/patients/{id}/history/       — Visit history timeline
    GET    /api/v1/patients/{id}/attachments/   — List attachments
    POST   /api/v1/patients/{id}/attachments/   — Upload file
    DELETE /api/v1/patients/{id}/attachments/{fid}/ — Remove file
    """

    queryset = Patient.objects.select_related(
        "primary_doctor", "registered_by", "clinic"
    ).prefetch_related("appointments", "prescriptions")
    permission_classes = [IsAuthenticated, IsClinicMember, PatientPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = PatientFilter
    search_fields = [
        "first_name", "last_name", "phone", "email",
        "patient_code", "alternate_phone",
    ]
    ordering_fields = ["created_at", "first_name", "last_name", "patient_code"]
    ordering = ["-created_at"]
    cache_key_prefix = "patients"
    cache_timeout = CACHE_TTL["patient_summary"]

    def get_serializer_class(self):
        if self.action == "list":
            return PatientListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return PatientCreateUpdateSerializer
        return PatientDetailSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        clinic = self.get_clinic_or_404()
        patient = serializer.save(
            clinic=clinic,
            registered_by=self.request.user,
        )
        # Invalidate clinic patient list cache
        self.invalidate_clinic_cache()
        logger.info("patient_created", patient_id=str(patient.id), clinic_id=str(clinic.id))

    @transaction.atomic
    def perform_destroy(self, instance):
        instance.delete(deleted_by=self.request.user)
        self.invalidate_clinic_cache()

    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request, pk=None):
        """
        GET /api/v1/patients/{id}/history/
        Returns chronological visit timeline: appointments + prescriptions.
        """
        patient = self.get_object()
        cache_key = self.get_cache_key(f"history:{pk}")
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        from apps.appointments.models import Appointment
        from apps.prescriptions.models import Prescription

        appointments = Appointment.objects.filter(
            clinic=request.clinic,
            patient=patient,
        ).order_by("-appointment_date").values(
            "id", "appointment_date", "appointment_type",
            "status", "doctor__first_name", "doctor__last_name",
            "chief_complaint",
        )

        prescriptions = Prescription.objects.filter(
            clinic=request.clinic,
            patient=patient,
        ).order_by("-visit_date").values(
            "id", "visit_date", "visit_number",
            "chief_complaint", "doctor__first_name", "doctor__last_name",
            "next_visit_date",
        )

        # Merge and sort into unified timeline
        timeline = []
        for apt in appointments:
            timeline.append({
                "type": "appointment",
                "date": str(apt["appointment_date"]),
                "data": apt,
            })
        for rx in prescriptions:
            timeline.append({
                "type": "prescription",
                "date": str(rx["visit_date"]),
                "data": rx,
            })

        timeline.sort(key=lambda x: x["date"], reverse=True)

        result = {
            "patient_id": str(patient.id),
            "patient_name": patient.full_name,
            "total_visits": len([t for t in timeline if t["type"] == "appointment"]),
            "total_prescriptions": len([t for t in timeline if t["type"] == "prescription"]),
            "timeline": timeline,
        }
        cache.set(cache_key, result, timeout=self.cache_timeout)
        return Response(result)

    @action(
        detail=True,
        methods=["get", "post"],
        url_path="attachments",
        parser_classes=[MultiPartParser, FormParser, JSONParser],
    )
    def attachments(self, request, pk=None):
        """
        GET  — List patient attachments
        POST — Upload new attachment
        """
        patient = self.get_object()

        if request.method == "GET":
            attachments = PatientAttachment.objects.filter(
                clinic=request.clinic, patient=patient
            )
            return Response(PatientAttachmentSerializer(attachments, many=True).data)

        # POST — Upload
        file = request.FILES.get("file")
        if not file:
            return Response({"error": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate size
        if file.size > MAX_ATTACHMENT_SIZE_MB * 1024 * 1024:
            return Response(
                {"error": f"File too large. Max {MAX_ATTACHMENT_SIZE_MB}MB allowed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate type
        if file.content_type not in ALLOWED_ATTACHMENT_TYPES:
            return Response(
                {"error": f"File type {file.content_type} not allowed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        attachment = PatientAttachment.objects.create(
            clinic=request.clinic,
            patient=patient,
            file=file,
            file_name=file.name,
            file_type=file.content_type,
            file_size=file.size,
            description=request.data.get("description", ""),
            category=request.data.get("category", "other"),
            uploaded_by=request.user,
        )

        return Response(
            PatientAttachmentSerializer(attachment).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"attachments/(?P<attachment_id>[0-9a-f-]+)",
    )
    def delete_attachment(self, request, pk=None, attachment_id=None):
        """DELETE /api/v1/patients/{id}/attachments/{attachment_id}/"""
        patient = self.get_object()
        try:
            attachment = PatientAttachment.objects.get(
                id=attachment_id, patient=patient, clinic=request.clinic
            )
            attachment.hard_delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except PatientAttachment.DoesNotExist:
            return Response({"error": "Attachment not found."}, status=status.HTTP_404_NOT_FOUND)
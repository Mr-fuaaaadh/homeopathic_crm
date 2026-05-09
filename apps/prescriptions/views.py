"""
apps/prescriptions/views.py
Prescription management with PDF generation via WeasyPrint.
"""

import io
import structlog
from django.http import HttpResponse
from django.template.loader import render_to_string
from rest_framework import status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.prescriptions.models import Prescription, PrescriptionRemedy, Remedy
from apps.prescriptions.serializers import (
    PrescriptionListSerializer,
    PrescriptionDetailSerializer,
    PrescriptionCreateSerializer,
    PrescriptionRemedySerializer,
    RemedySerializer,
)
from utils.mixins import TenantMixin, AuditMixin
from utils.permissions import IsClinicMember, PrescriptionPermission

logger = structlog.get_logger(__name__)


class PrescriptionViewSet(TenantMixin, AuditMixin, ModelViewSet):
    """
    GET    /api/v1/prescriptions/                 — List
    POST   /api/v1/prescriptions/                 — Create
    GET    /api/v1/prescriptions/{id}/            — Detail
    PUT    /api/v1/prescriptions/{id}/            — Update
    GET    /api/v1/prescriptions/{id}/pdf/        — Download PDF
    POST   /api/v1/prescriptions/{id}/remedies/   — Add remedy
    DELETE /api/v1/prescriptions/{id}/remedies/{rid}/ — Remove remedy
    """

    queryset = Prescription.objects.select_related(
        "patient", "doctor", "appointment", "clinic"
    ).prefetch_related("remedies__remedy")
    permission_classes = [IsAuthenticated, IsClinicMember, PrescriptionPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["patient__first_name", "patient__last_name", "chief_complaint"]
    ordering_fields = ["visit_date", "created_at"]
    ordering = ["-visit_date"]

    def get_serializer_class(self):
        if self.action == "list":
            return PrescriptionListSerializer
        if self.action == "create":
            return PrescriptionCreateSerializer
        return PrescriptionDetailSerializer

    def perform_create(self, serializer):
        clinic = self.get_clinic_or_404()
        # Auto-increment visit number for patient
        last_rx = Prescription.objects.filter(
            clinic=clinic, patient=serializer.validated_data["patient"]
        ).order_by("-visit_number").first()
        visit_number = (last_rx.visit_number + 1) if last_rx else 1

        serializer.save(
            clinic=clinic,
            doctor=self.request.user,
            visit_number=visit_number,
        )

    @action(detail=True, methods=["get"], url_path="pdf")
    def download_pdf(self, request, pk=None):
        """
        GET /api/v1/prescriptions/{id}/pdf/
        Generates a professional PDF prescription using WeasyPrint.
        """
        prescription = self.get_object()
        clinic = request.clinic

        # Get clinic settings for PDF header/footer
        try:
            clinic_settings = clinic.settings
        except Exception:
            clinic_settings = None

        # Render HTML template
        html_content = render_to_string(
            "prescriptions/prescription_pdf.html",
            {
                "prescription": prescription,
                "patient": prescription.patient,
                "doctor": prescription.doctor,
                "clinic": clinic,
                "clinic_settings": clinic_settings,
                "remedies": prescription.remedies.all().select_related("remedy"),
            },
        )

        # Generate PDF
        try:
            from weasyprint import HTML, CSS
            pdf_file = io.BytesIO()
            HTML(string=html_content).write_pdf(
                pdf_file,
                stylesheets=[CSS(string=self._get_pdf_css())],
            )
            pdf_file.seek(0)

            # Log the download
            self.log_action(
                action="prescription_pdf",
                resource_type="Prescription",
                resource_id=str(prescription.id),
                description=f"PDF downloaded for Rx-{prescription.id}",
            )

            filename = f"prescription_{prescription.patient.patient_code}_{prescription.visit_date}.pdf"
            response = HttpResponse(pdf_file.read(), content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response

        except Exception as e:
            logger.error("pdf_generation_failed", error=str(e), prescription_id=str(prescription.id))
            return Response(
                {"error": "PDF generation failed.", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"], url_path="remedies")
    def add_remedy(self, request, pk=None):
        """POST /api/v1/prescriptions/{id}/remedies/"""
        prescription = self.get_object()

        # Only the prescribing doctor or clinic admin can add remedies
        from utils.permissions import PrescriptionPermission
        if not (
            request.user.role in ["super_admin", "clinic_admin"]
            or prescription.doctor == request.user
        ):
            return Response({"error": "Only the prescribing doctor can add remedies."}, status=403)

        serializer = PrescriptionRemedySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        remedy_line = serializer.save(prescription=prescription)
        return Response(
            PrescriptionRemedySerializer(remedy_line).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"remedies/(?P<remedy_id>[0-9a-f-]+)",
    )
    def remove_remedy(self, request, pk=None, remedy_id=None):
        """DELETE /api/v1/prescriptions/{id}/remedies/{remedy_id}/"""
        prescription = self.get_object()
        try:
            remedy_line = PrescriptionRemedy.objects.get(
                id=remedy_id, prescription=prescription
            )
            remedy_line.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except PrescriptionRemedy.DoesNotExist:
            return Response({"error": "Remedy not found."}, status=status.HTTP_404_NOT_FOUND)

    def _get_pdf_css(self):
        return """
            @page {
                size: A4;
                margin: 2cm 2cm 3cm 2cm;
                @bottom-center {
                    content: "Page " counter(page) " of " counter(pages);
                    font-size: 8pt;
                    color: #666;
                }
            }
            body { font-family: 'DejaVu Sans', sans-serif; font-size: 10pt; color: #333; }
            .header { border-bottom: 2px solid #2D6A4F; padding-bottom: 10px; margin-bottom: 15px; }
            .clinic-name { font-size: 18pt; color: #2D6A4F; font-weight: bold; }
            .section-title { background: #f0f7f4; padding: 5px 10px; font-weight: bold; color: #2D6A4F; margin: 10px 0 5px 0; }
            .patient-info { display: grid; grid-template-columns: 1fr 1fr; gap: 5px; }
            .remedy-table { width: 100%; border-collapse: collapse; margin-top: 10px; }
            .remedy-table th { background: #2D6A4F; color: white; padding: 6px 8px; text-align: left; font-size: 9pt; }
            .remedy-table td { padding: 5px 8px; border-bottom: 1px solid #e0e0e0; font-size: 9pt; }
            .remedy-table tr:nth-child(even) { background: #f9f9f9; }
            .signature-line { border-top: 1px solid #333; margin-top: 40px; padding-top: 5px; text-align: right; width: 200px; float: right; }
            .footer { border-top: 1px solid #ccc; padding-top: 8px; margin-top: 20px; font-size: 8pt; color: #666; }
        """


class RemedyViewSet(TenantMixin, ModelViewSet):
    """
    Master remedy list — global + clinic-specific.
    GET /api/v1/prescriptions/remedies/
    """

    queryset = Remedy.objects.filter(is_active=True)
    serializer_class = RemedySerializer
    permission_classes = [IsAuthenticated, IsClinicMember]
    filter_backends = [filters.SearchFilter]
    search_fields = ["name", "abbreviation", "full_name"]

    def get_queryset(self):
        """Return global remedies + clinic-specific remedies."""
        from django.db.models import Q
        clinic = getattr(self.request, "clinic", None)
        qs = Remedy.objects.filter(is_active=True)
        if clinic:
            return qs.filter(Q(clinic__isnull=True) | Q(clinic=clinic))
        return qs.filter(clinic__isnull=True)  # Only global for super admin
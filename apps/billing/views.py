import structlog
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.billing.models import (
    Invoice, Payment, SubscriptionPlanDetail, ClinicSubscription
)
from apps.billing.serializers import (
    InvoiceSerializer, PaymentSerializer, 
    SubscriptionPlanDetailSerializer, ClinicSubscriptionSerializer
)
from utils.mixins import TenantMixin, AuditMixin
from utils.permissions import IsClinicMember, IsReceptionistOrAbove, IsClinicAdminOrAbove

logger = structlog.get_logger(__name__)

class InvoiceViewSet(TenantMixin, AuditMixin, viewsets.ModelViewSet):
    """
    Manage clinic invoices.
    """
    queryset = Invoice.objects.select_related("patient", "doctor", "appointment").prefetch_related("line_items", "payments")
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated, IsClinicMember, IsReceptionistOrAbove]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "patient", "doctor", "invoice_date"]
    search_fields = ["invoice_number", "patient__first_name", "patient__last_name"]
    ordering_fields = ["invoice_date", "total_amount", "created_at"]
    ordering = ["-invoice_date"]

    def perform_create(self, serializer):
        serializer.save(
            clinic=self.request.clinic,
            created_by=self.request.user
        )

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def pay(self, request, pk=None):
        """Record a payment against this invoice."""
        invoice = self.get_object()
        serializer = PaymentSerializer(data=request.data)
        if serializer.is_valid():
            payment = serializer.save(
                clinic=request.clinic,
                invoice=invoice,
                patient=invoice.patient,
                received_by=request.user
            )
            
            # Update invoice paid amount
            invoice.paid_amount += payment.amount
            if invoice.paid_amount >= invoice.total_amount:
                invoice.status = "paid"
            elif invoice.paid_amount > 0:
                invoice.status = "partial"
            invoice.save()
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PaymentViewSet(TenantMixin, AuditMixin, viewsets.ReadOnlyModelViewSet):
    """
    View payment history.
    """
    queryset = Payment.objects.select_related("invoice", "patient", "received_by")
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated, IsClinicMember, IsReceptionistOrAbove]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["payment_method", "patient", "invoice"]
    ordering_fields = ["payment_date", "amount", "created_at"]
    ordering = ["-payment_date"]

class SubscriptionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    View subscription plans and clinic subscription status.
    """
    queryset = SubscriptionPlanDetail.objects.filter(is_active=True)
    serializer_class = SubscriptionPlanDetailSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def my_subscription(self, request):
        if not hasattr(request, "clinic") or not request.clinic:
            return Response({"error": "No clinic context found."}, status=status.HTTP_400_BAD_REQUEST)
        
        subscription = ClinicSubscription.objects.filter(
            clinic=request.clinic, is_active=True
        ).order_by("-created_at").first()
        
        if not subscription:
            return Response({"message": "No active subscription found."})
            
        return Response(ClinicSubscriptionSerializer(subscription).data)

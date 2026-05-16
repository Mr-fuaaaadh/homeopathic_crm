from rest_framework import serializers
from apps.billing.models import (
    Invoice, InvoiceLineItem, Payment, 
    SubscriptionPlanDetail, ClinicSubscription
)
from apps.patients.serializers import PatientListSerializer
from apps.accounts.serializers import UserListSerializer

class InvoiceLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLineItem
        fields = [
            "id", "description", "category", "quantity", 
            "unit_price", "total_price"
        ]
        read_only_fields = ["id", "total_price"]

    def validate(self, data):
        data["total_price"] = data["quantity"] * data["unit_price"]
        return data

class InvoiceSerializer(serializers.ModelSerializer):
    line_items = InvoiceLineItemSerializer(many=True)
    patient_name = serializers.ReadOnlyField(source="patient.full_name")
    doctor_name = serializers.ReadOnlyField(source="doctor.full_name")
    balance_due = serializers.ReadOnlyField()

    class Meta:
        model = Invoice
        fields = [
            "id", "invoice_number", "patient", "patient_name", 
            "appointment", "doctor", "doctor_name", "invoice_date", 
            "due_date", "subtotal", "discount_percent", "discount_amount",
            "tax_percent", "tax_amount", "total_amount", "paid_amount",
            "balance_due", "status", "notes", "terms_conditions",
            "line_items", "created_at"
        ]
        read_only_fields = ["id", "invoice_number", "paid_amount", "balance_due", "created_at"]

    def create(self, validated_data):
        line_items_data = validated_data.pop("line_items")
        invoice = Invoice.objects.create(**validated_data)
        for item_data in line_items_data:
            InvoiceLineItem.objects.create(invoice=invoice, **item_data)
        return invoice

class PaymentSerializer(serializers.ModelSerializer):
    patient_name = serializers.ReadOnlyField(source="patient.full_name")
    received_by_name = serializers.ReadOnlyField(source="received_by.full_name")

    class Meta:
        model = Payment
        fields = [
            "id", "invoice", "patient", "patient_name", "amount",
            "payment_method", "payment_date", "transaction_id",
            "reference_number", "notes", "received_by", "received_by_name",
            "created_at"
        ]
        read_only_fields = ["id", "created_at"]

class SubscriptionPlanDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlanDetail
        fields = "__all__"

class ClinicSubscriptionSerializer(serializers.ModelSerializer):
    plan_name = serializers.ReadOnlyField(source="plan.name")

    class Meta:
        model = ClinicSubscription
        fields = "__all__"
        read_only_fields = ["id", "created_at"]

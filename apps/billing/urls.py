from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.billing.views import InvoiceViewSet, PaymentViewSet, SubscriptionViewSet

app_name = "billing"

router = DefaultRouter()
router.register("invoices", InvoiceViewSet, basename="invoice")
router.register("payments", PaymentViewSet, basename="payment")
router.register("subscriptions", SubscriptionViewSet, basename="subscription")

urlpatterns = [
    path("", include(router.urls)),
]
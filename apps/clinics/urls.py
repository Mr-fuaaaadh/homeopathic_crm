from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.clinics.views import ClinicViewSet

app_name = "clinics"

router = DefaultRouter()
router.register(r"", ClinicViewSet, basename="clinic")

urlpatterns = [
    path("", include(router.urls)),
]
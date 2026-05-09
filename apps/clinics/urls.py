from django.urls import path
from django.urls import include

app_name = "clinics"

urlpatterns = [
    path("", include("apps.clinics.views.ClinicViewSet", basename="clinic")),
]
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AppointmentViewSet

app_name = "appointments"

router = DefaultRouter()
router.register("", AppointmentViewSet, basename="appointment")

urlpatterns = [
    path("", include(router.urls)),
]
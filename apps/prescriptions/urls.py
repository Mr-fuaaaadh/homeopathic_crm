from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PrescriptionViewSet, RemedyViewSet

app_name = "prescriptions"

router = DefaultRouter()
router.register("remedies", RemedyViewSet, basename="remedy")
router.register("", PrescriptionViewSet, basename="prescription")

urlpatterns = [
    path("", include(router.urls)),
]
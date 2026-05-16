from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.staff.views import StaffViewSet

app_name = "staff"

router = DefaultRouter()
router.register("", StaffViewSet, basename="staff")

urlpatterns = [
    path("", include(router.urls)),
 ]
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.activity_logs.views import ActivityLogViewSet

app_name = "activity_logs"

router = DefaultRouter()
router.register("", ActivityLogViewSet, basename="activity_log")

urlpatterns = [
    path("", include(router.urls)),
]
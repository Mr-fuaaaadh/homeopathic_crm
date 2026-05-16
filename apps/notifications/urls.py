from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.notifications.views import (
    NotificationViewSet, NotificationTemplateViewSet, NotificationLogViewSet
)

app_name = "notifications"

router = DefaultRouter()
router.register("templates", NotificationTemplateViewSet, basename="template")
router.register("logs", NotificationLogViewSet, basename="log")
router.register("", NotificationViewSet, basename="notification")

urlpatterns = [
    path("", include(router.urls)),
]
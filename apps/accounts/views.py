"""
apps/accounts/views.py
Authentication views: register, login, logout, profile, password management.
"""

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.accounts.models import LoginSession, PasswordResetToken, User
from apps.accounts.serializers import (
    ChangePasswordSerializer,
    CustomTokenObtainPairSerializer,
    UserProfileSerializer,
    UserRegistrationSerializer,
)
from apps.activity_logs.models import ActivityAction, ActivityLog
import structlog

logger = structlog.get_logger(__name__)


class LoginView(TokenObtainPairView):
    """
    POST /api/v1/auth/login/
    Returns access + refresh tokens with clinic context.
    """
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]
    throttle_scope = "auth"


class RegisterView(APIView):
    """
    POST /api/v1/auth/register/
    Public registration (creates patient/staff accounts).
    Clinic admin/super admin creation requires elevated permissions.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            user = serializer.save()
            logger.info("user_registered", user_id=str(user.id), email=user.email)
            return Response(
                {
                    "message": "Account created successfully.",
                    "user": UserProfileSerializer(user).data,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    """
    POST /api/v1/auth/logout/
    Blacklists the refresh token and marks session as logged out.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"error": "Refresh token required."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            token = RefreshToken(refresh_token)
            jti = token.payload.get("jti")

            # Blacklist in SimpleJWT
            token.blacklist()

            # Mark session as logged out
            if jti:
                LoginSession.objects.filter(jti=jti).update(
                    is_active=False, logged_out_at=timezone.now()
                )

            # Audit log
            ActivityLog.objects.create(
                user=request.user,
                user_email=request.user.email,
                user_role=request.user.role,
                clinic=getattr(request, "clinic", None),
                action=ActivityAction.LOGOUT,
                resource_type="Auth",
                description=f"{request.user.full_name} logged out",
                ip_address=request.META.get("REMOTE_ADDR"),
            )

            return Response({"message": "Logged out successfully."})

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class MeView(APIView):
    """
    GET  /api/v1/auth/me/  — Get current user profile
    PATCH /api/v1/auth/me/ — Update profile
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserProfileSerializer(request.user).data)

    def patch(self, request):
        serializer = UserProfileSerializer(
            request.user, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):
    """POST /api/v1/auth/password/change/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data["new_password"])
            user.save()

            # Invalidate all existing sessions
            LoginSession.objects.filter(user=user, is_active=True).update(
                is_active=False, logged_out_at=timezone.now()
            )

            ActivityLog.objects.create(
                user=user,
                user_email=user.email,
                user_role=user.role,
                action=ActivityAction.PASSWORD_CHANGED,
                resource_type="Auth",
                description="Password changed",
            )

            return Response({"message": "Password changed. Please log in again."})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SessionListView(APIView):
    """
    GET /api/v1/auth/sessions/
    List active login sessions for the current user.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sessions = LoginSession.objects.filter(
            user=request.user, is_active=True
        ).values("id", "ip_address", "user_agent", "created_at", "clinic__name")
        return Response(list(sessions))

    def delete(self, request):
        """Revoke all other sessions (except current)."""
        current_jti = request.auth.payload.get("jti") if request.auth else None
        LoginSession.objects.filter(user=request.user, is_active=True).exclude(
            jti=current_jti
        ).update(is_active=False, logged_out_at=timezone.now())
        return Response({"message": "All other sessions revoked."})
"""
URL Configuration — Homeopathy Clinic Management System
All API routes registered here.
"""

from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenVerifyView

API_V1 = "api/v1/"

urlpatterns = [
    # ── Admin ──────────────────────────────────────────────────────────────────
    path("admin/", admin.site.urls),

    # ── Auth ───────────────────────────────────────────────────────────────────
    path(f"{API_V1}auth/", include("apps.accounts.urls", namespace="auth")),
    path(f"{API_V1}auth/token/verify/", TokenVerifyView.as_view(), name="token-verify"),

    # ── Clinics ────────────────────────────────────────────────────────────────
    path(f"{API_V1}clinics/", include("apps.clinics.urls", namespace="clinics")),

    # ── Patients ───────────────────────────────────────────────────────────────
    path(f"{API_V1}patients/", include("apps.patients.urls", namespace="patients")),

    # ── Appointments ───────────────────────────────────────────────────────────
    path(f"{API_V1}appointments/", include("apps.appointments.urls", namespace="appointments")),

    # ── Prescriptions ──────────────────────────────────────────────────────────
    path(f"{API_V1}prescriptions/", include("apps.prescriptions.urls", namespace="prescriptions")),

    # ── Staff ──────────────────────────────────────────────────────────────────
    path(f"{API_V1}staff/", include("apps.staff.urls", namespace="staff")),

    # ── Billing ────────────────────────────────────────────────────────────────
    path(f"{API_V1}billing/", include("apps.billing.urls", namespace="billing")),

    # ── Notifications ──────────────────────────────────────────────────────────
    path(f"{API_V1}notifications/", include("apps.notifications.urls", namespace="notifications")),

    # ── Activity Logs ──────────────────────────────────────────────────────────
    path(f"{API_V1}activity-logs/", include("apps.activity_logs.urls", namespace="activity_logs")),

    # ── Profiling (dev only) ───────────────────────────────────────────────────
    *([path("silk/", include("silk.urls", namespace="silk"))] if settings.DEBUG else []),
]

# Static & Media
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)


# ─────────────────────────────────────────────────────────────────────────────
# FULL API ROUTE REFERENCE
# ─────────────────────────────────────────────────────────────────────────────
#
# AUTH
#   POST   /api/v1/auth/register/                  Register new user
#   POST   /api/v1/auth/login/                     Obtain JWT tokens
#   POST   /api/v1/auth/logout/                    Blacklist refresh token
#   POST   /api/v1/auth/token/refresh/             Refresh access token
#   POST   /api/v1/auth/token/verify/              Verify token validity
#   POST   /api/v1/auth/password/change/           Change password
#   POST   /api/v1/auth/password/reset/            Request password reset
#   POST   /api/v1/auth/password/reset/confirm/    Confirm password reset
#   GET    /api/v1/auth/me/                        Current user profile
#   PATCH  /api/v1/auth/me/                        Update current user profile
#
# CLINICS  (Super Admin only for create/delete)
#   GET    /api/v1/clinics/                        List all clinics [SuperAdmin]
#   POST   /api/v1/clinics/                        Create clinic [SuperAdmin]
#   GET    /api/v1/clinics/{id}/                   Get clinic details
#   PUT    /api/v1/clinics/{id}/                   Update clinic
#   DELETE /api/v1/clinics/{id}/                   Soft-delete clinic
#   GET    /api/v1/clinics/{id}/stats/             Clinic statistics
#   POST   /api/v1/clinics/{id}/subscription/      Update subscription
#
# PATIENTS  (Scoped to clinic_id)
#   GET    /api/v1/patients/                       List patients (search/filter)
#   POST   /api/v1/patients/                       Register new patient
#   GET    /api/v1/patients/{id}/                  Patient detail
#   PUT    /api/v1/patients/{id}/                  Update patient
#   DELETE /api/v1/patients/{id}/                  Soft-delete patient
#   GET    /api/v1/patients/{id}/history/          Visit history timeline
#   GET    /api/v1/patients/{id}/attachments/      List attachments
#   POST   /api/v1/patients/{id}/attachments/      Upload attachment
#   DELETE /api/v1/patients/{id}/attachments/{fid}/Remove attachment
#
# APPOINTMENTS
#   GET    /api/v1/appointments/                   List (filter by date/doctor/status)
#   POST   /api/v1/appointments/                   Book appointment
#   GET    /api/v1/appointments/{id}/              Appointment detail
#   PUT    /api/v1/appointments/{id}/              Update appointment
#   POST   /api/v1/appointments/{id}/reschedule/   Reschedule
#   POST   /api/v1/appointments/{id}/cancel/       Cancel
#   POST   /api/v1/appointments/{id}/complete/     Mark complete
#   GET    /api/v1/appointments/queue/             Today's queue
#   POST   /api/v1/appointments/queue/next/        Call next patient
#   GET    /api/v1/appointments/slots/             Available slots by doctor/date
#
# PRESCRIPTIONS
#   GET    /api/v1/prescriptions/                  List prescriptions
#   POST   /api/v1/prescriptions/                  Create prescription
#   GET    /api/v1/prescriptions/{id}/             Prescription detail
#   PUT    /api/v1/prescriptions/{id}/             Update prescription
#   GET    /api/v1/prescriptions/{id}/pdf/         Download PDF
#   POST   /api/v1/prescriptions/{id}/remedies/    Add remedy
#   DELETE /api/v1/prescriptions/{id}/remedies/{rid}/ Remove remedy
#   GET    /api/v1/prescriptions/remedies/         Master remedy list
#
# STAFF
#   GET    /api/v1/staff/                          List staff
#   POST   /api/v1/staff/invite/                   Invite new staff member
#   GET    /api/v1/staff/{id}/                     Staff detail
#   PATCH  /api/v1/staff/{id}/update-role/         Update staff role/status
#   GET    /api/v1/staff/doctors/                  List all doctors
#
# BILLING
#   GET    /api/v1/billing/invoices/               List invoices
#   POST   /api/v1/billing/invoices/               Create invoice
#   GET    /api/v1/billing/invoices/{id}/          Invoice detail
#   POST   /api/v1/billing/invoices/{id}/pay/      Record payment
#   GET    /api/v1/billing/payments/               Payment history
#   GET    /api/v1/billing/subscriptions/          Available plans
#   GET    /api/v1/billing/subscriptions/my_subscription/ Current subscription status
#
# NOTIFICATIONS
#   GET    /api/v1/notifications/                  User notifications
#   POST   /api/v1/notifications/read-all/         Mark all as read
#   POST   /api/v1/notifications/{id}/read/        Mark specific as read
#   GET    /api/v1/notifications/templates/        Message templates
#   GET    /api/v1/notifications/logs/             Notification logs
#
# ACTIVITY LOGS
#   GET    /api/v1/activity-logs/                  List audit logs (Clinic Admin only)
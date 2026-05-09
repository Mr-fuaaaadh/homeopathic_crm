"""
apps/appointments/filters.py
FilterSet for appointment listing endpoints.
"""

import django_filters
from django.db.models import Q
from django.utils import timezone

from apps.appointments.models import Appointment, AppointmentStatus


class AppointmentFilter(django_filters.FilterSet):
    # Direct filters
    doctor_id = django_filters.UUIDFilter(field_name="doctor_id")
    patient_id = django_filters.UUIDFilter(field_name="patient_id")
    status = django_filters.CharFilter(field_name="status")
    appointment_type = django_filters.CharFilter(field_name="appointment_type")

    # Date filters
    appointment_date = django_filters.DateFilter(field_name="appointment_date")
    appointment_date_from = django_filters.DateFilter(
        field_name="appointment_date", lookup_expr="gte"
    )
    appointment_date_to = django_filters.DateFilter(
        field_name="appointment_date", lookup_expr="lte"
    )

    # Time filters
    appointment_time_from = django_filters.TimeFilter(
        field_name="appointment_time", lookup_expr="gte"
    )
    appointment_time_to = django_filters.TimeFilter(
        field_name="appointment_time", lookup_expr="lte"
    )

    # Queue/token filters
    token_from = django_filters.NumberFilter(field_name="token_number", lookup_expr="gte")
    token_to = django_filters.NumberFilter(field_name="token_number", lookup_expr="lte")

    # Convenience flags
    today = django_filters.BooleanFilter(method="filter_today")
    upcoming = django_filters.BooleanFilter(method="filter_upcoming")
    active_queue = django_filters.BooleanFilter(method="filter_active_queue")

    # Optional single search param across patient name/phone
    q = django_filters.CharFilter(method="filter_q")

    class Meta:
        model = Appointment
        fields = [
            "doctor_id",
            "patient_id",
            "status",
            "appointment_type",
            "appointment_date",
        ]

    def filter_today(self, queryset, name, value):
        if value is True:
            return queryset.filter(appointment_date=timezone.localdate())
        return queryset

    def filter_upcoming(self, queryset, name, value):
        if value is True:
            return queryset.filter(appointment_date__gte=timezone.localdate())
        return queryset

    def filter_active_queue(self, queryset, name, value):
        if value is True:
            return queryset.filter(
                status__in=[
                    AppointmentStatus.SCHEDULED,
                    AppointmentStatus.CONFIRMED,
                    AppointmentStatus.CHECKED_IN,
                    AppointmentStatus.IN_PROGRESS,
                ]
            )
        return queryset

    def filter_q(self, queryset, name, value):
        if not value:
            return queryset
        term = value.strip()
        return queryset.filter(
            Q(patient__first_name__icontains=term)
            | Q(patient__last_name__icontains=term)
            | Q(patient__phone__icontains=term)
            | Q(patient__patient_code__icontains=term)
        )
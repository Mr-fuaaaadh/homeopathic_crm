"""
apps/appointments/serializers.py
Serializers for appointment booking, queue, scheduling, and slot APIs.
"""

from datetime import date, datetime, timedelta

from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import User, UserRole
from apps.appointments.models import (
    Appointment,
    AppointmentQueue,
    AppointmentStatus,
    DoctorSchedule,
    DoctorLeave,
)
from apps.patients.models import Patient


class AppointmentListSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source="patient.full_name", read_only=True)
    patient_code = serializers.CharField(source="patient.patient_code", read_only=True)
    patient_phone = serializers.CharField(source="patient.phone", read_only=True)
    doctor_name = serializers.CharField(source="doctor.full_name", read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "appointment_date",
            "appointment_time",
            "appointment_type",
            "status",
            "token_number",
            "queue_position",
            "patient",
            "patient_name",
            "patient_code",
            "patient_phone",
            "doctor",
            "doctor_name",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "token_number", "queue_position"]


class AppointmentDetailSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source="patient.full_name", read_only=True)
    patient_code = serializers.CharField(source="patient.patient_code", read_only=True)
    patient_phone = serializers.CharField(source="patient.phone", read_only=True)

    doctor_name = serializers.CharField(source="doctor.full_name", read_only=True)
    doctor_specialization = serializers.CharField(source="doctor.specialization", read_only=True)

    booked_by_name = serializers.CharField(source="booked_by.full_name", read_only=True)
    cancelled_by_name = serializers.CharField(source="cancelled_by.full_name", read_only=True)

    actual_duration_minutes = serializers.ReadOnlyField()

    class Meta:
        model = Appointment
        fields = [
            "id",
            "clinic",
            "patient",
            "patient_name",
            "patient_code",
            "patient_phone",
            "doctor",
            "doctor_name",
            "doctor_specialization",
            "appointment_date",
            "appointment_time",
            "end_time",
            "duration_minutes",
            "appointment_type",
            "token_number",
            "queue_position",
            "status",
            "chief_complaint",
            "notes",
            "booked_by",
            "booked_by_name",
            "checked_in_at",
            "consultation_started_at",
            "consultation_ended_at",
            "actual_duration_minutes",
            "cancelled_by",
            "cancelled_by_name",
            "cancellation_reason",
            "cancelled_at",
            "rescheduled_from",
            "reminder_24h_sent",
            "reminder_2h_sent",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "clinic",
            "token_number",
            "queue_position",
            "booked_by",
            "checked_in_at",
            "consultation_started_at",
            "consultation_ended_at",
            "actual_duration_minutes",
            "cancelled_by",
            "cancelled_at",
            "reminder_24h_sent",
            "reminder_2h_sent",
            "created_at",
            "updated_at",
        ]


class AppointmentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = [
            "patient",
            "doctor",
            "appointment_date",
            "appointment_time",
            "duration_minutes",
            "appointment_type",
            "chief_complaint",
            "notes",
        ]

    def validate_patient(self, patient):
        clinic = self.context.get("clinic")
        if clinic and patient.clinic_id != clinic.id:
            raise serializers.ValidationError("Patient does not belong to the active clinic.")
        return patient

    def validate_doctor(self, doctor):
        clinic = self.context.get("clinic")
        if doctor.role not in [UserRole.DOCTOR, UserRole.CLINIC_ADMIN]:
            raise serializers.ValidationError("Selected user is not a valid consulting doctor.")
        if clinic:
            has_access = doctor.clinic_profiles.filter(clinic=clinic, is_active=True).exists()
            if not has_access:
                raise serializers.ValidationError("Doctor is not assigned to the active clinic.")
        return doctor

    def validate(self, attrs):
        appointment_date = attrs.get("appointment_date")
        appointment_time = attrs.get("appointment_time")
        doctor = attrs.get("doctor")
        clinic = self.context.get("clinic")

        if appointment_date and appointment_date < timezone.localdate():
            raise serializers.ValidationError({"appointment_date": "Appointment date cannot be in the past."})

        if appointment_date == timezone.localdate() and appointment_time:
            now_time = timezone.localtime().time()
            if appointment_time <= now_time:
                raise serializers.ValidationError({"appointment_time": "Appointment time must be in the future."})

        if appointment_date and appointment_time and doctor and clinic:
            duplicate_exists = Appointment.objects.filter(
                clinic=clinic,
                doctor=doctor,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                status__in=[
                    AppointmentStatus.SCHEDULED,
                    AppointmentStatus.CONFIRMED,
                    AppointmentStatus.CHECKED_IN,
                    AppointmentStatus.IN_PROGRESS,
                ],
            ).exists()
            if duplicate_exists:
                raise serializers.ValidationError(
                    {"appointment_time": "This slot is already booked for the doctor."}
                )

            on_leave = DoctorLeave.objects.filter(
                clinic=clinic,
                doctor=doctor,
                leave_date=appointment_date,
            ).exists()
            if on_leave:
                raise serializers.ValidationError(
                    {"appointment_date": "Doctor is on leave for the selected date."}
                )

        return attrs


class AppointmentRescheduleSerializer(serializers.Serializer):
    new_date = serializers.DateField()
    new_time = serializers.TimeField()
    doctor = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role__in=[UserRole.DOCTOR, UserRole.CLINIC_ADMIN]),
        required=False,
        allow_null=True,
    )
    reason = serializers.CharField(required=False, allow_blank=True, max_length=300)

    def validate_new_date(self, value):
        if value < timezone.localdate():
            raise serializers.ValidationError("Reschedule date cannot be in the past.")
        return value

    def validate(self, attrs):
        new_date = attrs.get("new_date")
        new_time = attrs.get("new_time")

        if new_date == timezone.localdate() and new_time <= timezone.localtime().time():
            raise serializers.ValidationError({"new_time": "Reschedule time must be in the future."})

        return attrs


class AppointmentQueueSerializer(serializers.ModelSerializer):
    doctor_name = serializers.CharField(source="doctor.full_name", read_only=True)

    class Meta:
        model = AppointmentQueue
        fields = [
            "id",
            "doctor",
            "doctor_name",
            "queue_date",
            "current_token",
            "total_tokens",
            "average_wait_minutes",
            "is_accepting",
            "queue_started_at",
            "queue_paused_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class DoctorScheduleSerializer(serializers.ModelSerializer):
    doctor_name = serializers.CharField(source="doctor.full_name", read_only=True)
    day_name = serializers.SerializerMethodField()

    class Meta:
        model = DoctorSchedule
        fields = [
            "id",
            "clinic",
            "doctor",
            "doctor_name",
            "day_of_week",
            "day_name",
            "start_time",
            "end_time",
            "slot_duration_minutes",
            "max_patients_per_slot",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "clinic", "created_at", "updated_at"]

    def get_day_name(self, obj):
        day_map = {
            0: "Monday",
            1: "Tuesday",
            2: "Wednesday",
            3: "Thursday",
            4: "Friday",
            5: "Saturday",
            6: "Sunday",
        }
        return day_map.get(obj.day_of_week, "")

    def validate(self, attrs):
        start = attrs.get("start_time")
        end = attrs.get("end_time")
        slot_minutes = attrs.get("slot_duration_minutes")

        if start and end and start >= end:
            raise serializers.ValidationError({"end_time": "End time must be after start time."})

        if slot_minutes and (slot_minutes < 5 or slot_minutes > 240):
            raise serializers.ValidationError(
                {"slot_duration_minutes": "Slot duration must be between 5 and 240 minutes."}
            )

        return attrs


class AvailableSlotsSerializer(serializers.Serializer):
    date = serializers.DateField()
    doctor_id = serializers.UUIDField()
    slots = serializers.ListField(child=serializers.DictField(), read_only=True)
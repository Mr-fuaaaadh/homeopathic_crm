"""
apps/core/models.py
Abstract base models shared across the entire system.
Every tenant-scoped model inherits from TenantModel.
"""

import uuid

from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """Adds created_at / updated_at to every model."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class SoftDeleteManager(models.Manager):
    """Default manager hides soft-deleted records."""

    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class AllObjectsManager(models.Manager):
    """Includes soft-deleted records — for admin/audit use only."""

    def get_queryset(self):
        return super().get_queryset()


class SoftDeleteModel(models.Model):
    """
    Provides soft-delete capability.
    Call instance.delete() to soft-delete;
    call instance.hard_delete() to permanently remove.
    """

    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    deleted_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True

    def delete(self, deleted_by=None, *args, **kwargs):
        self.deleted_at = timezone.now()
        self.deleted_by = deleted_by
        self.save(update_fields=["deleted_at", "deleted_by"])

    def hard_delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)

    def restore(self):
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=["deleted_at", "deleted_by"])

    @property
    def is_deleted(self):
        return self.deleted_at is not None


class UUIDModel(models.Model):
    """Uses UUID as primary key for security and distributed systems."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TenantModel(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """
    BASE CLASS for every tenant-scoped model.

    Enforces:
    - UUID PK
    - clinic_id FK (the tenant discriminator)
    - Timestamps
    - Soft delete

    Usage:
        class Patient(TenantModel):
            name = models.CharField(...)
            # clinic_id is auto-included
    """

    clinic = models.ForeignKey(
        "clinics.Clinic",
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)s_set",
        db_index=True,
    )

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["clinic", "created_at"]),
            models.Index(fields=["clinic", "deleted_at"]),
        ]
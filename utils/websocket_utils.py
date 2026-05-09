"""
utils/websocket_utils.py
Helpers to broadcast real-time queue updates over Django Channels.
"""

import structlog
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = structlog.get_logger(__name__)


def queue_group_name(clinic_id: str, doctor_id: str, queue_date: str) -> str:
    """
    Build a deterministic channel group name for queue updates.

    Example:
        queue.c_<clinic_uuid>.d_<doctor_uuid>.dt_2026_05_09
    """
    safe_date = str(queue_date).replace("-", "_")
    return f"queue.c_{clinic_id}.d_{doctor_id}.dt_{safe_date}"


def broadcast_queue_update(clinic_id: str, doctor_id: str, queue_date: str, payload: dict | None = None) -> bool:
    """
    Broadcast a queue update event to all websocket subscribers.

    Returns:
        bool: True if publish attempted, False if channel layer missing or failed.
    """
    channel_layer = get_channel_layer()
    if channel_layer is None:
        logger.warning(
            "queue_broadcast_skipped_no_channel_layer",
            clinic_id=clinic_id,
            doctor_id=doctor_id,
            queue_date=queue_date,
        )
        return False

    group = queue_group_name(clinic_id=clinic_id, doctor_id=doctor_id, queue_date=queue_date)
    event_payload = payload or {}

    event = {
        "type": "queue.update",  # handled by consumer method queue_update(...)
        "event": "QUEUE_UPDATED",
        "clinic_id": str(clinic_id),
        "doctor_id": str(doctor_id),
        "date": str(queue_date),
        "payload": event_payload,
    }

    try:
        async_to_sync(channel_layer.group_send)(group, event)
        logger.info(
            "queue_broadcast_sent",
            group=group,
            clinic_id=clinic_id,
            doctor_id=doctor_id,
            queue_date=queue_date,
        )
        return True
    except Exception as exc:
        logger.error(
            "queue_broadcast_failed",
            group=group,
            clinic_id=clinic_id,
            doctor_id=doctor_id,
            queue_date=queue_date,
            error=str(exc),
        )
        return False
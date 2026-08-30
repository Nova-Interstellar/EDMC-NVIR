"""
Builds the normalised event that every transport carries.

This shape is the seam between the plugin and nova-web: the Discord transport
renders it locally today, and the API transport will hand exactly the same
object to the site later. Keeping the two identical is what makes switching a
one-line change.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from . import events
from .config import PLUGIN_VERSION


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build(
    cmdr: str,
    event_name: str,
    entry: dict,
    system: Optional[str] = None,
    station: Optional[str] = None,
    test: bool = False,
) -> Optional[dict]:
    """
    Normalise a raw journal entry into the payload the transports send.

    Returns None when the event is not registered, or when its extractor
    decides this particular occurrence is not worth broadcasting.
    """
    spec = events.spec_for(event_name)
    if spec is None:
        return None

    data = spec.extract(entry)
    if data is None:
        return None

    amount = data.get(spec.amount_field) if spec.amount_field else None

    return {
        "v": 1,
        "plugin": PLUGIN_VERSION,
        "cmdr": cmdr,
        "event": event_name,
        "category": spec.category,
        "at": entry.get("timestamp") or utc_now(),
        # Lets the receiver drop a duplicate if a retry lands twice.
        "nonce": uuid.uuid4().hex,
        "system": system or entry.get("StarSystem") or "",
        "station": station or "",
        "amount": amount,
        "data": data,
        "test": bool(test),
    }

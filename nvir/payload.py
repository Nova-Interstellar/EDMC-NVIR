"""
Builds the normalised events the transport carries.

One journal entry can produce several payloads — a Promotion carrying two
careers becomes two, each with its own nonce so it routes and retries alone.
This shape is the seam between the plugin and nova-web.

No payload carries a credit amount: nothing here is a market sale, so there is
nothing to measure against a threshold.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

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
) -> List[dict]:
    """
    Normalise a raw journal entry into zero or more payloads.

    Returns an empty list when the event is not registered, when its extractor
    declines the occurrence, or when a produced item maps to no channel — a
    Federation rank-up, say, which the squadron does not carry.
    """
    spec = events.spec_for(event_name)
    if spec is None:
        return []

    extracted = spec.extract(entry)
    if not extracted:
        return []

    stamped = entry.get("timestamp") or utc_now()
    built = []

    for data in extracted:
        category = spec.category_for(data)
        if category is None:
            continue

        built.append({
            "v": 1,
            "plugin": PLUGIN_VERSION,
            "cmdr": cmdr,
            "event": event_name,
            # The channel this belongs to. The API re-derives it rather than
            # trusting us; this travels for logging and the debug panel.
            "category": category,
            "at": stamped,
            # Lets the receiver drop a duplicate if a retry lands twice.
            "nonce": uuid.uuid4().hex,
            "system": system or entry.get("StarSystem") or "",
            "station": station or "",
            "data": data,
            "test": bool(test),
        })

    return built

"""
Journal handling: decide whether an entry is worth broadcasting, then queue it.

Runs on EDMC's main thread, so it does no network work of its own.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from . import events, payload
from .config import REPLAY_GRACE_SECONDS
from .log import logger


class Journal:
    """Filters journal entries down to the ones the registry declares."""

    def __init__(self, settings, sender):
        self._settings = settings
        self._sender = sender
        # EDMC replays the current journal file when it loads, so anything
        # stamped before the plugin started is history, not news.
        self._started_at = datetime.now(timezone.utc) - timedelta(
            seconds=REPLAY_GRACE_SECONDS
        )
        self._owned_carriers = set()
        self._last_result = ""

    @property
    def last_result(self) -> str:
        return self._last_result

    def on_entry(
        self,
        cmdr: str,
        is_beta: bool,
        system: Optional[str],
        station: Optional[str],
        entry: dict,
        state: dict,
    ) -> None:
        if is_beta:
            return

        event_name = entry.get("event")
        if not event_name:
            return

        # Learn which carriers belong to this commander before the replay
        # guard runs: CarrierStats arrives during the login replay, and it is
        # what lets us tell an owned carrier's jump from one we are riding.
        if event_name in events.CARRIER_OWNERSHIP_EVENTS:
            carrier_id = entry.get("CarrierID")
            if carrier_id:
                self._owned_carriers.add(int(carrier_id))

        if self._is_replay(entry):
            return

        spec = events.spec_for(event_name)
        if spec is None:
            return

        if not self._settings.is_category_enabled(spec.category):
            return

        # CarrierJump fires for everyone docked aboard, so without this a
        # passenger would announce somebody else's carrier as their own.
        if event_name == "CarrierJump":
            market_id = entry.get("MarketID")
            if not market_id or int(market_id) not in self._owned_carriers:
                logger.debug("Ignoring CarrierJump for a carrier we do not own")
                return

        built = payload.build(cmdr, event_name, entry, system, station)
        if built is None:
            return

        logger.info("Queued %s for %s", event_name, cmdr)
        self._sender.submit(built, on_result=self._record)

    def _record(self, result) -> None:
        self._last_result = result.detail

    def _is_replay(self, entry: dict) -> bool:
        stamped = self._parse_timestamp(entry.get("timestamp"))
        if stamped is None:
            # An entry we cannot date is treated as live; the game writes a
            # timestamp on every line, so this should not happen.
            return False
        return stamped < self._started_at

    @staticmethod
    def _parse_timestamp(value) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.strptime(str(value), "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            return None

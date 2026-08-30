"""
Delivery queue.

EDMC calls journal_entry on its main thread, so nothing here may block: a
single rate-limited webhook post would otherwise freeze the whole application.
Events are queued and a daemon thread does the talking.
"""

import queue
import threading
from typing import Callable, Optional

from .config import MAX_ATTEMPTS
from .log import logger
from .transport import Delivery

# Pushed onto the queue to wake the worker for shutdown.
_SHUTDOWN = object()


class Sender:
    """Queues payloads and delivers them on a background thread."""

    def __init__(self, transport):
        self._transport = transport
        self._queue: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="NVIR-sender", daemon=True
        )
        self._thread.start()
        logger.info("Delivery thread started")

    def stop(self, timeout: float = 5.0) -> None:
        if self._thread is None:
            return
        self._stop.set()
        self._queue.put(_SHUTDOWN)
        self._thread.join(timeout=timeout)
        self._thread = None
        self._transport.close()
        logger.info("Delivery thread stopped")

    @property
    def transport(self):
        return self._transport

    def pending(self) -> int:
        return self._queue.qsize()

    def submit(
        self, payload: dict, on_result: Optional[Callable[[Delivery], None]] = None
    ) -> None:
        """
        Queue a payload for delivery.

        `on_result` is invoked on the worker thread, so a Tk caller must
        marshal back with `widget.after(...)` before touching any widget.
        """
        self._queue.put((payload, on_result))

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                item = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if item is _SHUTDOWN:
                break

            payload, on_result = item
            try:
                result = self._deliver(payload)
            except Exception as err:  # never let the worker die on one event
                logger.exception("Delivery raised")
                result = Delivery(False, detail=str(err))
            finally:
                self._queue.task_done()

            if on_result is not None:
                try:
                    on_result(result)
                except Exception:
                    logger.exception("Delivery callback raised")

    def _deliver(self, payload: dict) -> Delivery:
        event_name = payload.get("event", "?")
        result = Delivery(False, detail="Not attempted")

        for attempt in range(1, MAX_ATTEMPTS + 1):
            result = self._transport.send(payload)

            if result.ok:
                logger.info("Sent %s (attempt %d)", event_name, attempt)
                return result

            if not result.retryable or attempt == MAX_ATTEMPTS:
                break

            logger.warning(
                "Retrying %s in %.1fs (%s)", event_name, result.retry_after, result.detail
            )
            # Waiting on the stop event keeps shutdown responsive during a
            # rate-limit back-off.
            if self._stop.wait(result.retry_after):
                return result

        logger.error(
            "Dropped %s after %d attempts: %s", event_name, MAX_ATTEMPTS, result.detail
        )
        return result

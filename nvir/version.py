"""
Update check against the published plugin.

The version is read from `nvir/config.py` on the repository's default branch,
so a check works without cutting a release. The fetch happens on a background
thread and its result is cached for the session: the settings page renders
immediately from whatever is known and updates in place when the answer lands.
"""

import re
import threading
from dataclasses import dataclass
from typing import Callable, Optional

try:
    import requests  # type: ignore

    REQUESTS_AVAILABLE = True
except ImportError:  # pragma: no cover - EDMC ships requests
    REQUESTS_AVAILABLE = False

from .config import (
    PLUGIN_VERSION,
    USER_AGENT,
    VERSION_CHECK_TIMEOUT,
    VERSION_SOURCE_URL,
)
from .log import logger

_VERSION_PATTERN = re.compile(r'^PLUGIN_VERSION\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)

# States the settings page renders.
CHECKING = "checking"
CURRENT = "current"
OUTDATED = "outdated"
UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class VersionState:
    """What we know about the published version right now."""

    state: str
    installed: str = PLUGIN_VERSION
    latest: Optional[str] = None

    def label(self) -> str:
        if self.state == CHECKING:
            return "Checking\N{HORIZONTAL ELLIPSIS}"
        if self.state == OUTDATED:
            return "Update Available \N{EM DASH} v{0}".format(self.latest)
        if self.state == CURRENT:
            return "Up To Date \N{EM DASH} v{0}".format(self.installed)
        return "Version check unavailable"


def parse_version(text: str) -> tuple:
    """
    '0.4.0' -> (0, 4, 0), for ordering.

    Non-numeric parts sort as 0 rather than raising, so a tagged build like
    '0.4.0-rc1' still compares against release numbers instead of breaking the
    check outright.
    """
    parts = []
    for chunk in str(text).strip().lstrip("vV").split("."):
        digits = re.match(r"\d+", chunk)
        parts.append(int(digits.group()) if digits else 0)
    return tuple(parts)


def extract_version(source: str) -> Optional[str]:
    """Pull PLUGIN_VERSION out of a fetched config.py."""
    found = _VERSION_PATTERN.search(source)
    return found.group(1) if found else None


def _compare(latest: str) -> VersionState:
    if parse_version(latest) > parse_version(PLUGIN_VERSION):
        return VersionState(OUTDATED, PLUGIN_VERSION, latest)
    return VersionState(CURRENT, PLUGIN_VERSION, latest)


def fetch() -> VersionState:
    """Blocking check. Callers should use `Checker`, not this."""
    if not REQUESTS_AVAILABLE:
        return VersionState(UNAVAILABLE)

    try:
        response = requests.get(
            VERSION_SOURCE_URL,
            timeout=VERSION_CHECK_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
    except Exception as err:
        logger.info("Update check failed: %s", err)
        return VersionState(UNAVAILABLE)

    latest = extract_version(response.text)
    if not latest:
        logger.info("Update check could not find a version in the published config")
        return VersionState(UNAVAILABLE)

    return _compare(latest)


class Checker:
    """Runs the check once per session and remembers the answer."""

    def __init__(self):
        self._state = VersionState(CHECKING)
        self._lock = threading.Lock()
        self._running = False
        self._listeners = []

    @property
    def state(self) -> VersionState:
        with self._lock:
            return self._state

    def subscribe(self, callback: Callable[[VersionState], None]) -> None:
        """
        Register interest in the result.

        Fires immediately if the answer is already known; otherwise once the
        check finishes. Callbacks run on the checking thread, so a Tk caller
        must marshal back with `widget.after(...)`.
        """
        with self._lock:
            state = self._state
            if state.state == CHECKING:
                self._listeners.append(callback)
                callback_now = None
            else:
                callback_now = state

        if callback_now is not None:
            callback(callback_now)

    def start(self) -> None:
        """Kick the check off once. Repeat calls are ignored."""
        with self._lock:
            if self._running or self._state.state != CHECKING:
                return
            self._running = True

        threading.Thread(target=self._run, name="NVIR-version", daemon=True).start()

    def _run(self) -> None:
        result = fetch()

        with self._lock:
            self._state = result
            self._running = False
            listeners, self._listeners = self._listeners, []

        if result.state == OUTDATED:
            logger.info(
                "Update available: v%s installed, v%s published",
                result.installed,
                result.latest,
            )

        for callback in listeners:
            try:
                callback(result)
            except Exception:
                logger.exception("Version callback raised")

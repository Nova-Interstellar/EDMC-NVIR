"""
Per-commander preferences, stored in EDMC's config.

Only two things are a commander's choice: the squadron token, and what they are
willing to broadcast. Endpoints are squadron infrastructure and live in
`config.py` — except the localhost redirect, which is a development switch and
only exists while DEBUG is on.
"""

import tkinter as tk

from config import config  # type: ignore

from . import events
from .config import (
    DEBUG,
    DEFAULT_LOCALHOST_URL,
    KEY_API_TOKEN,
    KEY_CATEGORY,
    KEY_DEBUG_MODE,
    KEY_LOCALHOST_URL,
    KEY_STEALTH,
    KEY_USE_LOCALHOST,
    RETIRED_KEYS,
    squadron_url,
)
from .log import logger


class Settings:
    """Reads and writes what this commander chooses to broadcast."""

    def __init__(self):
        self.api_token = tk.StringVar()
        self.stealth = tk.BooleanVar()
        # One toggle per channel.
        self.categories = {key: tk.BooleanVar() for key in events.CATEGORIES}

        # Development only; ignored unless DEBUG is on in config.py.
        self.debug_mode = tk.BooleanVar()
        self.use_localhost = tk.BooleanVar()
        self.localhost_url = tk.StringVar()

        # Plain copies for the delivery thread. Tk variables may only be read
        # from the thread running the main loop, and the sender is not it.
        self.api_token_value = ""
        self.debug_mode_value = False
        self.use_localhost_value = False
        self.localhost_url_value = ""

        self.load()

    def load(self) -> None:
        self._drop_retired_keys()

        self.api_token.set(config.get_str(KEY_API_TOKEN, default=""))
        self.stealth.set(config.get_bool(KEY_STEALTH, default=False))

        for key, var in self.categories.items():
            var.set(config.get_bool(KEY_CATEGORY.format(key), default=True))

        self.debug_mode.set(config.get_bool(KEY_DEBUG_MODE, default=False))
        self.use_localhost.set(config.get_bool(KEY_USE_LOCALHOST, default=False))
        self.localhost_url.set(
            config.get_str(KEY_LOCALHOST_URL, default="") or DEFAULT_LOCALHOST_URL
        )

        self._snapshot()

    def save(self) -> None:
        config.set(KEY_API_TOKEN, self.api_token.get().strip())
        config.set(KEY_STEALTH, self.stealth.get())

        for key, var in self.categories.items():
            config.set(KEY_CATEGORY.format(key), var.get())

        config.set(KEY_DEBUG_MODE, self.debug_mode.get())
        config.set(KEY_USE_LOCALHOST, self.use_localhost.get())
        config.set(KEY_LOCALHOST_URL, self.localhost_url.get().strip())

        self._snapshot()
        logger.info("Preferences saved")

    def _drop_retired_keys(self) -> None:
        """Clear webhook URLs and endpoints left by an earlier build."""
        for key in RETIRED_KEYS:
            if config.get_str(key, default=""):
                config.delete(key)
                logger.info("Removed retired setting %s", key)

    def _snapshot(self) -> None:
        """Refresh the plain copies the delivery thread reads."""
        self.api_token_value = self.api_token.get().strip()
        self.debug_mode_value = bool(self.debug_mode.get())
        self.use_localhost_value = bool(self.use_localhost.get())
        self.localhost_url_value = self.localhost_url.get().strip()

    def is_debug(self) -> bool:
        """
        Whether debug tooling is active.

        Two gates on purpose: DEBUG in config.py decides whether a build
        carries the tooling at all, and the preference decides whether this
        commander has switched it on. A release build ignores the preference.
        """
        return bool(DEBUG and self.debug_mode_value)

    def is_local(self) -> bool:
        """Whether events are being redirected to a local site."""
        return bool(self.is_debug() and self.use_localhost_value)

    def base_url(self) -> str:
        """
        Where events go.

        The localhost redirect wins over everything while DEBUG is on, so a
        development build cannot accidentally post into the live feed. A
        release build (DEBUG = False) always uses the squadron endpoint,
        whatever is stored.
        """
        if self.is_local():
            return self.localhost_url_value or DEFAULT_LOCALHOST_URL
        return squadron_url()

    def is_stealthed(self) -> bool:
        return bool(self.stealth.get())

    def is_category_enabled(self, category: str) -> bool:
        """Stealth mode overrides every individual choice without erasing it."""
        if self.is_stealthed():
            return False
        var = self.categories.get(category)
        return bool(var.get()) if var else False

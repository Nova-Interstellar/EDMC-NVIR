"""
Per-commander preferences, stored in EDMC's config.

Only two things are a commander's choice: the squadron token, and what they are
willing to broadcast. Endpoints are squadron infrastructure and live in
`config.py`.
"""

import tkinter as tk

from config import config  # type: ignore

from . import events
from .config import KEY_API_TOKEN, KEY_CATEGORY, KEY_STEALTH, RETIRED_KEYS
from .log import logger


class Settings:
    """Reads and writes what this commander chooses to broadcast."""

    def __init__(self):
        self.api_token = tk.StringVar()
        self.stealth = tk.BooleanVar()
        self.categories = {key: tk.BooleanVar() for key in events.CATEGORIES}

        # Plain copy for the delivery thread. Tk variables may only be read
        # from the thread running the main loop, and the sender is not it.
        self.api_token_value = ""

        self.load()

    def load(self) -> None:
        self._drop_retired_keys()

        self.api_token.set(config.get_str(KEY_API_TOKEN, default=""))
        self.stealth.set(config.get_bool(KEY_STEALTH, default=False))

        for key, var in self.categories.items():
            var.set(config.get_bool(KEY_CATEGORY.format(key), default=True))

        self._snapshot()

    def save(self) -> None:
        config.set(KEY_API_TOKEN, self.api_token.get().strip())
        config.set(KEY_STEALTH, self.stealth.get())

        for key, var in self.categories.items():
            config.set(KEY_CATEGORY.format(key), var.get())

        self._snapshot()
        logger.info("Preferences saved")

    def _drop_retired_keys(self) -> None:
        """Clear webhook URLs and endpoints left by an earlier build."""
        for key in RETIRED_KEYS:
            if config.get_str(key, default=""):
                config.delete(key)
                logger.info("Removed retired setting %s", key)

    def _snapshot(self) -> None:
        """Refresh the plain copy the delivery thread reads."""
        self.api_token_value = self.api_token.get().strip()

    def is_stealthed(self) -> bool:
        return bool(self.stealth.get())

    def is_category_enabled(self, category: str) -> bool:
        """Stealth mode overrides every individual choice without erasing it."""
        if self.is_stealthed():
            return False
        var = self.categories.get(category)
        return bool(var.get()) if var else False

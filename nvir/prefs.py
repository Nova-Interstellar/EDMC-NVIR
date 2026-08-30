"""
Preferences tab.

Two settings only: the squadron token, and what this commander broadcasts.
Endpoints ship in `config.py` — nobody should have to paste a URL to use this.

Built against EDMC 6.x widgets: there is no `nb.Entry` any more (it is
`nb.EntryMenu`), and `plugin_prefs` is isinstance-checked, so every frame
returned from here — including an error frame — must be an `nb.Frame`.
"""

import tkinter as tk
from tkinter import ttk

import myNotebook as nb  # type: ignore

from . import events
from .config import DEBUG, PLUGIN_VERSION
from .log import logger

PAD = {"padx": 10, "pady": 3}


class PreferencesUI:
    """The plugin's page in EDMC's settings dialog."""

    def __init__(self, settings):
        self._settings = settings
        self._category_boxes = {}

    def build(self, parent) -> nb.Frame:
        frame = nb.Frame(parent)
        frame.columnconfigure(1, weight=1)

        # nb.Frame grids its own spacer into row 0, so content starts at 1.
        row = 1

        nb.Label(frame, text="Nova Interstellar squadron feed").grid(
            row=row, column=0, columnspan=2, sticky=tk.W, **PAD
        )
        row += 1

        nb.Label(frame, text="Squadron token").grid(row=row, column=0, sticky=tk.W, **PAD)
        nb.EntryMenu(
            frame, textvariable=self._settings.api_token, show="\N{BULLET}"
        ).grid(row=row, column=1, sticky=tk.EW, **PAD)
        row += 1

        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(
            row=row, column=0, columnspan=2, sticky=tk.EW, padx=10, pady=8
        )
        row += 1

        stealth = nb.Checkbutton(
            frame,
            text="Stealth mode \N{EM DASH} broadcast nothing",
            variable=self._settings.stealth,
            command=self._sync_enabled,
        )
        stealth.grid(row=row, column=0, columnspan=2, sticky=tk.W, **PAD)
        row += 1

        nb.Label(frame, text="Broadcast").grid(row=row, column=0, sticky=tk.W, **PAD)
        row += 1

        for key in events.CATEGORY_ORDER:
            box = nb.Checkbutton(
                frame,
                text=events.CATEGORIES[key],
                variable=self._settings.categories[key],
            )
            box.grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=26, pady=1)
            self._category_boxes[key] = box
            row += 1

        footer = "NVIR {0}".format(PLUGIN_VERSION)
        if DEBUG:
            footer += " \N{MIDDLE DOT} debug"
        nb.Label(frame, text=footer).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(12, 4)
        )

        self._sync_enabled()
        return frame

    def _sync_enabled(self) -> None:
        """Stealth mode locks the category choices without clearing them."""
        state = tk.DISABLED if self._settings.is_stealthed() else tk.NORMAL
        for box in self._category_boxes.values():
            try:
                box.configure(state=state)
            except tk.TclError:  # widget already destroyed
                pass


def error_frame(parent, message: str) -> nb.Frame:
    """A prefs page that reports its own failure instead of vanishing."""
    logger.error("Preferences UI failed: %s", message)
    frame = nb.Frame(parent)
    frame.columnconfigure(0, weight=1)
    nb.Label(frame, text="NVIR could not build its settings page.").grid(
        row=1, column=0, sticky=tk.W, **PAD
    )
    nb.Label(frame, text=str(message)).grid(row=2, column=0, sticky=tk.W, **PAD)
    return frame

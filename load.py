"""
EDMC-NVIR - Nova Interstellar squadron feed.

Broadcasts a declared set of journal events to the squadron's Discord. Only
events listed in `nvir/events.py` are ever read, and only the fields that entry
declares are ever sent.

EDMC entry points only; the work lives in the `nvir` package.
"""

import tkinter as tk
from typing import Optional

from nvir.log import logger
from nvir.plugin import Plugin

_plugin: Optional[Plugin] = None


def plugin_start3(plugin_dir: str) -> str:
    global _plugin
    _plugin = Plugin()
    return _plugin.start()


def plugin_stop() -> None:
    global _plugin
    if _plugin is not None:
        _plugin.stop()
        _plugin = None


def plugin_app(parent: tk.Frame):
    return _plugin.app_widgets(parent) if _plugin else None


def plugin_prefs(parent, cmdr: str, is_beta: bool):
    return _plugin.prefs_widget(parent) if _plugin else None


def prefs_changed(cmdr: str, is_beta: bool) -> None:
    if _plugin is not None:
        _plugin.save_prefs()


def journal_entry(
    cmdr: str,
    is_beta: bool,
    system: str,
    station: str,
    entry: dict,
    state: dict,
) -> None:
    if _plugin is None:
        return
    try:
        _plugin.on_journal(cmdr, is_beta, system, station, entry, state)
    except Exception:
        # A raise here would show an error banner in EDMC for every entry.
        logger.exception("Failed handling %s", entry.get("event"))

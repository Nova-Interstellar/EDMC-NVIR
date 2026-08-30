"""Wires the pieces together and holds the plugin's live state."""

from typing import Optional

from . import debug_panel, prefs, transport, version
from .config import PLUGIN_NAME, PLUGIN_VERSION
from .journal import Journal
from .log import logger
from .sender import Sender
from .settings import Settings


class Plugin:
    """One instance per EDMC run."""

    def __init__(self):
        self.settings: Optional[Settings] = None
        self.sender: Optional[Sender] = None
        self.journal: Optional[Journal] = None
        self.panel: Optional[debug_panel.AppPanel] = None
        self.checker = version.Checker()
        self.cmdr = ""

    def start(self) -> str:
        self.settings = Settings()
        self.sender = Sender(transport.build(self.settings))
        self.sender.start()
        self.journal = Journal(self.settings, self.sender)
        self.panel = debug_panel.AppPanel(self)
        self.checker.start()

        logger.info("%s %s started", PLUGIN_NAME, PLUGIN_VERSION)
        return PLUGIN_NAME

    def stop(self) -> None:
        if self.sender is not None:
            self.sender.stop()
            self.sender = None
        logger.info("%s stopped", PLUGIN_NAME)

    def app_widgets(self, parent):
        return self.panel.build(parent) if self.panel else None

    def prefs_widget(self, parent):
        try:
            return prefs.PreferencesUI(self.settings, self.checker).build(parent)
        except Exception as err:
            logger.exception("Building the preferences page failed")
            return prefs.error_frame(parent, err)

    def save_prefs(self) -> None:
        if self.settings is None:
            return
        self.settings.save()
        if self.panel is not None:
            # Debug mode is a preference now, so the button appears and
            # disappears with it rather than waiting for a restart.
            self.panel.sync()

    def on_journal(self, cmdr, is_beta, system, station, entry, state) -> None:
        if cmdr:
            self.cmdr = cmdr
        if self.journal is not None:
            self.journal.on_entry(cmdr, is_beta, system, station, entry, state)

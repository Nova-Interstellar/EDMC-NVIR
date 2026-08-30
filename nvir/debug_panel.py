"""
Debug tooling, gated by DEBUG in config.py.

The main window gets a status row; the Debug button opens a window where you
pick a registered event, edit its journal fields as JSON, and send it through
the real delivery path - same extraction, same payload, same transport as a
live event.

Preview shows the payload and where it would go, without sending. Send posts it
with `test` set, so the API routes it by the Debug API URL rather than the live
one, and echoes back the embed it rendered.
"""

import json
import tkinter as tk
from tkinter import ttk

from . import events, payload
from .config import DEBUG, PLUGIN_VERSION
from .log import logger


class AppPanel:
    """The plugin's row in EDMC's main window."""

    def __init__(self, controller):
        self._controller = controller
        self._status = None
        self._window = None

    def build(self, parent):
        label = tk.Label(parent, text="Nova Feed")

        right = tk.Frame(parent)
        right.columnconfigure(0, weight=1)

        self._status = tk.Label(right, text=self._idle_text(), anchor=tk.W)
        self._status.grid(row=0, column=0, sticky=tk.EW)

        if DEBUG:
            ttk.Button(right, text="Debug", width=7, command=self.open_debug).grid(
                row=0, column=1, padx=(6, 0)
            )

        return label, right

    def _idle_text(self) -> str:
        if self._controller.settings.is_stealthed():
            return "stealth"
        return "ready"

    def set_status(self, text: str) -> None:
        if self._status is not None:
            try:
                self._status.configure(text=text)
            except tk.TclError:
                pass

    def open_debug(self) -> None:
        if self._window is not None and self._window.winfo_exists():
            self._window.lift()
            return
        self._window = DebugWindow(self._controller)


class DebugWindow(tk.Toplevel):
    """Compose a journal entry by hand and push it through the real path."""

    def __init__(self, controller):
        super().__init__()
        self._controller = controller

        self.title("NVIR debug \N{EM DASH} {0}".format(PLUGIN_VERSION))
        self.geometry("620x620")
        self.columnconfigure(1, weight=1)
        self.rowconfigure(5, weight=1)
        self.rowconfigure(7, weight=1)

        names = events.event_names()
        self._event = tk.StringVar(value=names[0])
        self._cmdr = tk.StringVar(value=controller.cmdr or "Test Commander")
        self._system = tk.StringVar(value="Shinrarta Dezhra")
        self._station = tk.StringVar(value="Jameson Memorial")

        row = 0
        ttk.Label(self, text="Event").grid(row=row, column=0, sticky=tk.W, padx=8, pady=4)
        picker = ttk.OptionMenu(
            self, self._event, names[0], *names, command=self._on_event_change
        )
        picker.grid(row=row, column=1, sticky=tk.EW, padx=8, pady=4)
        row += 1

        for label, var in (
            ("Commander", self._cmdr),
            ("System", self._system),
            ("Station", self._station),
        ):
            ttk.Label(self, text=label).grid(
                row=row, column=0, sticky=tk.W, padx=8, pady=2
            )
            ttk.Entry(self, textvariable=var).grid(
                row=row, column=1, sticky=tk.EW, padx=8, pady=2
            )
            row += 1

        ttk.Label(self, text="Journal fields").grid(
            row=row, column=0, columnspan=2, sticky=tk.W, padx=8, pady=(8, 2)
        )
        row += 1

        self._entry_text = tk.Text(self, height=14, wrap=tk.NONE, undo=True)
        self._entry_text.grid(
            row=row, column=0, columnspan=2, sticky=tk.NSEW, padx=8, pady=2
        )
        row += 1

        buttons = ttk.Frame(self)
        buttons.grid(row=row, column=0, columnspan=2, sticky=tk.EW, padx=8, pady=6)
        ttk.Button(buttons, text="Reset", command=self._load_sample).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Preview", command=self._preview).pack(
            side=tk.LEFT, padx=(6, 0)
        )
        ttk.Button(buttons, text="Send", command=self._send).pack(
            side=tk.LEFT, padx=(6, 0)
        )
        self._target = ttk.Label(buttons, text="")
        self._target.pack(side=tk.RIGHT)
        row += 1

        self._output = tk.Text(self, height=10, wrap=tk.WORD)
        self._output.grid(
            row=row, column=0, columnspan=2, sticky=tk.NSEW, padx=8, pady=(2, 8)
        )

        self._load_sample()
        self._refresh_target()

    # --- actions ------------------------------------------------------------

    def _on_event_change(self, *_args) -> None:
        self._load_sample()
        self._refresh_target()

    def _load_sample(self) -> None:
        spec = events.spec_for(self._event.get())
        sample = dict(spec.sample) if spec else {}
        sample = {"event": self._event.get(), "timestamp": payload.utc_now(), **sample}
        self._entry_text.delete("1.0", tk.END)
        self._entry_text.insert("1.0", json.dumps(sample, indent=2))

    def _destination(self) -> str:
        """Where this event would go: category override, debug URL, default."""
        spec = events.spec_for(self._event.get())
        category = spec.category if spec else ""
        return (
            self._controller.sender.transport.url_for(category, test=True)
            or "no API URL set"
        )

    def _refresh_target(self) -> None:
        self._target.configure(text=self._destination())

    def _build_payload(self):
        raw = self._entry_text.get("1.0", tk.END).strip()
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError as err:
            self._write("Journal fields are not valid JSON:\n{0}".format(err))
            return None

        entry.setdefault("event", self._event.get())
        entry.setdefault("timestamp", payload.utc_now())

        built = payload.build(
            self._cmdr.get().strip() or "Test Commander",
            entry.get("event"),
            entry,
            self._system.get().strip(),
            self._station.get().strip(),
            test=True,
        )

        if built is None:
            self._write(
                "Nothing to send: {0} is not registered, or its extractor "
                "rejected these fields.".format(entry.get("event"))
            )
        return built

    def _preview(self) -> None:
        built = self._build_payload()
        if built is None:
            return
        self._write(
            "POST {0}\n\nPAYLOAD\n{1}".format(
                self._destination(), json.dumps(built, indent=2)
            )
        )

    def _send(self) -> None:
        built = self._build_payload()
        if built is None:
            return

        self._refresh_target()
        self._write("Sending {0}\N{HORIZONTAL ELLIPSIS}".format(built["event"]))
        logger.info("Debug send: %s", built["event"])
        self._controller.sender.submit(built, on_result=self._on_result)

    def _on_result(self, result) -> None:
        # Runs on the delivery thread; hop back before touching any widget.
        def apply():
            lines = [
                "{0}  status={1}".format(
                    "OK" if result.ok else "FAILED", result.status
                ),
                result.detail,
            ]
            # The API echoes the embed it rendered for a debug send, so the
            # panel can show what the channel would actually see.
            embed = (result.body or {}).get("embed")
            if embed:
                lines += ["", "EMBED", json.dumps(embed, indent=2)]
            self._write("\n".join(lines))

        try:
            self.after(0, apply)
        except tk.TclError:  # window closed while the send was in flight
            pass

    def _write(self, text: str) -> None:
        self._output.delete("1.0", tk.END)
        self._output.insert("1.0", text)

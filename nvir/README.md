# EDMC-NVIR-Uplink internals

Developer notes for the plugin package. End-user install and settings are in
the [root README](../README.md).

## Shape

The plugin is a filter and a transport, nothing more. It decides *whether* an
event may leave the machine and *what* of it goes; nova-web decides whether the
event is worth posting and what it reads like.

```
journal_entry (EDMC main thread)
  └─ journal.py    replay guard, category gate, carrier ownership
      └─ payload.py    normalise to the wire shape
          └─ sender.py     queue, hand to the delivery thread
              └─ transport.py  POST to nova-web
                                  └─ roster, routing, embed, Discord
```

Nothing blocks EDMC's main thread: `journal_entry` only enqueues.

| File | Holds |
| --- | --- |
| `config.py` | Build-time switches: `DEBUG`, endpoints, repo, preference keys |
| `version.py` | Update check against the published `PLUGIN_VERSION` |
| `events.py` | The registry — the one table deciding what may be sent |
| `payload.py` | The normalised wire shape |
| `transport.py` | HTTP to nova-web, retries classified |
| `sender.py` | Queue and delivery thread, rate-limit back-off |
| `journal.py` | Replay guard, category gate, carrier ownership |
| `settings.py` | Token and category choices |
| `prefs.py` | Settings tab |
| `debug_panel.py` | Main-window row and the debug window |
| `log.py` | Logger wired into EDMC's tree |
| `link-to-edmc.bat` | Links this checkout into EDMC's plugin folder |

## Working on a checkout

Double-click **`nvir/link-to-edmc.bat`**. It junctions the plugin root — its
own parent, not this package folder — into
`%LOCALAPPDATA%\EDMarketConnector\plugins`, so EDMC loads the code you are
editing and there is nothing to copy after a change. Restart EDMC to pick up
the link; after that a plugin reload is enough.

A junction needs no administrator rights. The script names the link after the
repository folder, so it survives a rename, and it clears an existing entry with
`rmdir` *without* `/s` — which removes a junction or an empty folder and fails
on anything holding files, so it can neither follow a link into your checkout
nor delete real work.

## Adding an event

Add one `EventSpec` to `events.py`:

```python
EventSpec(
    event="ShipyardBuy",
    category="trade",                  # must exist in events.CATEGORIES
    extract=_extract_shipyard_buy,     # returns a LIST of data dicts
    sample={"ShipType": "mandalay", "ShipPrice": 27452400},
)
```

`CATEGORIES` maps a channel to its checkbox label, so declaring the channel is
what creates the checkbox, picks the destination, and gates the send.
Extraction, the preferences grid and the debug form all read from that one
table, so there is no second list to update.

An extractor returns a **list**, so one journal entry can become several
payloads. `Promotion` uses this: each career is its own payload with its own
nonce, routed and retried alone. Its `category` is a function of the data
rather than a constant — the one event whose destination depends on its
contents.

Then add the event to `FEED_EVENTS` in nova-web's
`src/data/internal/authored/squadron-feed.ts` and give it a describer in
`src/services/squadron-feed.ts` — the server keeps its own allowlist, so an
event the plugin sends but the site does not know is refused.

An extractor returns `None` to decline an occurrence: `RedeemVoucher` uses this
to drop trade dividends and scan vouchers, which share the event with bounties
but are a different activity.

## Why the wording lives on the server

`events.py` carries no copy or colours. nova-web renders the embed,
so changing what the feed says is a deploy rather than every member updating
their plugin — and there is only one implementation of each sentence.

## Things that will bite you

**EDMC 6.x widgets.** `nb.Entry` no longer exists; it is `nb.EntryMenu`. And
`plugin_prefs` is isinstance-checked against `nb.Frame`, so an error path that
returns a plain `tk.Frame` makes the whole settings tab vanish rather than show
an error. `prefs.error_frame` exists for exactly this.

**`nb.Frame` grids a spacer into row 0.** Plugin content starts at row 1.

**Tk variables are main-thread only.** The delivery thread must never touch a
`StringVar`. `Settings` keeps plain-string snapshots refreshed in `load()` and
`save()`; `transport.py` reads those. Reading a Tk variable off-thread appears
to work and then fails intermittently.

**Journal replay.** EDMC replays the current journal file on load. `journal.py`
drops anything stamped before startup. `REPLAY_GRACE_SECONDS` is not zero on
purpose: journal timestamps have whole-second precision, so an event in the same
second as startup parses as *earlier* than startup and would be dropped.

**`CarrierJump` fires for passengers.** It also carries no `CarrierID` — the
carrier is identified by `MarketID`, and `StationName` is the callsign.
`journal.py` only forwards a jump for a carrier it has seen this commander own
via `CarrierStats`, `CarrierBuy` or `CarrierJumpRequest`. The site re-checks
against the roster's carrier callsigns, since the plugin cannot be trusted.

## Endpoints

`config.py` holds them. Members never type a URL — an endpoint is squadron
infrastructure, not a preference.

- `API_BASE_URL` — where events go (`https://nvir.vercel.app`).
- Channel routing is decided on the site, not here: `FEED_EVENT_CHANNELS` and
  `PROMOTION_CHANNELS` in `src/data/internal/authored/squadron-feed.ts`, with
  the webhook URLs themselves in Vercel Global Config.
- `DEFAULT_LOCALHOST_URL` — prefilled into the debug section's field.

Resolution order, in `Settings.base_url_for`:

1. **Localhost redirect**, if both debug gates and Use localhost are on. Beats
   everything, so a development build cannot post into the live feed.
2. `API_BASE_URL`.

A build shipped with `DEBUG = False` ignores a stored localhost redirect
entirely, so a developer's setting cannot follow the plugin to a member. See
[The two debug gates](#the-two-debug-gates).

Note that `test` on the payload does **not** change where the plugin posts — it
tells the site to use its debug Discord channel. Redirecting the plugin itself
is what the localhost toggle is for.

## The two debug gates

Debug tooling is behind two switches, and both must be on:

1. **`DEBUG` in `config.py`** — whether the build carries the tooling at all.
   A release build ships `DEBUG = False`, and then no Development section is
   drawn and any stored debug preference is ignored outright.
2. **The Debug mode checkbox** — whether this commander has switched it on.

`Settings.is_debug()` is that `and`. It gates the Development section's
contents, the main window's Debug button, and the localhost redirect
(`is_local()` is `is_debug() and use_localhost`).

The Debug button is built once at startup and shown or hidden on preference
save, because `plugin_app` only runs once — toggling it does not need a restart.

## Developing against a local site

Tick **Debug mode**, then **Use localhost**, and point it at your dev server.
Each field is greyed out until the switch above it is on, and the debug
window's destination line shows where a send would actually go.

Beats editing `config.py` and remembering to put it back.

## Update check

`version.py` reads `PLUGIN_VERSION` out of `nvir/config.py` on the repository's
default branch, so a check works without cutting a release. The fetch runs on a
background thread at plugin start and the answer is cached for the session; the
settings page renders whatever is known and updates in place when it lands.

Versions compare numerically, so `0.10.0` is correctly newer than `0.9.0`, and a
suffix like `0.4.0-rc1` degrades to `(0, 4, 0)` rather than breaking the check.

`GITHUB_REPO` is a single constant. Renaming the repository is one edit — and
GitHub redirects the old path, so an already-shipped build keeps checking
successfully in the meantime.

Bumping `PLUGIN_VERSION` and pushing is what tells every member an update
exists, so bump it in the same commit as the change you want them to take.

## Debug window

With both debug gates on, a **Debug** button appears in EDMC's main window.
Pick an event, edit its journal fields as JSON, and:

- **Preview** shows the payload and the URL it would go to. Sends nothing.
- **Send** posts it for real with `test` set, so the site routes it to the debug
  channel, and echoes back the embed it rendered.

Because it goes through `payload.build` and the real sender queue, it exercises
the same code a live journal entry does.

Ship a release build with `DEBUG = False`.

## Payload

```json
{
  "v": 1, "plugin": "0.4.0",
  "cmdr": "Elias Korben",
  "event": "Promotion",
  "category": "exploration",
  "at": "2026-08-30T18:04:11Z",
  "nonce": "3f2a…",
  "system": "Shinrarta Dezhra", "station": "Jameson Memorial",
  "data": { "career": "Explore", "careerLabel": "Exploration", "rank": "Elite" },
  "test": false
}
```

`at` is the journal's event time, not send time. `nonce` is per send, so a retry
that lands twice posts once — the site remembers a nonce only after it has
actually posted, so a retry after a rate-limit still gets through.

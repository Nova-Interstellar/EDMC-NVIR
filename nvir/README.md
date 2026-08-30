# EDMC-NVIR internals

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
                                  └─ roster, thresholds, embed, Discord
```

Nothing blocks EDMC's main thread: `journal_entry` only enqueues.

| File | Holds |
| --- | --- |
| `config.py` | Build-time switches: `DEBUG`, endpoints, preference keys |
| `events.py` | The registry — the one table deciding what may be sent |
| `payload.py` | The normalised wire shape |
| `transport.py` | HTTP to nova-web, retries classified |
| `sender.py` | Queue and delivery thread, rate-limit back-off |
| `journal.py` | Replay guard, category gate, carrier ownership |
| `settings.py` | Token and category choices |
| `prefs.py` | Settings tab |
| `debug_panel.py` | Main-window row and the debug window |
| `log.py` | Logger wired into EDMC's tree |

## Adding an event

Add one `EventSpec` to `events.py`:

```python
EventSpec(
    event="ShipyardBuy",
    category="milestones",
    extract=_extract_shipyard_buy,
    amount_field="price",
    sample={"ShipType": "mandalay", "ShipPrice": 27452400},
)
```

Extraction, the preferences checkboxes and the debug form all read from that
one entry, so there is no second list to update.

Then add the event to `FEED_EVENTS` in nova-web's
`src/data/internal/authored/squadron-feed.ts` and give it a describer in
`src/services/squadron-feed.ts` — the server keeps its own allowlist, so an
event the plugin sends but the site does not know is refused.

An extractor returns `None` to decline an occurrence: `RedeemVoucher` uses this
to drop trade dividends and scan vouchers, which share the event with bounties
but are a different activity.

## Why the wording lives on the server

`events.py` carries no copy, colours or thresholds. nova-web renders the embed,
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

**`SellOrganicData` has no total.** It must be summed across `BioData`, adding
`Value` and `Bonus` per sample.

**`MarketSell` reports gross.** Profit is `TotalSale − AvgPricePaid × Count`.

**`MultiSellExplorationData` is a different shape** from
`SellExplorationData` — `Discovered[]` of `{SystemName, NumBodies}` against a
flat `Systems[]`. It is also the common case; a plugin that only handles the
singular one misses most exploration sales.

## Endpoints

`config.py` holds them. Members never type a URL — an endpoint is squadron
infrastructure, not a preference.

- `API_BASE_URL` — where events go.
- `CATEGORY_API_URLS` — per-category override, for pointing a category at a
  different *deployment*. Routing a category to a different Discord *channel* is
  done on the site, in `src/constants/squadron-channels.ts`.
- `DEBUG_API_URL` — where debug sends go while `DEBUG` is on. Point it at
  `http://localhost:3000` to develop against a local site.

## Debug window

`DEBUG = True` in `config.py` puts a **Debug** button in EDMC's main window.
Pick an event, edit its journal fields as JSON, and:

- **Preview** shows the payload and the URL it would go to. Sends nothing.
- **Send** posts it for real with `test` set, so the site routes it to the debug
  channel, and echoes back the embed it rendered.

Because it goes through `payload.build` and the real sender queue, it exercises
the same code a live journal entry does.

Turn `DEBUG` off for a release build.

## Payload

```json
{
  "v": 1, "plugin": "0.3.0",
  "cmdr": "Elias Korben",
  "event": "SellOrganicData", "category": "exobiology",
  "at": "2026-08-30T18:04:11Z",
  "nonce": "3f2a…",
  "system": "Shinrarta Dezhra", "station": "Jameson Memorial",
  "amount": 38021300,
  "data": { "count": 2, "total": 38021300, "best": "Stratum Tectonicas" },
  "test": false
}
```

`at` is the journal's event time, not send time. `nonce` is per send, so a retry
that lands twice posts once — the site remembers a nonce only after it has
actually posted, so a retry after a rate-limit still gets through.

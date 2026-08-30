# EDMC-NVIR-Uplink

Squadron feed for **Nova Interstellar**. Posts your notable moments — big
trades, bounties, exploration and exobiology payouts, rank-ups, carrier jumps —
to the squadron Discord, automatically, while you fly.

Only the events listed below are ever read, and only the details each one needs
are ever sent. Nothing else leaves your machine.

## Install

1. Download the plugin and unzip it into EDMC's plugin folder:

   ```
   %LOCALAPPDATA%\EDMarketConnector\plugins\EDMC-NVIR-Uplink
   ```

   In EDMC you can get there with **File → Settings → Plugins → Open**.

2. Restart EDMC.
3. Open **File → Settings → NVIR Uplink** and paste the squadron token. Ask a
   squadron officer for it.

That is the whole setup. There is no URL to configure — the plugin already
knows where to send things.

Requires EDMC 6.x.

## Settings

**File → Settings → NVIR Uplink**

| Setting | What it does |
| --- | --- |
| **Squadron member token** | Identifies you to the squadron site. Without it nothing is sent. |
| **Stealth mode** | Broadcasts nothing at all. Your category choices are remembered, just switched off. |
| **Broadcast** | Pick which kinds of moment you are happy to share. |

Stealth mode is there so you can go quiet for an evening without losing your
settings — tick it, and nothing you do reaches the channel until you untick it.

The top of the page shows the version you are running, and whether a newer one
has been published. Either way it links to the repository, where you can
download the latest.

## What gets posted

| Category | Posted when you… |
| --- | --- |
| **Trade** | Sell cargo at a good profit |
| **Combat** | Cash in bounty vouchers or combat bonds |
| **Exploration** | Sell exploration data at Universal Cartographics |
| **Exobiology** | Sell samples at Vista Genomics |
| **Milestones** | Earn a rank promotion, or collect a community goal reward |
| **Fleet Carrier** | Schedule, cancel, or complete a carrier jump |

Small payouts are filtered out so the channel stays worth reading. The squadron
site decides the thresholds, so they can be tuned without you updating anything.

A couple of details worth knowing:

- **Trade posts your profit, not the sale price.** Selling 200M of cargo you
  paid 190M for reads as 10M, which is what you actually made.
- **Carrier jumps only post for your own carrier.** The game tells the plugin
  about a jump even when you are just a passenger aboard someone else's; those
  are ignored.
- **Restarting EDMC will not re-post your day.** Only things that happen while
  the plugin is running are sent.

## Privacy

The plugin holds no Discord webhook, so it cannot post to the channel directly
— it hands events to the squadron site, which checks them and posts them. Your
token identifies you and nothing more.

Your name is checked against the Inara squadron roster. If it does not match,
nothing you send is posted; tell an officer and they can add a mapping.

## Troubleshooting

**Nothing is posting.** Check the token in **File → Settings → NVIR Uplink**, and that
Stealth mode is off and the category is ticked. Remember the thresholds: a small
sale is filtered out on purpose.

**A payout was ignored.** It was probably under the threshold for its category.

**Something looks wrong.** EDMC's log has the detail —
**File → Settings → Plugins → Open Log Folder**, and search for `NVIR`.

**The settings page says "Version check unavailable".** It could not reach
GitHub. Harmless — it has no effect on whether your events are sent.

---

Developing on the plugin? See [`nvir/README.md`](nvir/README.md).

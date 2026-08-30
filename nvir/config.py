"""
Static configuration for the NVIR plugin.

Everything here is set in source and ships the same for everyone. Endpoints are
squadron infrastructure, not a member's choice, so they live here rather than in
preferences — a commander should never have to paste a URL to use the plugin.

The only per-commander settings are the squadron token and which categories to
broadcast; those live in `settings.py`.
"""

PLUGIN_NAME = "NVIR"
PLUGIN_VERSION = "0.3.0"

# Shows the debug panel in the main EDMC window: pick an event, edit its
# fields, send it through the real delivery path. Turn off for a release build.
DEBUG = False

# --- Endpoints ---------------------------------------------------------------
# Events go to the nova-web API, which checks them against the squadron roster,
# applies the thresholds, renders the embed and posts it to Discord. No webhook
# URL ever reaches a member's machine: the site holds those, so a leaked EDMC
# config exposes nothing and channels can be re-routed without a plugin update.

API_BASE_URL = "https://nova-interstellar.vercel.app"

API_EVENTS_PATH = "/api/squadron/events"

# Per-category endpoint overrides. Blank means API_BASE_URL. These exist for
# pointing a category at a different deployment; routing a category to a
# different Discord *channel* is done on the site, not here.
CATEGORY_API_URLS = {
    "trade": "",
    "combat": "",
    "exploration": "",
    "exobiology": "",
    "milestones": "",
    "carrier": "",
}

# Where debug sends go while DEBUG is on. Blank means API_BASE_URL; the payload
# is flagged `test` either way, and the site posts it to its debug channel.
DEBUG_API_URL = "http://localhost:3000"

USER_AGENT = f"EDMC-NVIR/{PLUGIN_VERSION}"
HTTP_TIMEOUT = 10

# Give up on an event after this many failed attempts.
MAX_ATTEMPTS = 3

# Journal entries older than this many seconds before plugin start are treated
# as replay and dropped. EDMC replays the current journal file on load.
#
# The grace absorbs the game's whole-second timestamps: an event happening in
# the same second the plugin starts would otherwise parse as earlier than
# startup and be dropped. Replayed history is minutes to hours old, so a few
# seconds of slack costs nothing.
REPLAY_GRACE_SECONDS = 5

# --- Preference keys ---------------------------------------------------------

KEY_API_TOKEN = "nvir_api_token"
KEY_STEALTH = "nvir_stealth"
KEY_CATEGORY = "nvir_category_{0}"

# Settings retired as the plugin moved to the squadron API. Any value still
# stored under these keys is deleted on load, so no webhook URL or hand-typed
# endpoint lingers in a member's EDMC config.
RETIRED_KEYS = (
    "nvir_webhook_url",
    "nvir_api_url",
    "nvir_api_url_debug",
    "nvir_api_url_trade",
    "nvir_api_url_combat",
    "nvir_api_url_exploration",
    "nvir_api_url_exobiology",
    "nvir_api_url_milestones",
    "nvir_api_url_carrier",
)


def base_url_for(category: str, test: bool = False) -> str:
    """Endpoint for a category: its override, else the shared base URL."""
    if test:
        return DEBUG_API_URL or API_BASE_URL
    return CATEGORY_API_URLS.get(category) or API_BASE_URL

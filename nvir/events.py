"""
The event registry: the single table deciding what leaves this machine.

Two things are carried: rank-ups, each career going to its own channel, and
fleet carrier jumps. Nothing is measured against a credit figure — market
sales and their thresholds are deliberately out.

An extractor returns a *list*, so one journal entry can become several
payloads: a Promotion carrying two careers becomes two, each with its own
nonce, routed and retried alone.

Wording and colours are absent — nova-web renders the embed, so the copy lives
in one place.
"""

from dataclasses import dataclass
from typing import Callable, List, Optional, Union

# --- Categories --------------------------------------------------------------
# One category is one Discord channel and one checkbox. The label is what the
# commander reads in preferences; the embed's own title comes from the site.

CATEGORIES = {
    "combat": "Combat Rank",
    "trade": "Trade Rank",
    "exploration": "Exploration Rank",
    "exobiology": "Exobiology Rank",
    "mercenary": "Mercenary Rank",
    "carrier": "Fleet Carrier Jumps",
}

CATEGORY_ORDER = list(CATEGORIES)


def label_of(category: str) -> str:
    return CATEGORIES.get(category, category)


# --- Rank tables -------------------------------------------------------------
# The journal reports a rank as an index, so the name is looked up here.
# Ranks 0-8 are the named tiers; the game continues past Elite with Elite I-V.

_ELITE_SUFFIXES = ["", " I", " II", " III", " IV", " V"]

RANK_TABLES = {
    "Combat": ["Harmless", "Mostly Harmless", "Novice", "Competent", "Expert",
               "Master", "Dangerous", "Deadly", "Elite"],
    "Trade": ["Penniless", "Mostly Penniless", "Peddler", "Dealer", "Merchant",
              "Broker", "Entrepreneur", "Tycoon", "Elite"],
    "Explore": ["Aimless", "Mostly Aimless", "Scout", "Surveyor", "Trailblazer",
                "Pathfinder", "Ranger", "Pioneer", "Elite"],
    "Soldier": ["Defenceless", "Mostly Defenceless", "Rookie", "Soldier",
                "Gunslinger", "Warrior", "Gladiator", "Deadeye", "Elite"],
    "Exobiologist": ["Directionless", "Mostly Directionless", "Compiler",
                     "Collector", "Cataloguer", "Taxonomist", "Ecologist",
                     "Geneticist", "Elite"],
    "CQC": ["Helpless", "Mostly Helpless", "Amateur", "Semi Professional",
            "Professional", "Champion", "Hero", "Legend", "Elite"],
}

# Journal career key -> channel. CQC shares the combat channel and the combat
# checkbox: it is still fighting, and a separate toggle for it earned nothing.
# A career absent here is never broadcast, which is how Federation and Empire
# navy ranks stay out.
PROMOTION_CATEGORIES = {
    "Combat": "combat",
    "CQC": "combat",
    "Trade": "trade",
    "Explore": "exploration",
    "Exobiologist": "exobiology",
    "Soldier": "mercenary",
}

CAREER_LABELS = {
    "Combat": "Combat",
    "Trade": "Trade",
    "Explore": "Exploration",
    "Soldier": "Mercenary",
    "Exobiologist": "Exobiology",
    "CQC": "CQC",
}


def rank_name(career: str, index: int) -> str:
    """Resolve a Promotion rank index to its in-game name."""
    table = RANK_TABLES.get(career)
    if not table:
        return "Rank {0}".format(index)
    if 0 <= index < len(table):
        return table[index]
    # Past the last named tier the pilot careers continue as Elite I-V.
    overflow = index - len(table) + 1
    if table[-1] == "Elite" and overflow < len(_ELITE_SUFFIXES):
        return "Elite" + _ELITE_SUFFIXES[overflow]
    return "Rank {0}".format(index)


# --- Spec --------------------------------------------------------------------


@dataclass(frozen=True)
class EventSpec:
    """One journal event the plugin is allowed to broadcast."""

    event: str
    #: Returns one data dict per payload, or None to decline this occurrence.
    extract: Callable[[dict], Optional[List[dict]]]
    #: Channel id, or a resolver when it depends on the data.
    category: Union[str, Callable[[dict], Optional[str]]]
    sample: dict

    def category_for(self, data: dict) -> Optional[str]:
        return self.category(data) if callable(self.category) else self.category

    def categories(self) -> List[str]:
        """Every channel this event can reach. Used to skip work early."""
        if callable(self.category):
            return list(dict.fromkeys(PROMOTION_CATEGORIES.values()))
        return [self.category]


# --- Extractors --------------------------------------------------------------


def _extract_promotion(entry: dict) -> Optional[List[dict]]:
    """
    One payload per career.

    A Promotion may carry several careers at once and each belongs to a
    different channel, so they are split here rather than fanned out server
    side: every rank-up then gets its own nonce, route and retry.
    """
    promotions = [
        {
            # The journal key, so the API can route without trusting a label.
            "career": career,
            "careerLabel": CAREER_LABELS.get(career, career),
            "rank": rank_name(career, int(entry[career])),
        }
        for career in PROMOTION_CATEGORIES
        if career in entry
    ]
    return promotions or None


def _extract_carrier_jump_request(entry: dict) -> Optional[List[dict]]:
    return [{
        "carrierId": int(entry.get("CarrierID", 0)),
        "system": entry.get("SystemName", ""),
        "body": entry.get("Body", ""),
        "departureTime": entry.get("DepartureTime", ""),
    }]


def _extract_carrier_jump(entry: dict) -> Optional[List[dict]]:
    # CarrierJump carries no CarrierID; MarketID identifies the carrier and
    # StationName is its callsign. Ownership is checked before we get here,
    # because this event also fires for anyone merely docked aboard.
    return [{
        "carrierId": int(entry.get("MarketID", 0)),
        "callsign": entry.get("StationName", ""),
        "system": entry.get("StarSystem", ""),
        "body": entry.get("Body", ""),
    }]


def _extract_carrier_jump_cancelled(entry: dict) -> Optional[List[dict]]:
    return [{"carrierId": int(entry.get("CarrierID", 0))}]


# --- Registry ----------------------------------------------------------------

_SPEC_LIST = [
    EventSpec(
        event="Promotion",
        # The career decides the channel.
        category=lambda data: PROMOTION_CATEGORIES.get(str(data.get("career", ""))),
        extract=_extract_promotion,
        sample={"Explore": 8},
    ),
    EventSpec(
        event="CarrierJumpRequest",
        category="carrier",
        extract=_extract_carrier_jump_request,
        sample={
            "CarrierID": 3700005632, "SystemName": "Colonia",
            "Body": "Colonia 2 a", "SystemAddress": 3238296097059,
            "BodyID": 5, "DepartureTime": "2026-08-30T19:15:00Z",
        },
    ),
    EventSpec(
        event="CarrierJump",
        category="carrier",
        extract=_extract_carrier_jump,
        sample={
            "Docked": True, "StationName": "H2J-85B",
            "StationType": "FleetCarrier", "MarketID": 3700005632,
            "StarSystem": "Colonia", "Body": "Colonia 2 a",
        },
    ),
    EventSpec(
        event="CarrierJumpCancelled",
        category="carrier",
        extract=_extract_carrier_jump_cancelled,
        sample={"CarrierID": 3700005632},
    ),
]

SPECS = {spec.event: spec for spec in _SPEC_LIST}

# Journal events that tell us a carrier belongs to this commander. Used to keep
# CarrierJump - which also fires for anyone merely docked aboard - from posting
# somebody else's carrier.
CARRIER_OWNERSHIP_EVENTS = ("CarrierStats", "CarrierBuy", "CarrierJumpRequest")


def spec_for(event_name: str) -> Optional[EventSpec]:
    return SPECS.get(event_name)


def event_names() -> List[str]:
    """Registered events, in declaration order, for menus."""
    return [spec.event for spec in _SPEC_LIST]

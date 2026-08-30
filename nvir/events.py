"""
The event registry: the single table deciding what leaves this machine.

Each EventSpec declares the category an event belongs to and how to lift the
fields that matter out of a raw journal entry. Nothing that is not declared
here is ever read or sent.

Wording, colours and thresholds are deliberately absent: nova-web renders the
embed, so the copy lives in one place and changing it does not mean every
member updating their plugin.
"""

from dataclasses import dataclass
from typing import Callable, Optional

# --- Categories -------------------------------------------------------------

CATEGORIES = {
    "trade": "Trade",
    "combat": "Combat",
    "exploration": "Exploration",
    "exobiology": "Exobiology",
    "milestones": "Milestones",
    "carrier": "Fleet Carrier",
}

CATEGORY_ORDER = list(CATEGORIES)


# --- Rank tables (Promotion) -------------------------------------------------
# The journal reports a rank as an index, so the name has to be looked up here.
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
    "Federation": ["Recruit", "Cadet", "Midshipman", "Petty Officer",
                   "Chief Petty Officer", "Warrant Officer", "Ensign",
                   "Lieutenant", "Lieutenant Commander", "Post Commander",
                   "Post Captain", "Rear Admiral", "Vice Admiral", "Admiral"],
    "Empire": ["Outsider", "Serf", "Master", "Squire", "Knight", "Lord",
               "Baron", "Viscount", "Count", "Earl", "Marquis", "Duke",
               "Prince", "King"],
}

CAREER_LABELS = {
    "Combat": "Combat",
    "Trade": "Trade",
    "Explore": "Exploration",
    "Soldier": "Mercenary",
    "Exobiologist": "Exobiology",
    "CQC": "CQC",
    "Federation": "Federal Navy",
    "Empire": "Imperial Navy",
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


def _localised(entry: dict, key: str) -> str:
    """Prefer the game's localised name, falling back to the raw token."""
    value = entry.get(key + "_Localised") or entry.get(key) or ""
    text = str(value)
    return text.replace("_", " ").title() if text.islower() else text


# --- Spec --------------------------------------------------------------------


@dataclass(frozen=True)
class EventSpec:
    """One journal event the plugin is allowed to broadcast."""

    event: str
    category: str
    extract: Callable[[dict], Optional[dict]]
    sample: dict
    #: Key within the extracted data holding the credit amount, if any. The API
    #: reads it to apply the category threshold.
    amount_field: Optional[str] = None


# --- Extractors --------------------------------------------------------------


def _extract_market_sell(entry: dict) -> Optional[dict]:
    count = int(entry.get("Count", 0))
    total = int(entry.get("TotalSale", 0))
    # TotalSale is gross. What the commander actually made is the difference
    # against what the cargo cost them.
    paid = int(entry.get("AvgPricePaid", 0)) * count
    return {
        "commodity": _localised(entry, "Type"),
        "count": count,
        "total": total,
        "profit": total - paid,
        "stolen": bool(entry.get("StolenGoods", False)),
        "blackMarket": bool(entry.get("BlackMarket", False)),
    }


_VOUCHER_LABELS = {
    "bounty": "bounty vouchers",
    "combatbond": "combat bonds",
}


def _extract_redeem_voucher(entry: dict) -> Optional[dict]:
    # Only fighting pays into the combat feed. Trade dividends, scan data and
    # settlement vouchers arrive through the same event but are a different
    # activity, so they are dropped rather than mislabelled.
    kind = str(entry.get("Type", "")).lower()
    if kind not in _VOUCHER_LABELS:
        return None
    return {
        "voucherType": _VOUCHER_LABELS[kind],
        "amount": int(entry.get("Amount", 0)),
    }


def _extract_sell_exploration(entry: dict) -> Optional[dict]:
    return {
        "systems": len(entry.get("Systems") or []),
        "bodies": 0,
        "base": int(entry.get("BaseValue", 0)),
        "bonus": int(entry.get("Bonus", 0)),
        "total": int(entry.get("TotalEarnings", 0)),
    }


def _extract_multi_sell_exploration(entry: dict) -> Optional[dict]:
    # This variant reports per-system body counts rather than a flat name list.
    discovered = entry.get("Discovered") or []
    return {
        "systems": len(discovered),
        "bodies": sum(int(d.get("NumBodies", 0)) for d in discovered),
        "base": int(entry.get("BaseValue", 0)),
        "bonus": int(entry.get("Bonus", 0)),
        "total": int(entry.get("TotalEarnings", 0)),
    }


def _extract_sell_organic(entry: dict) -> Optional[dict]:
    # SellOrganicData carries no total: it has to be summed across BioData.
    samples = entry.get("BioData") or []
    total = sum(int(s.get("Value", 0)) + int(s.get("Bonus", 0)) for s in samples)
    best = max(
        samples,
        key=lambda s: int(s.get("Value", 0)) + int(s.get("Bonus", 0)),
        default=None,
    )
    species = ""
    if best:
        species = (
            best.get("Species_Localised")
            or best.get("Genus_Localised")
            or best.get("Species")
            or ""
        )
    return {"count": len(samples), "total": total, "best": species}


def _extract_promotion(entry: dict) -> Optional[dict]:
    promotions = [
        {
            "career": CAREER_LABELS.get(career, career),
            "rank": rank_name(career, int(entry[career])),
        }
        for career in RANK_TABLES
        if career in entry
    ]
    if not promotions:
        return None
    return {"promotions": promotions}


def _extract_cg_reward(entry: dict) -> Optional[dict]:
    return {
        "name": entry.get("Name", ""),
        "system": entry.get("System", ""),
        "amount": int(entry.get("Reward", 0)),
    }


def _extract_carrier_jump_request(entry: dict) -> Optional[dict]:
    return {
        "carrierId": int(entry.get("CarrierID", 0)),
        "system": entry.get("SystemName", ""),
        "body": entry.get("Body", ""),
        "departureTime": entry.get("DepartureTime", ""),
    }


def _extract_carrier_jump(entry: dict) -> Optional[dict]:
    # CarrierJump carries no CarrierID; MarketID identifies the carrier and
    # StationName is its callsign. Ownership is checked before we get here,
    # because this event also fires for anyone merely docked aboard.
    return {
        "carrierId": int(entry.get("MarketID", 0)),
        "callsign": entry.get("StationName", ""),
        "system": entry.get("StarSystem", ""),
        "body": entry.get("Body", ""),
    }


def _extract_carrier_jump_cancelled(entry: dict) -> Optional[dict]:
    return {"carrierId": int(entry.get("CarrierID", 0))}


# --- Registry ----------------------------------------------------------------

_SPEC_LIST = [
    EventSpec(
        event="MarketSell",
        category="trade",
        extract=_extract_market_sell,
        amount_field="profit",
        sample={
            "Type": "gold", "Type_Localised": "Gold", "Count": 720,
            "SellPrice": 49512, "TotalSale": 35648640, "AvgPricePaid": 9021,
        },
    ),
    EventSpec(
        event="RedeemVoucher",
        category="combat",
        extract=_extract_redeem_voucher,
        amount_field="amount",
        sample={"Type": "bounty", "Amount": 12400000},
    ),
    EventSpec(
        event="SellExplorationData",
        category="exploration",
        extract=_extract_sell_exploration,
        amount_field="total",
        sample={
            "Systems": ["Shinrarta Dezhra"], "Discovered": [],
            "BaseValue": 10822, "Bonus": 3959, "TotalEarnings": 14781,
        },
    ),
    EventSpec(
        event="MultiSellExplorationData",
        category="exploration",
        extract=_extract_multi_sell_exploration,
        amount_field="total",
        sample={
            "Discovered": [
                {"SystemName": "Byeia Eurk QY-S d3-33", "NumBodies": 14},
                {"SystemName": "Byeia Eurk AA-A h29", "NumBodies": 9},
            ],
            "BaseValue": 2938186, "Bonus": 291000, "TotalEarnings": 3229186,
        },
    ),
    EventSpec(
        event="SellOrganicData",
        category="exobiology",
        extract=_extract_sell_organic,
        amount_field="total",
        sample={
            "MarketID": 3221379328,
            "BioData": [
                {
                    "Genus": "$Codex_Ent_Bacterial_Genus_Name;",
                    "Genus_Localised": "Bacterium",
                    "Species": "$Codex_Ent_Bacterial_05_Name;",
                    "Species_Localised": "Bacterium Cerbrus",
                    "Value": 19010500, "Bonus": 0,
                },
                {
                    "Genus": "$Codex_Ent_Stratum_Genus_Name;",
                    "Genus_Localised": "Stratum",
                    "Species": "$Codex_Ent_Stratum_02_Name;",
                    "Species_Localised": "Stratum Tectonicas",
                    "Value": 19010800, "Bonus": 0,
                },
            ],
        },
    ),
    EventSpec(
        event="Promotion",
        category="milestones",
        extract=_extract_promotion,
        sample={"Explore": 8},
    ),
    EventSpec(
        event="CommunityGoalReward",
        category="milestones",
        extract=_extract_cg_reward,
        amount_field="amount",
        sample={
            "CGID": 726, "Name": "Alliance Research Initiative",
            "System": "Alioth", "Reward": 42000000,
        },
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


def event_names() -> list:
    """Registered events, grouped by category order for menus."""
    return [
        spec.event
        for category in CATEGORY_ORDER
        for spec in _SPEC_LIST
        if spec.category == category
    ]

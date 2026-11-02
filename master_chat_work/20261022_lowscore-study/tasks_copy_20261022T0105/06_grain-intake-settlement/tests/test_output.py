import ast
import csv
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from rewardkit import criteria, criterion


FLAG_CHAIN_TARE = 0x0001
FLAG_DOCKAGE_ECHO = 0x0002
FLAG_ROLE_LOOKBACK = 0x0004
FLAG_BAND_TIER_SHIFT = 0x0008
FLAG_TESTWEIGHT_FLOOR = 0x0010
FLAG_CUSTOM_HAUL = 0x0020
FLAG_TARE_DELTA = 0x0040
FLAG_TESTWEIGHT_ORDER = 0x0080
FLAG_VOID_ABSOLVES = 0x0100
FLAG_COUNT_BIAS = 0x0200
FLAG_COMMODITY_ALIAS = 0x0400
FLAG_EMBARGO_SPAN = 0x0800
FLAG_SCRAP_CARRY = 0x1000
ALL_FLAGS = 0x1FFF

COMMODITY_ORDER = ["wheat", "barley", "canola", "oats", "corn", "milo", "rye"]
TICKET_FIELDS = ("action", "bin", "card", "grader", "gross", "hauler", "seq", "testweight")
TICKET_ACTIONS = ("weigh", "tare", "settle", "void")


def _read_csv(path):
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _strict_int(value):
    # JSON true and false load as Python bools, which are ints; the screen refuses them.
    return type(value) is int


class _KeyPairs(list):
    """A JSON object as its key/value pairs in written order."""


def _screen_one(raw, bins, graders, haulers):
    """Pass one of intake screening: one raw line on its own, or None when set aside."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    try:
        # Keep the raw key/value pairs so a key named twice is visible; a plain
        # json.loads would silently keep the last value.
        parsed = json.loads(text, object_pairs_hook=_KeyPairs)
    except ValueError:
        return None
    if not isinstance(parsed, _KeyPairs):
        return None
    names = [name for name, _value in parsed]
    if len(set(names)) != len(names):
        return None
    row = dict(parsed)
    for field in TICKET_FIELDS:
        if field not in row:
            return None
    for field in ("action", "bin", "card", "grader", "hauler"):
        if not isinstance(row[field], str):
            return None
    if not _strict_int(row["seq"]) or row["seq"] < 1:
        return None
    if not _strict_int(row["gross"]) or row["gross"] < 0:
        return None
    if not _strict_int(row["testweight"]) or row["testweight"] < 1:
        return None
    if row["action"] not in TICKET_ACTIONS:
        return None
    if row["bin"] not in bins or row["grader"] not in graders or row["hauler"] not in haulers:
        return None
    return {field: row[field] for field in TICKET_FIELDS}


def screen_tickets(blob, bins, graders, haulers):
    """All three screening passes over the raw bytes of tickets.jsonl."""
    kept = []
    malformed = 0
    for raw in blob.split(b"\n"):
        if not raw.strip():
            continue
        row = _screen_one(raw, bins, graders, haulers)
        if row is None:
            malformed += 1
        else:
            kept.append(row)
    groups = {}
    for row in kept:
        groups.setdefault(row["seq"], []).append(row)
    singles = []
    conflicted = 0
    for seq in sorted(groups):
        copies = groups[seq]
        if all(copy == copies[0] for copy in copies):
            singles.append(copies)
        else:
            conflicted += len(copies)
    # Pass three: one card on one bin is settled once; a later seq carrying the
    # same bin and card is a re-entry and every line of it is set aside.
    claimed = set()
    tickets = []
    retransmitted = 0
    reentered = 0
    for copies in singles:
        slip = (copies[0]["bin"], copies[0]["card"])
        if slip in claimed:
            reentered += len(copies)
            continue
        claimed.add(slip)
        tickets.append(copies[0])
        retransmitted += len(copies) - 1
    screened = {"conflicted": conflicted, "malformed": malformed,
                "reentered": reentered, "retransmitted": retransmitted}
    return tickets, screened


def load_corpus(data_dir, prefix=""):
    with open(os.path.join(data_dir, prefix + "manifest.json"), "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    dryers = {}
    for row in _read_csv(os.path.join(data_dir, prefix + "dryers.csv")):
        dryers[row["dryer"]] = {
            "make": row["make"],
            "tare_base": int(row["tare_base"]),
        }
    contracts = {}
    for row in _read_csv(os.path.join(data_dir, prefix + "contracts.csv")):
        contracts[row["contract"]] = {
            "family": row["family"],
            "lots": int(row["lots"]),
        }
    graders = {}
    for row in _read_csv(os.path.join(data_dir, prefix + "graders.csv")):
        graders[row["grader"]] = {"role": row["role"]}
    haulers = {}
    for row in _read_csv(os.path.join(data_dir, prefix + "haulers.csv")):
        haulers[row["hauler"]] = {"class": row["class"]}
    bins = {}
    for row in _read_csv(os.path.join(data_dir, prefix + "bins.csv")):
        bins[row["bin"]] = {
            "dryer": row["dryer"],
            "contract": row["contract"],
            "commodity": row["commodity"],
            "tier": int(row["tier"]),
        }
    with open(os.path.join(data_dir, prefix + "tickets.jsonl"), "rb") as handle:
        blob = handle.read()
    tickets, screened = screen_tickets(blob, bins, graders, haulers)
    return {
        "mode": int(manifest["mode"]),
        "dryers": dryers,
        "contracts": contracts,
        "graders": graders,
        "haulers": haulers,
        "bins": bins,
        "tickets": tickets,
        "screened": screened,
    }


def _adjust_commodity(value, commodity):
    if commodity == "barley":
        return value - 6
    if commodity == "canola":
        return value * 4 // 5
    if commodity == "oats":
        return value + 9
    if commodity == "corn":
        return value // 2
    if commodity == "milo":
        return value - (value % 4)
    if commodity == "rye":
        return value * 6 // 5
    return value


def _adjust_family(value, family):
    if family == "track":
        return value * 4 // 5
    if family == "board":
        return value + 15
    if family == "hedge":
        return value * 8 // 5
    return value


def _band(bushels, lift):
    if bushels >= 260 + lift:
        return "prime"
    if bushels >= 130 + lift:
        return "mill"
    if bushels >= 45 + lift:
        return "feed"
    return "scrap"


def _role_limit(role):
    if role == "inspector":
        return 45
    if role == "apprentice":
        return 15
    if role == "relief":
        return 0
    return 30


def _status(action, band, dockage_before, role):
    if action == "tare" or action == "settle":
        return "open"
    if action == "void":
        return "voided"
    if band == "scrap":
        return "rejected"
    if dockage_before > _role_limit(role):
        return "flagged"
    return "clear"


def _charge(testweight, tier):
    charge = testweight // 40
    if tier == 3:
        charge = charge * 2
    return charge


def _tare_bases(dryers, bins, mode):
    values = {}
    for name, row in dryers.items():
        values[name] = row["tare_base"]
    carried = sorted({row["dryer"] for row in bins.values()})
    if mode & FLAG_TARE_DELTA and len(values) > 1 and carried:
        island = carried[-1]
        others = [values[name] for name in values if name != island]
        if others:
            values[island] = values[island] + min(others)
    return values


def _commodity_for(bin_row, mode):
    written = bin_row["commodity"]
    if not (mode & FLAG_COMMODITY_ALIAS):
        return written
    if written not in COMMODITY_ORDER:
        return written
    index = COMMODITY_ORDER.index(written)
    return COMMODITY_ORDER[(index + bin_row["tier"] + 5) % len(COMMODITY_ORDER)]


def _resolution_order(tickets, mode):
    order = sorted(tickets, key=lambda t: t["seq"])
    if mode & FLAG_COUNT_BIAS:
        order = order[:-3]
    if mode & FLAG_TESTWEIGHT_ORDER:
        order = sorted(order, key=lambda t: (t["testweight"], t["seq"]))
    return order


def resolve(corpus):
    mode = corpus["mode"]
    dryers = corpus["dryers"]
    contracts = corpus["contracts"]
    graders = corpus["graders"]
    haulers = corpus["haulers"]
    bins = corpus["bins"]
    tare_bases = _tare_bases(dryers, bins, mode)

    order = _resolution_order(corpus["tickets"], mode)

    floors = {}
    if mode & FLAG_TESTWEIGHT_FLOOR:
        for ticket in order:
            current = floors.get(ticket["bin"])
            if current is None or ticket["testweight"] < current:
                floors[ticket["bin"]] = ticket["testweight"]

    state = {}
    latest = {}
    settlements = []
    for ticket in order:
        bin_id = ticket["bin"]
        bin_row = bins[bin_id]
        if bin_id not in state:
            start = tare_bases[bin_row["dryer"]]
            previous = latest.get(bin_row["dryer"])
            if mode & FLAG_CHAIN_TARE and previous is not None:
                start = state[previous]["tare"]
            state[bin_id] = {
                "tare": start,
                "dockage": 0,
                "pending": 0,
                "strikes": 0,
                "grader": None,
                "scrapped": False,
                "previous": latest.get(bin_row["dryer"]),
            }
            latest[bin_row["dryer"]] = bin_id
        slot = state[bin_id]

        commodity = _commodity_for(bin_row, mode)
        family = contracts[bin_row["contract"]]["family"]
        role = graders[ticket["grader"]]["role"]
        if mode & FLAG_ROLE_LOOKBACK and slot["grader"] is not None:
            role = graders[slot["grader"]]["role"]
        testweight = ticket["testweight"]
        if mode & FLAG_TESTWEIGHT_FLOOR:
            testweight = floors[bin_id]
        lift = bin_row["tier"] * 20 if mode & FLAG_BAND_TIER_SHIFT else 0

        net = ticket["gross"] - slot["tare"]
        net = net * 1000 // testweight
        if net < 0:
            net = 0
        net = _adjust_commodity(net, commodity)
        if net < 0:
            net = 0
        net = _adjust_family(net, family)
        if net < 0:
            net = 0
        dockage_before = slot["dockage"]
        bushels = net - dockage_before
        if bushels < 0:
            bushels = 0
        band = _band(bushels, lift)
        status = _status(ticket["action"], band, dockage_before, role)
        if mode & FLAG_SCRAP_CARRY and slot["scrapped"] and status == "clear":
            status = "flagged"

        settlements.append({
            "action": ticket["action"],
            "band": band,
            "bin": bin_id,
            "bushels": bushels,
            "card": ticket["card"],
            "dockage_before": dockage_before,
            "grader": ticket["grader"],
            "seq": ticket["seq"],
            "status": status,
        })

        if status == "rejected":
            slot["strikes"] = slot["strikes"] + 1
        if ticket["action"] == "void" and mode & FLAG_VOID_ABSOLVES and slot["strikes"] > 0:
            slot["strikes"] = slot["strikes"] - 1
        slot["grader"] = ticket["grader"]
        slot["scrapped"] = band == "scrap"

        charge = 0
        if ticket["action"] == "weigh":
            charge = _charge(ticket["testweight"], bin_row["tier"])
        if mode & FLAG_CUSTOM_HAUL and haulers[ticket["hauler"]]["class"] == "custom":
            charge = 0
        if mode & FLAG_DOCKAGE_ECHO:
            carried = slot["pending"]
            slot["pending"] = charge
        else:
            carried = charge
        if ticket["action"] == "tare":
            slot["tare"] = ticket["gross"]
        elif ticket["action"] == "settle":
            slot["dockage"] = 0
            slot["pending"] = 0
            carried = 0
        dockage = slot["dockage"] + carried
        if dockage > 96:
            dockage = 96
        slot["dockage"] = dockage

    bin_rows = []
    for bin_id in sorted(bins):
        rows = [r for r in settlements if r["bin"] == bin_id]
        slot = state.get(bin_id)
        counted = [r for r in rows if r["status"] == "clear" or r["status"] == "flagged"]
        bushel_total = 0
        peak = 0
        best = None
        for row in counted:
            bushel_total = bushel_total + row["bushels"]
            if row["bushels"] > peak:
                peak = row["bushels"]
            if best is None:
                best = row
            elif row["bushels"] > best["bushels"]:
                best = row
            elif row["bushels"] == best["bushels"] and row["seq"] > best["seq"]:
                best = row
        strikes = slot["strikes"] if slot else 0
        dockage_end = slot["dockage"] if slot else 0
        weighed_strikes = strikes
        if mode & FLAG_EMBARGO_SPAN and slot is not None and slot["previous"] is not None:
            weighed_strikes = strikes + state[slot["previous"]]["strikes"]
        if weighed_strikes >= 3:
            disposition = "embargo"
        elif dockage_end > 35:
            disposition = "hold"
        else:
            disposition = "release"
        bands = {"feed": 0, "mill": 0, "prime": 0, "scrap": 0}
        for row in rows:
            bands[row["band"]] = bands[row["band"]] + 1
        bin_rows.append({
            "bands": bands,
            "bin": bin_id,
            "bushel_total": bushel_total,
            "disposition": disposition,
            "dockage_end": dockage_end,
            "flagged": sum(1 for r in rows if r["status"] == "flagged"),
            "peak": peak,
            "rejects": strikes,
            "tare_end": slot["tare"] if slot else tare_bases[bins[bin_id]["dryer"]],
            "tickets": len(rows),
            "top_card": best["card"] if best is not None else None,
            "weighed": sum(1 for r in rows if r["action"] == "weigh"),
        })

    by_band = {"feed": 0, "mill": 0, "prime": 0, "scrap": 0}
    by_status = {"clear": 0, "flagged": 0, "open": 0, "rejected": 0, "voided": 0}
    for row in settlements:
        by_band[row["band"]] = by_band[row["band"]] + 1
        by_status[row["status"]] = by_status[row["status"]] + 1

    top_bin = None
    top_total = None
    for row in bin_rows:
        if top_total is None or row["bushel_total"] > top_total:
            top_bin = row["bin"]
            top_total = row["bushel_total"]

    elevator = {
        "bins": len(bin_rows),
        "bushel_total": sum(r["bushel_total"] for r in bin_rows),
        "by_band": by_band,
        "by_status": by_status,
        "embargoed": sorted(r["bin"] for r in bin_rows if r["disposition"] == "embargo"),
        "screened": dict(corpus["screened"]),
        "tickets": len(settlements),
        "top_bin": top_bin,
    }
    return settlements, bin_rows, elevator


def derive(data_dir, prefix=""):
    return resolve(load_corpus(data_dir, prefix))


def render_settlements(settlements):
    parts = []
    for row in settlements:
        parts.append(json.dumps(row, sort_keys=True, separators=(",", ":")))
        parts.append("\n")
    return "".join(parts)


def render_document(document):
    return json.dumps(document, sort_keys=True, indent=2) + "\n"


def bin_digest(settlements, bin_rows, bin_id):
    rows = [row for row in settlements if row["bin"] == bin_id]
    body = render_settlements(rows)
    for row in bin_rows:
        if row["bin"] == bin_id:
            body = body + render_document(row)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def run_digest(settlements, bin_rows, elevator):
    body = (render_settlements(settlements)
            + render_document({"bins": bin_rows})
            + render_document(elevator))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


SAMPLE_SEED = 6250831
EXAMPLE_A_SEED = 4410056
EXAMPLE_B_SEED = 4410062

_BASE_DRYERS = [
    ("DRY-A", "rotary", 140),
    ("DRY-B", "tower", 60),
    ("DRY-C", "column", 100),
    ("DRY-D", "rotary", 80),
]
_BASE_CONTRACTS = [
    ("CON-B1", "basis", 2),
    ("CON-B2", "basis", 3),
    ("CON-T1", "track", 2),
    ("CON-T2", "track", 5),
    ("CON-D1", "board", 3),
    ("CON-H1", "hedge", 2),
    ("CON-H2", "hedge", 5),
]
_BASE_GRADERS = [
    ("GR-01", "weighman"),
    ("GR-02", "weighman"),
    ("GR-03", "inspector"),
    ("GR-04", "apprentice"),
    ("GR-05", "relief"),
]
_BASE_HAULERS = [
    ("HL-01", "line"),
    ("HL-02", "line"),
    ("HL-03", "custom"),
    ("HL-04", "spot"),
]
_COMMODITIES = ["wheat", "barley", "canola", "oats", "corn", "milo", "rye"]
_ROLES = ["weighman", "inspector", "apprentice", "relief"]
_CLASSES = ["line", "custom", "spot"]
_PROBE_GROSS = [303, 404, 507, 608]
# Gross readings that put a band probe ticket exactly on each shifted band edge
# of its bin, so the size of the band lift is fixed by the bin digest alone.
_LIFT_PROBE_GROSS = {
    "BIN-43": (373, 374, 285, 307, 256, 275),
    "BIN-44": (439, 440, 334, 360, 299, 321),
    "BIN-45": (425, 426, 345, 392, 306, 307),
}


class _Rng:
    def __init__(self, seed):
        self.state = (seed * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF

    def draw(self):
        self.state = (self.state * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        return (self.state >> 33) & 0x7FFFFFFF

    def below(self, limit):
        return self.draw() % limit

    def between(self, low, high):
        return low + self.below(high - low + 1)

    def pick(self, items):
        return items[self.below(len(items))]


class _Case:
    def __init__(self):
        self.dryers = list(_BASE_DRYERS)
        self.contracts = list(_BASE_CONTRACTS)
        self.graders = list(_BASE_GRADERS)
        self.haulers = list(_BASE_HAULERS)
        self.bins = []
        self.tickets = []
        self.seq = 0
        self.state = {}
        self.cards = {}

    def tare_base(self, dryer):
        for name, _make, value in self.dryers:
            if name == dryer:
                return value
        raise KeyError(dryer)

    def family(self, contract):
        for name, value, _lots in self.contracts:
            if name == contract:
                return value
        raise KeyError(contract)

    def bin(self, bin_id, dryer, contract, commodity, tier):
        self.bins.append((bin_id, dryer, contract, commodity, tier))
        self.state[bin_id] = {
            "tare": self.tare_base(dryer),
            "dockage": 0,
            "commodity": commodity,
            "family": self.family(contract),
            "tier": tier,
        }
        self.cards[bin_id] = 0
        return bin_id

    def _card(self, bin_id):
        index = self.cards[bin_id]
        self.cards[bin_id] = index + 1
        return "%s%02d" % ("ABCDEFGH"[index // 12], (index % 12) + 1)

    def ticket(self, bin_id, grader, action, gross, testweight, hauler="HL-01"):
        slot = self.state[bin_id]
        self.seq += 1
        self.tickets.append({
            "seq": self.seq,
            "bin": bin_id,
            "card": self._card(bin_id),
            "grader": grader,
            "hauler": hauler,
            "action": action,
            "gross": gross,
            "testweight": testweight,
        })
        if action == "tare":
            slot["tare"] = gross
        elif action == "settle":
            slot["dockage"] = 0
        elif action == "weigh":
            charge = testweight // 40
            if slot["tier"] == 3:
                charge = charge * 2
            dockage = slot["dockage"] + charge
            if dockage > 96:
                dockage = 96
            slot["dockage"] = dockage
        return self.seq

    def target(self, bin_id, grader, bushels, testweight, action="weigh", hauler="HL-01"):
        slot = self.state[bin_id]
        if slot["commodity"] != "wheat" or slot["family"] != "basis":
            raise ValueError("target inversion is defined on a plain bin only")
        net = bushels + slot["dockage"]
        product = net * testweight
        if product % 1000 != 0:
            raise ValueError("testweight %d cannot express net %d exactly" % (testweight, net))
        return self.ticket(bin_id, grader, action, slot["tare"] + product // 1000,
                           testweight, hauler)

    def flat(self, bin_id, grader, action, testweight, hauler="HL-01"):
        return self.ticket(bin_id, grader, action, self.state[bin_id]["tare"],
                           testweight, hauler)


def _spine(case):
    case.bin("BIN-01", "DRY-A", "CON-B1", "wheat", 1)
    for bushels in (260, 259, 130, 129, 45, 44):
        case.target("BIN-01", "GR-01", bushels, 1000, "void")
    case.target("BIN-01", "GR-01", 200, 1000)

    for bin_id, commodity in (
        ("BIN-02", "barley"),
        ("BIN-03", "canola"),
        ("BIN-04", "oats"),
        ("BIN-05", "corn"),
        ("BIN-06", "milo"),
        ("BIN-07", "rye"),
        ("BIN-08", "wheat"),
    ):
        case.bin(bin_id, "DRY-A", "CON-B1", commodity, 1)
        for gross in _PROBE_GROSS:
            case.ticket(bin_id, "GR-01", "weigh", gross, 1000)

    for bin_id, contract in (
        ("BIN-09", "CON-T1"),
        ("BIN-10", "CON-D1"),
        ("BIN-11", "CON-H1"),
        ("BIN-12", "CON-B2"),
        ("BIN-30", "CON-T2"),
        ("BIN-31", "CON-H2"),
    ):
        case.bin(bin_id, "DRY-B", contract, "wheat", 1)
        for gross in _PROBE_GROSS:
            case.ticket(bin_id, "GR-01", "weigh", gross - 40, 1000)

    case.bin("BIN-13", "DRY-A", "CON-B2", "wheat", 1)
    case.target("BIN-13", "GR-01", 300, 1800)
    case.target("BIN-13", "GR-03", 100, 1000)
    case.flat("BIN-13", "GR-01", "settle", 1000)
    case.target("BIN-13", "GR-01", 300, 1840)
    case.target("BIN-13", "GR-03", 100, 1000)

    case.bin("BIN-14", "DRY-A", "CON-B2", "wheat", 1)
    case.target("BIN-14", "GR-01", 200, 600)
    case.target("BIN-14", "GR-04", 100, 1000)
    case.flat("BIN-14", "GR-01", "settle", 1000)
    case.target("BIN-14", "GR-01", 200, 640)
    case.target("BIN-14", "GR-04", 100, 1000)

    case.bin("BIN-15", "DRY-A", "CON-B2", "wheat", 1)
    case.target("BIN-15", "GR-05", 100, 1000)
    case.flat("BIN-15", "GR-01", "settle", 1000)
    case.target("BIN-15", "GR-01", 200, 40)
    case.target("BIN-15", "GR-05", 100, 1000)

    case.bin("BIN-16", "DRY-A", "CON-B2", "wheat", 1)
    case.target("BIN-16", "GR-01", 300, 1200)
    case.target("BIN-16", "GR-02", 100, 1000)
    case.flat("BIN-16", "GR-01", "settle", 1000)
    case.target("BIN-16", "GR-01", 300, 1240)
    case.target("BIN-16", "GR-02", 100, 1000)

    case.bin("BIN-17", "DRY-B", "CON-B2", "wheat", 1)
    for _step in range(3):
        case.flat("BIN-17", "GR-01", "weigh", 1000)

    case.bin("BIN-18", "DRY-B", "CON-B2", "wheat", 1)
    case.target("BIN-18", "GR-01", 300, 1560)

    case.bin("BIN-19", "DRY-B", "CON-B2", "wheat", 1)
    case.target("BIN-19", "GR-01", 300, 1500)

    case.bin("BIN-20", "DRY-B", "CON-B2", "wheat", 1)
    case.target("BIN-20", "GR-01", 300, 2000)
    case.target("BIN-20", "GR-01", 300, 2000)
    case.target("BIN-20", "GR-01", 100, 1000)

    case.bin("BIN-21", "DRY-D", "CON-B2", "wheat", 3)
    case.target("BIN-21", "GR-01", 200, 1000)
    case.target("BIN-21", "GR-03", 100, 1000)

    case.bin("BIN-22", "DRY-D", "CON-B2", "wheat", 2)
    case.target("BIN-22", "GR-01", 200, 1000)
    case.target("BIN-22", "GR-04", 100, 1000)

    case.bin("BIN-23", "DRY-A", "CON-B2", "wheat", 1)
    case.flat("BIN-23", "GR-01", "settle", 1000)
    case.flat("BIN-23", "GR-01", "void", 1000)
    case.target("BIN-23", "GR-01", 400, 1600)
    case.flat("BIN-23", "GR-01", "weigh", 1000)
    case.target("BIN-23", "GR-01", 100, 1000)
    case.flat("BIN-23", "GR-02", "void", 800)

    case.bin("BIN-24", "DRY-A", "CON-B2", "wheat", 1)
    case.ticket("BIN-24", "GR-01", "tare", 150, 1000)
    case.target("BIN-24", "GR-01", 60, 1000)
    case.ticket("BIN-24", "GR-03", "tare", 220, 1000)
    case.target("BIN-24", "GR-01", 90, 1000)

    case.bin("BIN-25", "DRY-A", "CON-B2", "wheat", 1)
    case.target("BIN-25", "GR-01", 150, 1000)
    case.target("BIN-25", "GR-01", 150, 1000)
    case.target("BIN-25", "GR-01", 100, 1000)

    for bin_id in ("BIN-26", "BIN-27"):
        case.bin(bin_id, "DRY-A", "CON-B2", "wheat", 1)
        for bushels in (1200, 1320, 1440, 1560):
            case.target(bin_id, "GR-02", bushels, 1000)

    case.bin("BIN-28", "DRY-A", "CON-B1", "wheat", 1)
    case.ticket("BIN-28", "GR-01", "tare", 130, 1000)
    case.ticket("BIN-28", "GR-01", "void", 300, 1000)

    case.bin("BIN-29", "DRY-A", "CON-B1", "wheat", 1)
    for testweight in (500, 800, 1000, 2000, 2500):
        case.ticket("BIN-29", "GR-01", "void", 300, testweight)

    case.bin("BIN-32", "DRY-D", "CON-B2", "wheat", 2)
    case.flat("BIN-32", "GR-01", "weigh", 1000)
    case.flat("BIN-32", "GR-05", "weigh", 1200)
    case.target("BIN-32", "GR-01", 250, 1000)

    case.bin("BIN-33", "DRY-C", "CON-B1", "barley", 1)
    case.ticket("BIN-33", "GR-02", "weigh", 460, 900)
    case.ticket("BIN-33", "GR-04", "void", 300, 1500)
    case.ticket("BIN-33", "GR-02", "weigh", 520, 1100)

    case.bin("BIN-34", "DRY-A", "CON-B2", "wheat", 1)
    for step in range(10):
        case.ticket("BIN-34", ("GR-01", "GR-03", "GR-04", "GR-05")[step % 4],
                    "weigh", 500, 1000,
                    ("HL-01", "HL-03", "HL-02", "HL-03", "HL-04")[step % 5])

    case.bin("BIN-35", "DRY-B", "CON-B2", "wheat", 1)
    for step in range(6):
        case.ticket("BIN-35", "GR-01", "weigh" if step % 2 == 0 else "void", 0, 1000)

    case.bin("BIN-36", "DRY-B", "CON-B2", "wheat", 1)
    for _step in range(2):
        case.ticket("BIN-36", "GR-01", "weigh", 0, 4000)

    case.bin("BIN-37", "DRY-B", "CON-B2", "wheat", 1)
    case.ticket("BIN-37", "GR-01", "weigh", 0, 4050)

    case.bin("BIN-38", "DRY-A", "CON-B2", "wheat", 1)
    case.target("BIN-38", "GR-01", 300, 1200, "weigh", "HL-03")
    case.target("BIN-38", "GR-02", 300, 1200, "weigh", "HL-03")
    case.target("BIN-38", "GR-02", 100, 1000, "weigh", "HL-01")

    case.bin("BIN-42", "DRY-A", "CON-B2", "wheat", 1)
    for step in range(8):
        case.ticket("BIN-42", ("GR-03", "GR-05", "GR-01", "GR-04")[step % 4],
                    "weigh", 900 - 40 * step, 1000)

    case.bin("BIN-40", "DRY-A", "CON-B2", "corn", 1)
    case.ticket("BIN-40", "GR-01", "weigh", 700, 1000)
    case.ticket("BIN-40", "GR-05", "weigh", 500, 1000)
    case.ticket("BIN-40", "GR-01", "void", 300, 1500)
    case.ticket("BIN-40", "GR-03", "weigh", 260, 1000)

    case.bin("BIN-41", "DRY-C", "CON-B1", "milo", 3)
    case.ticket("BIN-41", "GR-01", "weigh", 800, 1000)
    case.ticket("BIN-41", "GR-04", "weigh", 600, 1200, "HL-03")
    case.ticket("BIN-41", "GR-02", "weigh", 200, 1000)
    case.ticket("BIN-41", "GR-01", "settle", 140, 1000)
    case.ticket("BIN-41", "GR-02", "weigh", 900, 2000)

    # Calibration bins. BIN-43 to BIN-45 sit a ticket on each shifted band edge and
    # one bushel under it at every tier, which fixes the size of the band lift.
    # BIN-46 and BIN-47 end on dockage 35 and 36, which fixes the hold threshold.
    # BIN-48 and BIN-49 send a figure below zero at the tare stage and at the
    # commodity stage on a contract that reacts to it, which fixes both clamps.
    for bin_id, dryer, tier in (
        ("BIN-43", "DRY-D", 1),
        ("BIN-44", "DRY-D", 2),
        ("BIN-45", "DRY-C", 3),
    ):
        case.bin(bin_id, dryer, "CON-B1", "wheat", tier)
        for gross in _LIFT_PROBE_GROSS[bin_id]:
            case.ticket(bin_id, "GR-01", "weigh", gross, 1000)

    case.bin("BIN-46", "DRY-D", "CON-B1", "wheat", 1)
    case.flat("BIN-46", "GR-01", "weigh", 1400)

    case.bin("BIN-47", "DRY-C", "CON-B1", "wheat", 1)
    case.flat("BIN-47", "GR-01", "weigh", 1440)

    case.bin("BIN-48", "DRY-B", "CON-D1", "barley", 1)
    case.ticket("BIN-48", "GR-01", "weigh", case.tare_base("DRY-B") + 3, 1000)
    case.ticket("BIN-48", "GR-01", "weigh", 0, 1000)

    case.bin("BIN-49", "DRY-B", "CON-B1", "oats", 1)
    case.ticket("BIN-49", "GR-01", "weigh", case.tare_base("DRY-B") - 5, 1000)

    case.bin("BIN-39", "DRY-A", "CON-B2", "wheat", 1)
    case.target("BIN-39", "GR-01", 20, 1000)
    case.target("BIN-39", "GR-01", 300, 1000)
    case.target("BIN-39", "GR-01", 10, 1000)
    case.target("BIN-39", "GR-01", 400, 1000)

    # BIN-01 closes the spine with two light voids. In a screened intake the
    # re-entry that resolves sits above them, so under the count bias the three
    # make up the dropped tail, which fixes whether the testweight floor reads it.
    for _step in range(2):
        case.flat("BIN-01", "GR-01", "void", 500)


def _extras(case, seed):
    rng = _Rng(seed ^ 0x5A17)
    for index in range(1 + rng.below(2)):
        case.dryers.append((
            "DRY-%s" % chr(ord("P") + index),
            rng.pick(["rotary", "column", "tower"]),
            rng.between(40, 200),
        ))
    for index in range(1 + rng.below(3)):
        case.graders.append(("GR-%02d" % (20 + index), rng.pick(_ROLES)))
    for index in range(1 + rng.below(2)):
        case.haulers.append(("HL-%02d" % (20 + index), rng.pick(_CLASSES)))

    dryers = [row[0] for row in case.dryers]
    contracts = [row[0] for row in case.contracts]
    graders = [row[0] for row in case.graders]
    haulers = [row[0] for row in case.haulers]
    for index in range(2 + rng.below(4)):
        bin_id = "BIN-%02d" % (50 + index)
        dryer = rng.pick(dryers)
        case.bin(bin_id, dryer, rng.pick(contracts), rng.pick(_COMMODITIES), rng.between(1, 3))
        base = case.tare_base(dryer)
        for _step in range(3 + rng.below(3)):
            case.ticket(
                bin_id,
                rng.pick(graders),
                rng.pick(["weigh", "weigh", "weigh", "weigh", "tare", "settle", "void"]),
                base + rng.between(0, 300),
                40 * rng.between(25, 50),
                rng.pick(haulers),
            )

    # One voided bulk load far past the range a double holds exactly, so the chain
    # has to stay in whole number arithmetic to settle its bushels. A void is never
    # counted, so the load leaves the bin totals and the top bin tie break alone.
    bulk = case.bins[-1][0]
    case.ticket(
        bulk,
        rng.pick(graders),
        "void",
        case.state[bulk]["tare"] + (1 << 60) + 1 + 2 * rng.below(1 << 20),
        997 + rng.below(500),
        rng.pick(haulers),
    )


def build_case(seed, extra, keep=None):
    case = _Case()
    _spine(case)
    if extra:
        _extras(case, seed)
    if keep is not None:
        chosen = set(keep)
        case.bins = [row for row in case.bins if row[0] in chosen]
        case.tickets = [row for row in case.tickets if row["bin"] in chosen]
    return case


def _shuffled(tickets, seed):
    order = list(tickets)
    rng = _Rng(seed ^ 0x2C91)
    index = len(order) - 1
    while index > 0:
        swap = rng.below(index + 1)
        order[index], order[swap] = order[swap], order[index]
        index -= 1
    return order


def _line(row, **dump):
    if not dump:
        dump = {"sort_keys": True, "separators": (",", ":")}
    return json.dumps(row, **dump).encode("utf-8")


def _noise_lines(case, seed):
    """Damaged, retransmitted and conflicting lines the scale house link adds to an intake.

    Every rule these lines exercise is written down in engine.md; the generator only
    decides how many of each kind fall where, from the corpus seed. Fresh seqs sit
    above the last real ticket, so a reading that trims the intake tail before
    screening differs from one that trims it after.
    """
    rng = _Rng(seed ^ 0x7E13)
    pool = sorted(case.tickets, key=lambda t: t["seq"])
    used = set()

    def fresh_pick():
        while True:
            candidate = rng.pick(pool)
            if candidate["seq"] not in used:
                used.add(candidate["seq"])
                return candidate

    lines = []
    for _copy in range(1 + rng.below(2)):
        lines.append(_line(fresh_pick()))
    for _copy in range(1 + rng.below(2)):
        row = fresh_pick()
        lines.append(_line(dict(reversed(sorted(row.items()))), separators=(",", ":")))
    for _copy in range(1 + rng.below(2)):
        relay = dict(fresh_pick())
        relay["relay"] = "LINK-%d" % (1 + rng.below(4))
        lines.append(_line(relay))
    for _copy in range(1 + rng.below(2)):
        lines.append(_line(fresh_pick(), sort_keys=True))
    twice = fresh_pick()
    for _copy in range(2):
        lines.append(_line(twice))

    graders = [row[0] for row in case.graders]
    for index in range(1 + rng.below(3)):
        clash = fresh_pick()
        bumped = dict(clash)
        if index % 2 == 0:
            bumped["gross"] = clash["gross"] + 1 + rng.below(40)
        else:
            bumped["grader"] = rng.pick([g for g in graders if g != clash["grader"]])
        lines.append(_line(bumped))
        if index == 0:
            lines.append(_line(clash))
            orphaned = clash

    for _copy in range(1 + rng.below(2)):
        damaged = dict(fresh_pick())
        damaged["testweight"] = str(damaged["testweight"])
        lines.append(_line(damaged))

    bins = [row[0] for row in case.bins]
    haulers = [row[0] for row in case.haulers]
    kinds = ["orphan_bin", "orphan_grader", "orphan_hauler", "bad_action", "zero_testweight",
             "bool_testweight", "string_gross", "negative_gross", "missing_card", "string_seq",
             "truncated", "array", "bad_utf8", "null_bin"]
    chosen = [kind for kind in kinds if rng.below(4) != 0]
    for kind in ("zero_testweight", "bool_testweight", "truncated"):
        if kind not in chosen:
            chosen.append(kind)
    chosen = _shuffled(chosen, seed ^ 0x51)
    top = pool[-1]["seq"] if pool else 0
    for index, kind in enumerate(chosen):
        row = {
            "seq": top + 1 + index,
            "bin": rng.pick(bins),
            "card": "Z%02d" % (index + 1),
            "grader": rng.pick(graders),
            "hauler": rng.pick(haulers),
            "action": rng.pick(["weigh", "weigh", "tare", "void"]),
            "gross": 200 + rng.below(400),
            "testweight": 40 * rng.between(25, 50),
        }
        if kind == "orphan_bin":
            row["bin"] = "BIN-98"
        elif kind == "orphan_grader":
            row["grader"] = "GR-77"
        elif kind == "orphan_hauler":
            row["hauler"] = "HL-66"
        elif kind == "bad_action":
            row["action"] = "reweigh"
        elif kind == "zero_testweight":
            row["testweight"] = 0
        elif kind == "bool_testweight":
            row["testweight"] = True
        elif kind == "string_gross":
            row["gross"] = str(row["gross"])
        elif kind == "negative_gross":
            row["gross"] = -1 - rng.below(9)
        elif kind == "missing_card":
            del row["card"]
        elif kind == "string_seq":
            row["seq"] = str(row["seq"])
        elif kind == "null_bin":
            row["bin"] = None
        if kind == "truncated":
            whole = _line(row)
            lines.append(whole[: len(whole) // 2])
        elif kind == "array":
            lines.append(_line([row["seq"], row["bin"], row["gross"]]))
        elif kind == "bad_utf8":
            lines.append(_line(row).replace(b'"Z', b'"\xff\xfeZ'))
        else:
            lines.append(_line(row))
    # Relayed copies of real tickets that re-serialised one integer field as a JSON
    # number with a fraction or an exponent. The value is still whole, and Python
    # compares 412.0 equal to 412, but screening sets the line aside as damaged.
    for index in range(1 + rng.below(2)):
        row = fresh_pick()
        field = ("gross", "seq", "testweight")[rng.below(3)]
        body = _line(row)
        token = b'"%s":%d' % (field.encode("utf-8"), row[field])
        spelled = token + (b".0" if index % 2 == 0 else b"e0")
        for tail in (b",", b"}"):
            if token + tail in body:
                body = body.replace(token + tail, spelled + tail, 1)
                break
        lines.append(body)

    # Relayed copies of real tickets that name one key twice. A plain json.loads
    # keeps the last value, which makes the first copy look like one more
    # retransmission and the second, whose repeated testweight disagrees, look like
    # a conflict that would set the real ticket aside. The third repeats a key
    # outside the eight, which a check confined to the eight lets through as a
    # retransmission. Screening sets all three aside as damaged and the real
    # tickets resolve.
    for field in ("gross", "testweight"):
        row = fresh_pick()
        value = row[field] if field == "gross" else row[field] + 40 * (1 + rng.below(5))
        body = _line(row)
        lines.append(body[:-1] + b',"%s":%d}' % (field.encode("utf-8"), value))
    relay = dict(fresh_pick())
    relay["relay"] = "LINK-%d" % (1 + rng.below(4))
    body = _line(relay)
    lines.append(body[:-1] + b',"relay":"LINK-%d"}' % (5 + rng.below(4)))

    # A relay that re-escaped the card as \\u sequences. The eight values are
    # unchanged, so it is a retransmission. A blank line of spaces and a tab
    # follows it.
    row = fresh_pick()
    escaped = "".join("\\u%04x" % ord(letter) for letter in row["card"])
    body = _line(row).replace(
        b'"card":"%s"' % row["card"].encode("utf-8"),
        b'"card":"%s"' % escaped.encode("utf-8"), 1)
    lines.append(body)
    lines.append(b" \t ")

    # Re-entries: a real ticket's bin and card sent again under a fresh seq above
    # every real one. The first carries a new gross and grader, the second arrives
    # twice with a new testweight; the earlier seq keeps the card, so every line of
    # both is set aside. The third re-enters the card of the ticket whose seq the
    # first clash put in conflict: that seq claims nothing, so the re-entry is the
    # first claim on its card and resolves.
    after = top + len(chosen) + 1
    first = dict(fresh_pick())
    first["seq"] = after + 1
    first["gross"] = first["gross"] + 1 + rng.below(60)
    first["grader"] = rng.pick(graders)
    lines.append(_line(first))
    second = dict(fresh_pick())
    second["seq"] = after + 2
    second["testweight"] = second["testweight"] + 40 * (1 + rng.below(5))
    for _copy in range(2):
        lines.append(_line(second))
    claimant = dict(orphaned)
    claimant["seq"] = after
    claimant["gross"] = claimant["gross"] + 1 + rng.below(60)
    lines.append(_line(claimant))
    return lines


def write_case(root, seed, mode, extra=True, keep=None, prefix="", noise=False):
    case = build_case(seed, extra, keep)
    os.makedirs(root, exist_ok=True)

    def emit(name, body):
        if isinstance(body, str):
            body = body.encode("utf-8")
        with open(os.path.join(root, prefix + name), "wb") as handle:
            handle.write(body)

    lines = ["dryer,make,tare_base"]
    for name, make, value in case.dryers:
        lines.append("%s,%s,%d" % (name, make, value))
    emit("dryers.csv", "\n".join(lines) + "\n")

    lines = ["contract,family,lots"]
    for name, value, lots in case.contracts:
        lines.append("%s,%s,%d" % (name, value, lots))
    emit("contracts.csv", "\n".join(lines) + "\n")

    lines = ["grader,role"]
    for name, role in case.graders:
        lines.append("%s,%s" % (name, role))
    emit("graders.csv", "\n".join(lines) + "\n")

    lines = ["hauler,class"]
    for name, klass in case.haulers:
        lines.append("%s,%s" % (name, klass))
    emit("haulers.csv", "\n".join(lines) + "\n")

    lines = ["bin,dryer,contract,commodity,tier"]
    for bin_id, dryer, contract, commodity, tier in case.bins:
        lines.append("%s,%s,%s,%s,%d" % (bin_id, dryer, contract, commodity, tier))
    emit("bins.csv", "\n".join(lines) + "\n")

    raw = [_line(row) for row in case.tickets]
    if noise:
        raw.extend(_noise_lines(case, seed))
    order = _shuffled(raw, seed)
    # Lines of damaged bytes are moved out of the first 8 KiB, so a tool that sniffs
    # the head of the file to tell text from binary still sweeps it as text.
    head, early = 0, []
    for index, line in enumerate(order):
        if head >= 8192:
            break
        head += len(line) + 1
        try:
            line.decode("utf-8")
        except UnicodeDecodeError:
            early.append(index)
    order = [line for index, line in enumerate(order) if index not in early] + [order[i] for i in early]
    emit("tickets.jsonl", b"".join(line + b"\n" for line in order))

    header = {
        "intake": "INT-%d" % (seed % 1000000),
        "mode": mode,
        "declared_tickets": len(raw),
        "bin_digests": {},
        "run_digest": "",
    }
    emit("manifest.json", json.dumps(header, sort_keys=True, indent=2) + "\n")

    settlements, bin_rows, elevator = resolve(load_corpus(root, prefix))
    header["bin_digests"] = {
        row[0]: bin_digest(settlements, bin_rows, row[0]) for row in case.bins}
    header["run_digest"] = run_digest(settlements, bin_rows, elevator)
    emit("manifest.json", json.dumps(header, sort_keys=True, indent=2) + "\n")
    return case


REPORTS = ("settlements.jsonl", "binroll.json", "elevator.json")

BASE_SEEDS = (6610011, 6610022)
SCREEN_SEED = 6610033
BIT_SEEDS = (7710011, 7710022, 7710033, 7710044, 7710055, 7710066, 7710077,
             7710088, 7710099, 7710110, 7710121, 7710132, 7710143)
# One all but one corpus per mode bit, in bit order.
EXCEPT_SEEDS = (8810011, 8810077, 8810022, 8810088, 8810033, 8810044, 8810099,
                8810110, 8810055, 8810121, 8810132, 8810143, 8810066)
FULL_SEED = 9910011
ALIAS_SEED = 9910099
REPEAT_SEED = 4410011

MODE_BITS = [
    ("chain_tare", FLAG_CHAIN_TARE),
    ("dockage_echo", FLAG_DOCKAGE_ECHO),
    ("role_lookback", FLAG_ROLE_LOOKBACK),
    ("band_tier_shift", FLAG_BAND_TIER_SHIFT),
    ("testweight_floor", FLAG_TESTWEIGHT_FLOOR),
    ("custom_haul", FLAG_CUSTOM_HAUL),
    ("tare_delta", FLAG_TARE_DELTA),
    ("testweight_order", FLAG_TESTWEIGHT_ORDER),
    ("void_absolves", FLAG_VOID_ABSOLVES),
    ("count_bias", FLAG_COUNT_BIAS),
    ("commodity_alias", FLAG_COMMODITY_ALIAS),
    ("embargo_span", FLAG_EMBARGO_SPAN),
    ("scrap_carry", FLAG_SCRAP_CARRY),
]

_TMP_ROOT = os.path.realpath(tempfile.gettempdir())
_RUNS = {}


def _script(workspace):
    return os.path.join(str(workspace), "out", "settle.py")


def _inside_sandbox(path):
    resolved = os.path.realpath(path)
    return resolved != _TMP_ROOT and resolved.startswith(_TMP_ROOT + os.sep)


def _open_up(path):
    node = os.path.realpath(path)
    while _inside_sandbox(node):
        try:
            os.chmod(node, (os.stat(node).st_mode & 0o7777) | 0o111 | 0o044)
        except OSError:
            pass
        node = os.path.dirname(node)


def _grant_read(path):
    try:
        os.chmod(path, (os.stat(path).st_mode & 0o7777) | 0o044)
    except OSError:
        pass


def _demoted(argv):
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups", "--"] + argv
    return argv


def _terminate(proc):
    # start_new_session makes the child its own group leader, so its pid is the pgid.
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, AttributeError):
        pass
    try:
        proc.kill()
    except OSError:
        pass
    try:
        proc.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _launch(argv, scratch, budget=240):
    """Run the delivered program demoted; returns its exit code, or None on timeout."""
    stdout_path = os.path.join(scratch, "stdout.txt")
    stderr_path = os.path.join(scratch, "stderr.txt")
    env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": scratch,
        "TMPDIR": scratch,
        "LC_ALL": "C",
    }
    with open(stdout_path, "wb") as sink, open(stderr_path, "wb") as errsink:
        proc = subprocess.Popen(
            _demoted(argv),
            stdout=sink,
            stderr=errsink,
            stdin=subprocess.DEVNULL,
            env=env,
            start_new_session=True,
        )
        try:
            code = proc.wait(timeout=budget)
        except subprocess.TimeoutExpired:
            code = None
        # Kill the whole session group either way, so no child of the agent's
        # program outlives the check that started it.
        _terminate(proc)
        return code


def _run(workspace, label, seed, mode, extra=True, noise=False):
    if label in _RUNS:
        return _RUNS[label]
    script = _script(workspace)
    if not os.path.isfile(script):
        return None
    _open_up(script)
    _grant_read(os.path.dirname(script))
    _grant_read(script)
    work = tempfile.mkdtemp(prefix="gis-" + label + "-")
    data = os.path.join(work, "data")
    out = os.path.join(work, "out")
    scratch = os.path.join(work, "scratch")
    write_case(data, seed, mode, extra, None, "", noise)
    os.makedirs(out)
    os.makedirs(scratch)
    for node in (work, data, out, scratch):
        os.chmod(node, 0o777)
    for name in os.listdir(data):
        os.chmod(os.path.join(data, name), 0o644)
    code = _launch([sys.executable, script, data, out], scratch)
    _RUNS[label] = (data, out, scratch, code)
    return _RUNS[label]


def _expected(data):
    settlements, bin_rows, elevator = derive(data)
    return {
        "settlements.jsonl": render_settlements(settlements),
        "binroll.json": render_document({"bins": bin_rows}),
        "elevator.json": render_document(elevator),
    }


def _artifact(out, name):
    path = os.path.join(out, name)
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as handle:
        return handle.read()


def _matches(workspace, label, seed, mode, extra=True, noise=False):
    """True when the program exits 0 and writes all three reports byte for byte."""
    try:
        run = _run(workspace, label, seed, mode, extra, noise)
        if run is None or run[3] != 0:
            return False
        data, out = run[0], run[1]
        expected = _expected(data)
        for name in REPORTS:
            if _artifact(out, name) != expected[name].encode("utf-8"):
                return False
        return True
    except Exception:
        return False


def _delivered_source(workspace):
    script = _script(workspace)
    if not os.path.isfile(script):
        return None
    _grant_read(script)
    with open(script, "rb") as handle:
        return handle.read().decode("utf-8", "replace")


@criterion(description="the reusable program sits at /app/out/settle.py and parses as Python source")
def reusable_program_is_delivered(workspace: Path) -> bool:
    try:
        source = _delivered_source(workspace)
        if source is None or not source.strip():
            return False
        ast.parse(source)
        return True
    except Exception:
        return False


@criterion(description="an intake whose mode word is clear resolves exactly like the worked example runs")
def untrapped_run_alpha_resolves(workspace: Path) -> bool:
    return _matches(workspace, "base-a", BASE_SEEDS[0], 0)


@criterion(description="a second intake whose mode word is clear resolves through the base chain")
def untrapped_run_beta_resolves(workspace: Path) -> bool:
    return _matches(workspace, "base-b", BASE_SEEDS[1], 0)


@criterion(description="a mode zero intake carrying retransmitted, conflicting and damaged ticket lines is screened and resolves exactly")
def screened_intake_mode_zero_resolves(workspace: Path) -> bool:
    return _matches(workspace, "screen", SCREEN_SEED, 0, True, True)


@criterion(description="an intake carrying only the first mode bit resolves exactly")
def mode_bit_chain_tare(workspace: Path) -> bool:
    return _matches(workspace, "bit-00", BIT_SEEDS[0], MODE_BITS[0][1])


@criterion(description="an intake carrying only the second mode bit resolves exactly")
def mode_bit_dockage_echo(workspace: Path) -> bool:
    return _matches(workspace, "bit-01", BIT_SEEDS[1], MODE_BITS[1][1])


@criterion(description="an intake carrying only the third mode bit resolves exactly")
def mode_bit_role_lookback(workspace: Path) -> bool:
    return _matches(workspace, "bit-02", BIT_SEEDS[2], MODE_BITS[2][1])


@criterion(description="an intake carrying only the fourth mode bit resolves exactly")
def mode_bit_band_tier_shift(workspace: Path) -> bool:
    return _matches(workspace, "bit-03", BIT_SEEDS[3], MODE_BITS[3][1])


@criterion(description="an intake carrying only the fifth mode bit resolves exactly")
def mode_bit_testweight_floor(workspace: Path) -> bool:
    return _matches(workspace, "bit-04", BIT_SEEDS[4], MODE_BITS[4][1])


@criterion(description="an intake carrying only the sixth mode bit resolves exactly")
def mode_bit_custom_haul(workspace: Path) -> bool:
    return _matches(workspace, "bit-05", BIT_SEEDS[5], MODE_BITS[5][1])


@criterion(description="an intake carrying only the seventh mode bit resolves exactly")
def mode_bit_tare_delta(workspace: Path) -> bool:
    return _matches(workspace, "bit-06", BIT_SEEDS[6], MODE_BITS[6][1])


@criterion(description="an intake carrying only the eighth mode bit resolves exactly")
def mode_bit_testweight_order(workspace: Path) -> bool:
    return _matches(workspace, "bit-07", BIT_SEEDS[7], MODE_BITS[7][1])


@criterion(description="an intake carrying only the ninth mode bit resolves exactly")
def mode_bit_void_absolves(workspace: Path) -> bool:
    return _matches(workspace, "bit-08", BIT_SEEDS[8], MODE_BITS[8][1])


@criterion(description="an intake carrying only the tenth mode bit resolves exactly")
def mode_bit_count_bias(workspace: Path) -> bool:
    return _matches(workspace, "bit-09", BIT_SEEDS[9], MODE_BITS[9][1])


@criterion(description="an intake carrying only the eleventh mode bit resolves exactly")
def mode_bit_commodity_alias(workspace: Path) -> bool:
    return _matches(workspace, "bit-10", BIT_SEEDS[10], MODE_BITS[10][1])


@criterion(description="an intake carrying only the twelfth mode bit resolves exactly")
def mode_bit_embargo_span(workspace: Path) -> bool:
    return _matches(workspace, "bit-11", BIT_SEEDS[11], MODE_BITS[11][1])


@criterion(description="an intake carrying only the thirteenth mode bit resolves exactly")
def mode_bit_scrap_carry(workspace: Path) -> bool:
    return _matches(workspace, "bit-12", BIT_SEEDS[12], MODE_BITS[12][1])


@criterion(description="a screened intake carrying every mode bit apart from the first resolves exactly")
def every_bit_except_chain_tare(workspace: Path) -> bool:
    return _matches(workspace, "except-00", EXCEPT_SEEDS[0], ALL_FLAGS & ~MODE_BITS[0][1], True, True)


@criterion(description="a screened intake carrying every mode bit apart from the second resolves exactly")
def every_bit_except_dockage_echo(workspace: Path) -> bool:
    return _matches(workspace, "except-01", EXCEPT_SEEDS[1], ALL_FLAGS & ~MODE_BITS[1][1], True, True)


@criterion(description="a screened intake carrying every mode bit apart from the third resolves exactly")
def every_bit_except_role_lookback(workspace: Path) -> bool:
    return _matches(workspace, "except-02", EXCEPT_SEEDS[2], ALL_FLAGS & ~MODE_BITS[2][1], True, True)


@criterion(description="a screened intake carrying every mode bit apart from the fourth resolves exactly")
def every_bit_except_band_tier_shift(workspace: Path) -> bool:
    return _matches(workspace, "except-03", EXCEPT_SEEDS[3], ALL_FLAGS & ~MODE_BITS[3][1], True, True)


@criterion(description="a screened intake carrying every mode bit apart from the fifth resolves exactly")
def every_bit_except_testweight_floor(workspace: Path) -> bool:
    return _matches(workspace, "except-04", EXCEPT_SEEDS[4], ALL_FLAGS & ~MODE_BITS[4][1], True, True)


@criterion(description="a screened intake carrying every mode bit apart from the sixth resolves exactly")
def every_bit_except_custom_haul(workspace: Path) -> bool:
    return _matches(workspace, "except-05", EXCEPT_SEEDS[5], ALL_FLAGS & ~MODE_BITS[5][1], True, True)


@criterion(description="a screened intake carrying every mode bit apart from the seventh resolves exactly")
def every_bit_except_tare_delta(workspace: Path) -> bool:
    return _matches(workspace, "except-06", EXCEPT_SEEDS[6], ALL_FLAGS & ~MODE_BITS[6][1], True, True)


@criterion(description="a screened intake carrying every mode bit apart from the eighth resolves exactly")
def every_bit_except_testweight_order(workspace: Path) -> bool:
    return _matches(workspace, "except-07", EXCEPT_SEEDS[7], ALL_FLAGS & ~MODE_BITS[7][1], True, True)


@criterion(description="a screened intake carrying every mode bit apart from the ninth resolves exactly")
def every_bit_except_void_absolves(workspace: Path) -> bool:
    return _matches(workspace, "except-08", EXCEPT_SEEDS[8], ALL_FLAGS & ~MODE_BITS[8][1], True, True)


@criterion(description="a screened intake carrying every mode bit apart from the tenth resolves exactly")
def every_bit_except_count_bias(workspace: Path) -> bool:
    return _matches(workspace, "except-09", EXCEPT_SEEDS[9], ALL_FLAGS & ~MODE_BITS[9][1], True, True)


@criterion(description="a screened intake carrying every mode bit apart from the eleventh resolves exactly")
def every_bit_except_commodity_alias(workspace: Path) -> bool:
    return _matches(workspace, "except-10", EXCEPT_SEEDS[10], ALL_FLAGS & ~MODE_BITS[10][1], True, True)


@criterion(description="a screened intake carrying every mode bit apart from the twelfth resolves exactly")
def every_bit_except_embargo_span(workspace: Path) -> bool:
    return _matches(workspace, "except-11", EXCEPT_SEEDS[11], ALL_FLAGS & ~MODE_BITS[11][1], True, True)


@criterion(description="a screened intake carrying every mode bit apart from the thirteenth resolves exactly")
def every_bit_except_scrap_carry(workspace: Path) -> bool:
    return _matches(workspace, "except-12", EXCEPT_SEEDS[12], ALL_FLAGS & ~MODE_BITS[12][1], True, True)


@criterion(description="a screened intake carrying every mode bit resolves exactly")
def full_mode_intake_alpha(workspace: Path) -> bool:
    return _matches(workspace, "full-a", FULL_SEED, ALL_FLAGS, True, True)


@criterion(description="a second screened intake carrying every mode bit resolves exactly")
def full_mode_intake_beta(workspace: Path) -> bool:
    return _matches(workspace, "alias", ALIAS_SEED, ALL_FLAGS, True, True)


@criterion(description="the delivered program carries the shipped intake's bin identifiers as literal answers")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        source = _delivered_source(workspace)
        if source is None:
            return False
        shipped = sorted({row[0] for row in build_case(SAMPLE_SEED, False).bins})
        literals = []
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                literals.append(node.value)
        blob = "\n".join(literals)
        return sum(1 for name in shipped if name in blob) >= 5
    except Exception:
        return False


@criterion(description="the delivered program pulls in a module outside the standard library")
def negative_third_party_dependency(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        source = _delivered_source(workspace)
        if source is None:
            return False
        wanted = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                wanted.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                wanted.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call):
                name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                if name in ("__import__", "import_module") and node.args:
                    first = node.args[0]
                    if isinstance(first, ast.Constant) and isinstance(first.value, str):
                        wanted.add(first.value.split(".")[0])
        return bool(wanted - set(sys.stdlib_module_names))
    except Exception:
        return False


@criterion(description="repeated runs of the delivered program over one input write differing bytes")
def negative_nondeterministic_output(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        run = _run(workspace, "repeat", REPEAT_SEED, ALL_FLAGS, True, True)
        if run is None or run[3] != 0:
            return False
        data, out, scratch = run[0], run[1], run[2]
        first = {name: _artifact(out, name) for name in REPORTS}
        for _attempt in range(4):
            again = _launch([sys.executable, _script(workspace), data, out], scratch)
            if again is None:
                return False
            if again != 0:
                return True
            for name, body in first.items():
                if _artifact(out, name) != body:
                    return True
        return False
    except Exception:
        return False


criteria.reusable_program_is_delivered(weight=1)
criteria.untrapped_run_alpha_resolves(weight=1)
criteria.untrapped_run_beta_resolves(weight=1)
criteria.screened_intake_mode_zero_resolves(weight=3)
criteria.mode_bit_chain_tare(weight=5)
criteria.mode_bit_dockage_echo(weight=5)
criteria.mode_bit_role_lookback(weight=5)
criteria.mode_bit_band_tier_shift(weight=5)
criteria.mode_bit_testweight_floor(weight=5)
criteria.mode_bit_custom_haul(weight=5)
criteria.mode_bit_tare_delta(weight=5)
criteria.mode_bit_testweight_order(weight=5)
criteria.mode_bit_void_absolves(weight=5)
criteria.mode_bit_count_bias(weight=5)
criteria.mode_bit_commodity_alias(weight=5)
criteria.mode_bit_embargo_span(weight=5)
criteria.mode_bit_scrap_carry(weight=5)
criteria.every_bit_except_chain_tare(weight=1)
criteria.every_bit_except_dockage_echo(weight=1)
criteria.every_bit_except_role_lookback(weight=1)
criteria.every_bit_except_band_tier_shift(weight=1)
criteria.every_bit_except_testweight_floor(weight=1)
criteria.every_bit_except_custom_haul(weight=1)
criteria.every_bit_except_tare_delta(weight=1)
criteria.every_bit_except_testweight_order(weight=1)
criteria.every_bit_except_void_absolves(weight=1)
criteria.every_bit_except_count_bias(weight=1)
criteria.every_bit_except_commodity_alias(weight=1)
criteria.every_bit_except_embargo_span(weight=1)
criteria.every_bit_except_scrap_carry(weight=1)
criteria.full_mode_intake_alpha(weight=5)
criteria.full_mode_intake_beta(weight=5)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_third_party_dependency(weight=-3)
criteria.negative_nondeterministic_output(weight=-3)

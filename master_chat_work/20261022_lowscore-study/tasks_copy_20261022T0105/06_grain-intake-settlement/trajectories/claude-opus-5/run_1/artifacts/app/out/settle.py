#!/usr/bin/env python3
"""The intake settlement engine.

Usage: settle.py <input_dir> <output_dir>

Reads the seven intake files out of the input directory, honours the mode word
carried in manifest.json, and writes settlements.jsonl, binroll.json and
elevator.json into the output directory.

Every figure is derived from the input files at run time. All arithmetic runs
through Python integers, so a load larger than a float can hold still settles
exactly.
"""
import collections
import csv
import json
import os
import sys

EIGHT = ("action", "bin", "card", "grader", "hauler", "gross", "seq", "testweight")
STRING_KEYS = ("action", "bin", "card", "grader", "hauler")
ACTIONS = ("weigh", "tare", "settle", "void")
BANDNAMES = ("feed", "mill", "prime", "scrap")
STATUSNAMES = ("clear", "flagged", "open", "rejected", "voided")

# Sentinel for JSON numbers that are not integers (fractions, exponents) and for
# the bare constants. Reusing one object keeps the identity test cheap.
_NONINT = object()


# --------------------------------------------------------------------------
# input
# --------------------------------------------------------------------------

def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_refs(indir):
    j = lambda n: os.path.join(indir, n)
    bins = {}
    order = []
    for r in read_csv(j("bins.csv")):
        bins[r["bin"]] = dict(bin=r["bin"], dryer=r["dryer"], contract=r["contract"],
                              commodity=r["commodity"], tier=int(r["tier"]))
        order.append(r["bin"])
    dryers = {r["dryer"]: dict(make=r["make"], tare_base=int(r["tare_base"]))
              for r in read_csv(j("dryers.csv"))}
    contracts = {r["contract"]: dict(family=r["family"], lots=int(r["lots"]))
                 for r in read_csv(j("contracts.csv"))}
    graders = {r["grader"]: r["role"] for r in read_csv(j("graders.csv"))}
    haulers = {r["hauler"]: r["class"] for r in read_csv(j("haulers.csv"))}
    with open(j("manifest.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    return dict(bins=bins, bin_order=order, dryers=dryers, contracts=contracts,
                graders=graders, haulers=haulers, manifest=manifest)


# --------------------------------------------------------------------------
# intake screening -- identical at every mode word
# --------------------------------------------------------------------------

def parse_line(raw, refs):
    """Return the eight ticket values, or None when the line is damaged."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None

    repeated = []

    def pairs_hook(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                repeated.append(key)
            obj[key] = value
        return obj

    try:
        obj = json.loads(text, object_pairs_hook=pairs_hook,
                         parse_float=lambda s: _NONINT,
                         parse_constant=lambda s: _NONINT)
    except Exception:
        return None
    if repeated or not isinstance(obj, dict):
        return None
    for key in EIGHT:
        if key not in obj:
            return None
    for key in STRING_KEYS:
        if not isinstance(obj[key], str):
            return None

    def whole(value):
        return isinstance(value, int) and not isinstance(value, bool)

    if not whole(obj["seq"]) or obj["seq"] < 1:
        return None
    if not whole(obj["gross"]) or obj["gross"] < 0:
        return None
    if not whole(obj["testweight"]) or obj["testweight"] < 1:
        return None
    if obj["action"] not in ACTIONS:
        return None
    if obj["bin"] not in refs["bins"]:
        return None
    if obj["grader"] not in refs["graders"]:
        return None
    if obj["hauler"] not in refs["haulers"]:
        return None
    return {key: obj[key] for key in EIGHT}


def screen(indir, refs):
    with open(os.path.join(indir, "tickets.jsonl"), "rb") as fh:
        blob = fh.read()

    malformed = 0
    survivors = []
    for raw in blob.split(b"\n"):
        if raw.strip() == b"":
            continue
        ticket = parse_line(raw, refs)
        if ticket is None:
            malformed += 1
        else:
            survivors.append(ticket)

    groups = collections.defaultdict(list)
    for ticket in survivors:
        groups[ticket["seq"]].append(ticket)

    conflicted = 0
    agreed = []
    for seq in sorted(groups):
        group = groups[seq]
        first = tuple(group[0][k] for k in EIGHT)
        if all(tuple(t[k] for k in EIGHT) == first for t in group):
            agreed.append(group)
        else:
            conflicted += len(group)

    claimed = set()
    reentered = 0
    retransmitted = 0
    resolved = []
    for group in agreed:
        pair = (group[0]["bin"], group[0]["card"])
        if pair in claimed:
            reentered += len(group)
            continue
        claimed.add(pair)
        retransmitted += len(group) - 1
        resolved.append(group[0])

    counts = dict(conflicted=conflicted, malformed=malformed,
                  reentered=reentered, retransmitted=retransmitted)
    return resolved, counts


# --------------------------------------------------------------------------
# the chain
# --------------------------------------------------------------------------

def base_config():
    """The mode zero chain, as pinned by the two worked intakes."""
    return dict(
        norm=1000,
        edge_prime=260, edge_mill=130, edge_feed=45,
        commodity={"barley": ("add", -6), "canola": ("mul", 4, 5),
                   "oats": ("add", 9), "corn": ("mul", 1, 2),
                   "milo": ("floor", 4), "rye": ("mul", 6, 5)},
        contract={"track": ("mul", 4, 5), "board": ("add", 15),
                  "hedge": ("mul", 8, 5)},
        tol={"weighman": 30, "inspector": 45, "apprentice": 15, "relief": 0},
        charge_div=40, charge_tier=3, charge_mult=2, ceiling=96,
        charge_skip="none",
        comm_shift=0,
        opening=frozenset(("tare", "settle")),
        counted=frozenset(("clear", "flagged")),
        embargo_strikes=3, hold_dockage=35,
        tare_init="dryer",
        top_card="last", top_bin="first",
    )


def config_for(mode):
    """Apply the alterations the mode word switches on.

    Each bit drives one independent alteration. Bits whose reading is not yet
    settled against the manifest digests are left as no-ops.
    """
    cfg = base_config()
    for bit in range(13):
        if mode & (1 << bit):
            hook = BIT_HOOKS.get(bit)
            if hook is not None:
                hook(cfg)
    return cfg


def _tare_by_make(cfg):
    """The tare level starts at the tare_base shared by the dryer's make."""
    cfg["tare_init"] = "make_first"


def _commodity_shift(cfg):
    """The commodity adjustment keys one position back along the declared order."""
    cfg["comm_shift"] = -1


def _first_ticket_free(cfg):
    """A bin's first resolved ticket accrues no dockage charge."""
    cfg["charge_skip"] = "first"


# Three alterations are pinned by sha256 preimages recovered from the one- and
# two-ticket bins of the 0x1fff intake. Which *bit* carries which alteration is
# not recoverable from the evidence that ships here: mode 0 and mode 0x1fff are
# the only worked points, and every assignment of alterations to bits reproduces
# both. The assignment below is therefore a stated assumption, not a finding.
# The ten unresolved bits are left as no-ops so that a mode word only ever moves
# the chain in ways the digests actually support.
BIT_HOOKS = {
    0: _tare_by_make,
    1: _commodity_shift,
    2: _first_ticket_free,
}


def adjust(spec, figure):
    kind = spec[0]
    if kind == "add":
        return figure + spec[1]
    if kind == "mul":
        return figure * spec[1] // spec[2]
    if kind == "floor":
        return figure // spec[1] * spec[1]
    return figure


COMMODITY_ORDER = ("wheat", "barley", "canola", "oats", "corn", "milo", "rye")


def commodity_spec(cfg, commodity):
    """The commodity adjustment, keyed with whatever shift the mode word asks for."""
    shift = cfg["comm_shift"]
    if shift and commodity in COMMODITY_ORDER:
        i = COMMODITY_ORDER.index(commodity)
        commodity = COMMODITY_ORDER[(i + shift) % len(COMMODITY_ORDER)]
    return cfg["commodity"].get(commodity)


def band_of(cfg, bushels):
    if bushels >= cfg["edge_prime"]:
        return "prime"
    if bushels >= cfg["edge_mill"]:
        return "mill"
    if bushels >= cfg["edge_feed"]:
        return "feed"
    return "scrap"


def initial_tare(cfg, refs, binrow):
    dryer = refs["dryers"][binrow["dryer"]]
    if cfg["tare_init"] == "make_first":
        for other in refs["dryers"].values():
            if other["make"] == dryer["make"]:
                return other["tare_base"]
    return dryer["tare_base"]


def resolve(cfg, refs, tickets):
    bins = refs["bins"]
    state = {}
    for name, binrow in bins.items():
        state[name] = dict(tare=initial_tare(cfg, refs, binrow), dock=0,
                           strikes=0, seen=0)

    records = []
    for ticket in sorted(tickets, key=lambda t: t["seq"]):
        binrow = bins[ticket["bin"]]
        st = state[ticket["bin"]]
        family = refs["contracts"][binrow["contract"]]["family"]
        role = refs["graders"][ticket["grader"]]

        figure = max(0, ticket["gross"] - st["tare"])
        figure = max(0, figure * cfg["norm"] // ticket["testweight"])
        spec = commodity_spec(cfg, binrow["commodity"])
        if spec:
            figure = max(0, adjust(spec, figure))
        spec = cfg["contract"].get(family)
        if spec:
            figure = max(0, adjust(spec, figure))

        dockage_before = st["dock"]
        bushels = max(0, figure - dockage_before)
        band = band_of(cfg, bushels)

        if ticket["action"] in cfg["opening"]:
            status = "open"
        elif ticket["action"] == "void":
            status = "voided"
        elif band == "scrap":
            status = "rejected"
        elif dockage_before > cfg["tol"][role]:
            status = "flagged"
        else:
            status = "clear"

        records.append(dict(action=ticket["action"], band=band, bin=ticket["bin"],
                            bushels=bushels, card=ticket["card"],
                            dockage_before=dockage_before, grader=ticket["grader"],
                            seq=ticket["seq"], status=status))

        st["seen"] += 1
        if ticket["action"] == "tare":
            st["tare"] = ticket["gross"]
        elif ticket["action"] == "settle":
            st["dock"] = 0
        elif ticket["action"] == "weigh":
            if not (cfg["charge_skip"] == "first" and st["seen"] == 1):
                charge = ticket["testweight"] // cfg["charge_div"]
                if binrow["tier"] == cfg["charge_tier"]:
                    charge *= cfg["charge_mult"]
                st["dock"] = min(cfg["ceiling"], st["dock"] + charge)
        if status == "rejected":
            st["strikes"] += 1

    return records, state


# --------------------------------------------------------------------------
# rollups
# --------------------------------------------------------------------------

def build_binroll(cfg, refs, records, state):
    per_bin = collections.defaultdict(list)
    for rec in records:
        per_bin[rec["bin"]].append(rec)

    rows = []
    for name in sorted(refs["bins"]):
        mine = per_bin.get(name, [])
        counted = [r for r in mine if r["status"] in cfg["counted"]]
        bands = {b: 0 for b in BANDNAMES}
        for rec in mine:
            bands[rec["band"]] += 1

        top_card = None
        peak = 0
        if counted:
            peak = max(r["bushels"] for r in counted)
            tied = [r["card"] for r in counted if r["bushels"] == peak]
            top_card = tied[-1] if cfg["top_card"] == "last" else tied[0]

        st = state[name]
        rows.append(dict(
            bands=bands,
            bin=name,
            bushel_total=sum(r["bushels"] for r in counted),
            disposition=("embargo" if st["strikes"] >= cfg["embargo_strikes"]
                         else "hold" if st["dock"] > cfg["hold_dockage"]
                         else "release"),
            dockage_end=st["dock"],
            flagged=sum(1 for r in mine if r["status"] == "flagged"),
            peak=peak,
            rejects=st["strikes"],
            tare_end=st["tare"],
            tickets=len(mine),
            top_card=top_card,
            weighed=sum(1 for r in mine if r["action"] == "weigh"),
        ))
    return rows


def build_elevator(cfg, refs, records, rows, counts):
    by_band = {b: 0 for b in BANDNAMES}
    by_status = {s: 0 for s in STATUSNAMES}
    for rec in records:
        by_band[rec["band"]] += 1
        by_status[rec["status"]] += 1

    top_bin = None
    if rows:
        best = max(r["bushel_total"] for r in rows)
        tied = [r["bin"] for r in rows if r["bushel_total"] == best]
        top_bin = tied[0] if cfg["top_bin"] == "first" else tied[-1]

    return dict(
        bins=len(refs["bins"]),
        bushel_total=sum(r["bushel_total"] for r in rows),
        by_band=by_band,
        by_status=by_status,
        embargoed=sorted(r["bin"] for r in rows if r["disposition"] == "embargo"),
        screened=counts,
        tickets=len(records),
        top_bin=top_bin,
    )


# --------------------------------------------------------------------------
# byte forms
# --------------------------------------------------------------------------

def settlements_text(records):
    return "".join(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n"
                   for r in records)


def document_text(document):
    return json.dumps(document, sort_keys=True, indent=2) + "\n"


def run(indir):
    refs = load_refs(indir)
    mode = int(refs["manifest"].get("mode", 0))
    cfg = config_for(mode)
    tickets, counts = screen(indir, refs)
    records, state = resolve(cfg, refs, tickets)
    rows = build_binroll(cfg, refs, records, state)
    elevator = build_elevator(cfg, refs, records, rows, counts)
    return dict(refs=refs, mode=mode, cfg=cfg, records=records, state=state,
                rows=rows, binroll={"bins": rows}, elevator=elevator,
                counts=counts)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: settle.py <input_dir> <output_dir>\n")
        return 2
    indir, outdir = argv[1], argv[2]
    result = run(indir)
    os.makedirs(outdir, exist_ok=True)
    out = {
        "settlements.jsonl": settlements_text(result["records"]),
        "binroll.json": document_text(result["binroll"]),
        "elevator.json": document_text(result["elevator"]),
    }
    for name, text in out.items():
        with open(os.path.join(outdir, name), "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

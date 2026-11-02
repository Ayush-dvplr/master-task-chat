#!/usr/bin/env python3
"""Oracle for grain-intake-settlement.

Writes the rebuilt settlement engine to /app/out/settle.py, runs it over /app/data,
checks it against both worked intakes and against every digest the graded manifest
carries, then prints the closing report the instruction asks for.
"""
import hashlib
import json
import os
import subprocess
import sys

ENGINE = r'''#!/usr/bin/env python3
"""Grain intake settlement engine.

Rebuilt from engine.md and reports.md. Plain chain constants were fitted on the two
mode zero worked intakes; each mode bit was settled against the bin digests of the
graded manifest. Usage: settle.py INPUT_DIR OUTPUT_DIR
"""
import csv
import json
import os
import sys

# Plain chain constants (fitted on example_a_ and example_b_).
NORMALISE = 1000
GRADE_ADJUST = {
    "wheat": lambda f: f,
    "barley": lambda f: f - 6,
    "canola": lambda f: f * 4 // 5,
    "oats": lambda f: f + 9,
    "corn": lambda f: f // 2,
    "milo": lambda f: f - f % 4,
    "rye": lambda f: f * 6 // 5,
}
CONTRACT_ADJUST = {
    "basis": lambda f: f,
    "track": lambda f: f * 4 // 5,
    "board": lambda f: f + 15,
    "hedge": lambda f: f * 8 // 5,
}
BAND_FLOORS = (("prime", 260), ("mill", 130), ("feed", 45))
TOLERANCE = {"weighman": 30, "inspector": 45, "apprentice": 15, "relief": 0}
CHARGE_DIVISOR = 40
DOUBLE_CHARGE_TIER = 3
DOCKAGE_CEILING = 96
EMBARGO_AT = 3
HOLD_ABOVE = 35
COUNTED_STATUSES = ("clear", "flagged")
GRAIN_SEQUENCE = ("wheat", "barley", "canola", "oats", "corn", "milo", "rye")

# Mode bits (settled one at a time against the graded manifest's bin digests).
BITS = dict((name, 1 << place) for place, name in enumerate((
    "tare_chains_across_dryer",    # 0x0001 bin opens at the dryer's previous bin tare
    "charge_lands_late",           # 0x0002 dockage charge applies on the next ticket
    "tolerance_from_last_grader",  # 0x0004 role tolerance of the previous grader
    "bands_lift_with_tier",        # 0x0008 band floors + 20 * tier
    "bin_minimum_testweight",      # 0x0010 normalise on the bin's lowest testweight
    "custom_haul_free",            # 0x0020 custom class haulers carry no charge
    "island_dryer_delta",          # 0x0040 last carrying dryer stores a delta
    "testweight_walk",             # 0x0080 resolve by (testweight, seq)
    "void_forgives_strike",        # 0x0100 a void removes one strike
    "tail_of_three_dropped",       # 0x0200 last three screened tickets by seq dropped
    "commodity_shifted",           # 0x0400 commodity read tier + 5 places along
    "embargo_counts_neighbour",    # 0x0800 previous bin on dryer adds its strikes
    "scrap_taints_next",           # 0x1000 ticket after a scrap ticket cannot be clear
)))

FIELDS = ("action", "bin", "card", "grader", "gross", "hauler", "seq", "testweight")
TEXT_FIELDS = ("action", "bin", "card", "grader", "hauler")
ACTIONS = ("weigh", "tare", "settle", "void")


def table(path, key):
    with open(path, encoding="utf-8", newline="") as stream:
        return {line[key]: line for line in csv.DictReader(stream)}


def whole(value, lowest):
    return type(value) is int and value >= lowest


class Members(tuple):
    """One JSON object as the (key, value) pairs it was written with."""


class Intake:
    def __init__(self, folder):
        def path(name):
            return os.path.join(folder, name)

        with open(path("manifest.json"), encoding="utf-8") as stream:
            self.mode = int(json.load(stream)["mode"])
        self.tare_base = {k: int(v["tare_base"]) for k, v in table(path("dryers.csv"), "dryer").items()}
        self.family = {k: v["family"] for k, v in table(path("contracts.csv"), "contract").items()}
        self.role = {k: v["role"] for k, v in table(path("graders.csv"), "grader").items()}
        self.haul_class = {k: v["class"] for k, v in table(path("haulers.csv"), "hauler").items()}
        self.bins = {}
        for k, v in table(path("bins.csv"), "bin").items():
            self.bins[k] = {"dryer": v["dryer"], "contract": v["contract"],
                            "commodity": v["commodity"], "tier": int(v["tier"])}
        with open(path("tickets.jsonl"), "rb") as stream:
            self.tickets, self.screened = self.screen(stream.read())

    def on(self, name):
        return bool(self.mode & BITS[name])

    def vet(self, raw):
        """Screening pass one: a line on its own; None means it is set aside."""
        try:
            record = json.loads(raw.decode("utf-8"), object_pairs_hook=Members)
        except (UnicodeDecodeError, ValueError):
            return None
        if type(record) is not Members:
            return None
        names = [name for name, _value in record]
        if len(names) != len(set(names)):
            return None
        record = dict(record)
        if any(name not in record for name in FIELDS):
            return None
        if any(not isinstance(record[name], str) for name in TEXT_FIELDS):
            return None
        if not (whole(record["seq"], 1) and whole(record["gross"], 0)
                and whole(record["testweight"], 1)):
            return None
        if record["action"] not in ACTIONS:
            return None
        if (record["bin"] not in self.bins or record["grader"] not in self.role
                or record["hauler"] not in self.haul_class):
            return None
        return tuple(record[name] for name in FIELDS)

    def screen(self, blob):
        survivors = {}
        malformed = 0
        for raw in blob.split(b"\n"):
            if raw.strip() == b"":
                continue
            vetted = self.vet(raw)
            if vetted is None:
                malformed += 1
            else:
                survivors.setdefault(vetted[FIELDS.index("seq")], []).append(vetted)
        once, conflicted = [], 0
        for seq in sorted(survivors):
            copies = survivors[seq]
            if len(set(copies)) == 1:
                once.append(copies)
            else:
                conflicted += len(copies)
        kept, cards, reentered, repeats = [], set(), 0, 0
        for copies in once:
            ticket = dict(zip(FIELDS, copies[0]))
            if (ticket["bin"], ticket["card"]) in cards:
                reentered += len(copies)
                continue
            cards.add((ticket["bin"], ticket["card"]))
            kept.append(ticket)
            repeats += len(copies) - 1
        return kept, {"conflicted": conflicted, "malformed": malformed,
                      "reentered": reentered, "retransmitted": repeats}


class BinState:
    def __init__(self, tare, before):
        self.tare = tare
        self.dockage = 0
        self.deferred = 0
        self.strikes = 0
        self.last_grader = None
        self.after_scrap = False
        self.before = before


def band_for(figure, lift):
    for label, floor in BAND_FLOORS:
        if figure >= floor + lift:
            return label
    return "scrap"


def settle(intake):
    bases = dict(intake.tare_base)
    carrying = sorted(set(row["dryer"] for row in intake.bins.values()))
    if intake.on("island_dryer_delta") and len(bases) > 1 and carrying:
        island = carrying[-1]
        rest = [value for name, value in bases.items() if name != island]
        if rest:
            bases[island] += min(rest)

    walk = sorted(intake.tickets, key=lambda t: t["seq"])
    if intake.on("tail_of_three_dropped"):
        walk = walk[:-3]
    if intake.on("testweight_walk"):
        walk.sort(key=lambda t: (t["testweight"], t["seq"]))

    lowest = {}
    for t in walk:
        lowest[t["bin"]] = min(lowest.get(t["bin"], t["testweight"]), t["testweight"])

    states, newest_on_dryer, lines = {}, {}, []
    for t in walk:
        info = intake.bins[t["bin"]]
        state = states.get(t["bin"])
        if state is None:
            neighbour = newest_on_dryer.get(info["dryer"])
            opening = bases[info["dryer"]]
            if intake.on("tare_chains_across_dryer") and neighbour is not None:
                opening = states[neighbour].tare
            state = states[t["bin"]] = BinState(opening, neighbour)
            newest_on_dryer[info["dryer"]] = t["bin"]

        grain = info["commodity"]
        if intake.on("commodity_shifted") and grain in GRAIN_SEQUENCE:
            grain = GRAIN_SEQUENCE[(GRAIN_SEQUENCE.index(grain) + info["tier"] + 5) % len(GRAIN_SEQUENCE)]
        judged_by = t["grader"]
        if intake.on("tolerance_from_last_grader") and state.last_grader is not None:
            judged_by = state.last_grader
        divisor = lowest[t["bin"]] if intake.on("bin_minimum_testweight") else t["testweight"]
        lift = 20 * info["tier"] if intake.on("bands_lift_with_tier") else 0

        figure = max(0, (t["gross"] - state.tare) * NORMALISE // divisor)
        figure = max(0, GRADE_ADJUST.get(grain, GRADE_ADJUST["wheat"])(figure))
        figure = max(0, CONTRACT_ADJUST.get(intake.family[info["contract"]], CONTRACT_ADJUST["basis"])(figure))
        held = state.dockage
        bushels = max(0, figure - held)
        band = band_for(bushels, lift)
        if t["action"] in ("tare", "settle"):
            status = "open"
        elif t["action"] == "void":
            status = "voided"
        elif band == "scrap":
            status = "rejected"
        elif held > TOLERANCE.get(intake.role[judged_by], TOLERANCE["weighman"]):
            status = "flagged"
        else:
            status = "clear"
        if status == "clear" and intake.on("scrap_taints_next") and state.after_scrap:
            status = "flagged"
        lines.append({"action": t["action"], "band": band, "bin": t["bin"], "bushels": bushels,
                      "card": t["card"], "dockage_before": held, "grader": t["grader"],
                      "seq": t["seq"], "status": status})

        if status == "rejected":
            state.strikes += 1
        if t["action"] == "void" and intake.on("void_forgives_strike") and state.strikes:
            state.strikes -= 1
        state.last_grader = t["grader"]
        state.after_scrap = band == "scrap"

        fee = 0
        if t["action"] == "weigh":
            fee = t["testweight"] // CHARGE_DIVISOR
            if info["tier"] == DOUBLE_CHARGE_TIER:
                fee *= 2
        if intake.on("custom_haul_free") and intake.haul_class[t["hauler"]] == "custom":
            fee = 0
        if intake.on("charge_lands_late"):
            fee, state.deferred = state.deferred, fee
        if t["action"] == "tare":
            state.tare = t["gross"]
        elif t["action"] == "settle":
            state.dockage, state.deferred, fee = 0, 0, 0
        state.dockage = min(DOCKAGE_CEILING, state.dockage + fee)

    rollup = []
    for name in sorted(intake.bins):
        mine = [line for line in lines if line["bin"] == name]
        counted = [line for line in mine if line["status"] in COUNTED_STATUSES]
        state = states.get(name)
        strikes = state.strikes if state else 0
        weighed_strikes = strikes
        if state and intake.on("embargo_counts_neighbour") and state.before is not None:
            weighed_strikes += states[state.before].strikes
        dockage_end = state.dockage if state else 0
        if weighed_strikes >= EMBARGO_AT:
            disposition = "embargo"
        elif dockage_end > HOLD_ABOVE:
            disposition = "hold"
        else:
            disposition = "release"
        leader = max(counted, key=lambda line: (line["bushels"], line["seq"])) if counted else None
        tally = dict.fromkeys(("feed", "mill", "prime", "scrap"), 0)
        for line in mine:
            tally[line["band"]] += 1
        rollup.append({
            "bands": tally,
            "bin": name,
            "bushel_total": sum(line["bushels"] for line in counted),
            "disposition": disposition,
            "dockage_end": dockage_end,
            "flagged": len([line for line in mine if line["status"] == "flagged"]),
            "peak": max([line["bushels"] for line in counted] + [0]),
            "rejects": strikes,
            "tare_end": state.tare if state else bases[intake.bins[name]["dryer"]],
            "tickets": len(mine),
            "top_card": leader["card"] if leader else None,
            "weighed": len([line for line in mine if line["action"] == "weigh"]),
        })

    band_count = dict.fromkeys(("feed", "mill", "prime", "scrap"), 0)
    status_count = dict.fromkeys(("clear", "flagged", "open", "rejected", "voided"), 0)
    for line in lines:
        band_count[line["band"]] += 1
        status_count[line["status"]] += 1
    leading = max(rollup, key=lambda row: row["bushel_total"])["bin"] if rollup else None
    elevator = {
        "bins": len(rollup),
        "bushel_total": sum(row["bushel_total"] for row in rollup),
        "by_band": band_count,
        "by_status": status_count,
        "embargoed": sorted(row["bin"] for row in rollup if row["disposition"] == "embargo"),
        "screened": dict(intake.screened),
        "tickets": len(lines),
        "top_bin": leading,
    }
    return lines, rollup, elevator


def as_line(record):
    return json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"


def as_document(document):
    return json.dumps(document, sort_keys=True, indent=2) + "\n"


def reports(lines, rollup, elevator):
    return {
        "settlements.jsonl": "".join(as_line(line) for line in lines),
        "binroll.json": as_document({"bins": rollup}),
        "elevator.json": as_document(elevator),
    }


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: settle.py INPUT_DIR OUTPUT_DIR\n")
        return 2
    source, target = argv
    written = reports(*settle(Intake(source)))
    os.makedirs(target, exist_ok=True)
    for name in sorted(written):
        with open(os.path.join(target, name), "w", encoding="utf-8", newline="") as stream:
            stream.write(written[name])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
'''

DATA = "/app/data"
OUT = "/app/out"
PROGRAM = os.path.join(OUT, "settle.py")
WORKED = ("example_a_", "example_b_")


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def digests(lines, rollup, elevator, as_line, as_document):
    per_bin = {}
    for row in rollup:
        own = "".join(as_line(line) for line in lines if line["bin"] == row["bin"])
        per_bin[row["bin"]] = sha(own + as_document(row))
    whole = sha("".join(as_line(line) for line in lines)
                + as_document({"bins": rollup}) + as_document(elevator))
    return per_bin, whole


def stage_worked_intake(prefix, scratch):
    """Copy one prefixed worked intake under the plain names the program reads."""
    os.makedirs(scratch, exist_ok=True)
    for name in ("manifest.json", "dryers.csv", "contracts.csv", "graders.csv",
                 "haulers.csv", "bins.csv", "tickets.jsonl"):
        with open(os.path.join(DATA, prefix + name), "rb") as src:
            body = src.read()
        with open(os.path.join(scratch, name), "wb") as dst:
            dst.write(body)


def run_program(source, target):
    done = subprocess.run([sys.executable, PROGRAM, source, target])
    if done.returncode != 0:
        raise SystemExit("settle.py exited %d on %s" % (done.returncode, source))


def main():
    for note in ("engine.md", "reports.md"):
        with open(os.path.join(DATA, note), encoding="utf-8") as stream:
            print("read %s (%d lines)" % (note, stream.read().count("\n")))

    os.makedirs(OUT, exist_ok=True)
    with open(PROGRAM, "w", encoding="utf-8", newline="") as stream:
        stream.write(ENGINE)
    engine = {"__name__": "engine"}
    exec(compile(ENGINE, PROGRAM, "exec"), engine)

    scratch_root = os.path.join("/tmp", "settle-oracle")
    for prefix in WORKED:
        staged = os.path.join(scratch_root, prefix + "in")
        produced = os.path.join(scratch_root, prefix + "out")
        stage_worked_intake(prefix, staged)
        run_program(staged, produced)
        for name in ("settlements.jsonl", "binroll.json", "elevator.json"):
            with open(os.path.join(produced, name), "rb") as mine, \
                    open(os.path.join(DATA, prefix + "out_" + name), "rb") as theirs:
                if mine.read() != theirs.read():
                    raise SystemExit("%s%s differs from the worked output" % (prefix, name))
        print("%s reproduced byte for byte" % prefix)

    run_program(DATA, OUT)
    intake = engine["Intake"](DATA)
    lines, rollup, elevator = engine["settle"](intake)
    expected = engine["reports"](lines, rollup, elevator)
    for name, body in expected.items():
        with open(os.path.join(OUT, name), encoding="utf-8", newline="") as stream:
            if stream.read() != body:
                raise SystemExit("%s on disk differs from the in process resolution" % name)

    with open(os.path.join(DATA, "manifest.json"), encoding="utf-8") as stream:
        manifest = json.load(stream)
    per_bin, whole = digests(lines, rollup, elevator, engine["as_line"], engine["as_document"])
    agreeing = sum(1 for name, value in manifest["bin_digests"].items() if per_bin.get(name) == value)
    total = len(manifest["bin_digests"])

    settled, still_open = [], []
    full_mode = intake.mode
    for name, bit in sorted(engine["BITS"].items(), key=lambda item: item[1]):
        intake.mode = full_mode & ~bit
        trial = engine["settle"](intake)
        hits = sum(1 for bin_id, value in digests(*trial, engine["as_line"], engine["as_document"])[0].items()
                   if manifest["bin_digests"].get(bin_id) == value)
        print("bit 0x%04x %s cleared: %d of %d bin digests agree" % (bit, name, hits, total))
        (settled if hits < agreeing else still_open).append("0x%04x" % bit)
    intake.mode = full_mode

    family = {b: intake.family[row["contract"]] for b, row in intake.bins.items()}
    grain = {b: row["commodity"] for b, row in intake.bins.items()}
    figures = [
        ("scrap_rejects", sum(1 for l in lines if l["status"] == "rejected")),
        ("weighman_flags", sum(1 for l in lines if l["status"] == "flagged"
                               and intake.role[l["grader"]] == "weighman")),
        ("off_role_flags", sum(1 for l in lines if l["status"] == "flagged"
                               and intake.role[l["grader"]] != "weighman")),
        ("hold_bins", sum(1 for r in rollup if r["disposition"] == "hold")),
        ("capped_tickets", sum(1 for l in lines if l["dockage_before"] == engine["DOCKAGE_CEILING"])),
        ("light_grain_total", sum(l["bushels"] for l in lines if grain[l["bin"]] in ("corn", "milo"))),
        ("heavy_grain_total", sum(l["bushels"] for l in lines if grain[l["bin"]] in ("barley", "oats"))),
        ("hedge_clear_total", sum(l["bushels"] for l in lines if l["status"] == "clear"
                                  and family[l["bin"]] in ("board", "hedge"))),
        ("prime_tickets", sum(1 for l in lines if l["band"] == "prime")),
        ("tare_end_total", sum(r["tare_end"] for r in rollup)),
        ("set_aside_lines", sum(elevator["screened"][kind] for kind in ("conflicted", "malformed", "reentered"))),
    ]

    print()
    print("Closing report for the unprefixed intake in %s (mode 0x%04x)" % (DATA, full_mode))
    for name, value in figures:
        print("%-18s %d" % (name, value))
    print("bins held: %d; tickets resolved: %d" % (len(rollup), len(lines)))
    print("mode bits settled: %d of 13; still open: %s"
          % (len(settled), ", ".join(still_open) if still_open else "none"))
    print("bin digests agreeing: %d of %d (%s)" % (agreeing, total, "all agree" if agreeing == total else "not all"))
    print("whole intake digest agrees: %s" % ("yes" if whole == manifest["run_digest"] else "no"))
    return 0 if agreeing == total and whole == manifest["run_digest"] else 1


if __name__ == "__main__":
    sys.exit(main())

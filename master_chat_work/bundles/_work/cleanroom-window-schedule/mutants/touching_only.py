#!/usr/bin/env python3
"""Cleanroom night book: plans every night of the book and writes the ten report documents.

Usage: python3 derive_report.py <data_dir> <out_dir>
"""
import configparser
import csv
import json
import sys
import tomllib
from pathlib import Path

INPUTS = ("jobs.csv", "windows.tsv", "bays.json", "qualifications.ini", "setup_fees.csv",
          "clients.jsonl", "regions.csv", "segments.tsv", "mandatory.json", "audit.toml")
REGIONS = ("North", "South", "West", "East")
SEGMENTS = ("commercial", "public")
DAY_END = 1440


class Book:
    """Parsed input files."""

    def __init__(self, data: Path):
        def table(name, delim):
            with open(data / name, newline="", encoding="utf-8") as fh:
                return list(csv.DictReader(fh, delimiter=delim))

        def split(text):
            return [x.strip() for x in text.split(",") if x.strip()]

        self.job_rows = table("jobs.csv", ",")
        self.windows = {r["window_id"]: (int(r["start"]), int(r["end"])) for r in table("windows.tsv", "\t")}
        self.bays = json.loads((data / "bays.json").read_text(encoding="utf-8"))["bays"]
        ini = configparser.ConfigParser()
        ini.read(data / "qualifications.ini", encoding="utf-8")
        self.catalog = split(ini["catalog"]["families"])
        self.qualified = {b["bay_id"]: set(split(ini[b["bay_id"]]["families"])) for b in self.bays}
        self.fees = {}
        for r in table("setup_fees.csv", ","):
            self.fees[(r["night_id"], r["from_family"], r["to_family"])] = (int(r["fee"]), int(r["crew_minutes"]))
        self.site_of = {}
        for line in (data / "clients.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                self.site_of[rec["client_id"]] = rec["site"]
        self.region_of = {r["site"]: r["region"] for r in table("regions.csv", ",")}
        self.segment_of = {r["client_id"]: r["segment"] for r in table("segments.tsv", "\t")}
        self.mandatory = json.loads((data / "mandatory.json").read_text(encoding="utf-8"))
        audit = tomllib.loads((data / "audit.toml").read_text(encoding="utf-8"))
        self.crew_limit = audit["thresholds"]["crew_minutes_limit"]
        self.margin_floor = audit["thresholds"]["margin_floor"]
        self.nights = sorted(audit["night"], key=lambda n: n["date"])
        self.row_count = {}
        for r in self.job_rows:
            self.row_count[r["job_id"]] = self.row_count.get(r["job_id"], 0) + 1


def rejection(book: Book, night_id: str, rows: list) -> str | None:
    """First failing condition in the stated order, or None for an accepted night."""
    if any(book.row_count[r["job_id"]] > 1 for r in rows):
        return "E_DUP_JOB"
    for r in rows:
        w = book.windows.get(r["window_id"])
        if w is None or not 0 <= w[0] < w[1] <= DAY_END:
            return "E_BAD_WINDOW"
    if any(r["family"] not in book.catalog or r["client_id"] not in book.site_of for r in rows):
        return "E_UNKNOWN_RESOURCE"
    for a in book.catalog:
        for b in book.catalog:
            if a != b and (night_id, a, b) not in book.fees:
                return "E_BAD_FEE"
    return None


def best_plan(book: Book, night_id: str, jobs: list, holding: dict) -> dict:
    """Maximum-net plan of one night as {job_id: bay_id}.

    Jobs are visited by start time. A state records, per bay, the family it holds and the minute
    it becomes free, plus the minute the crew becomes free. A free minute at least the longest
    crew lead time before the current start can never constrain a later job, so it is stored as 0
    and such states merge. On equal nets the prefix that is smaller in the stated tie order is
    kept: both prefixes share every possible future, so the prefix alone decides."""
    bay_ids = [b["bay_id"] for b in book.bays]
    rate = {b["bay_id"]: b["minute_rate"] for b in book.bays}
    terms = {(a, b): v for (n, a, b), v in book.fees.items() if n == night_id}
    lead = max((c for _, c in terms.values()), default=0)
    must = set(book.mandatory.get(night_id, []))
    order = sorted(jobs, key=lambda j: (j["start"], j["job_id"]))
    id_rank = {j["job_id"]: i for i, j in enumerate(sorted(jobs, key=lambda j: j["job_id"]))}
    layers = []

    def tie_key(depth, prev, pick):
        picks = [(id_rank[order[depth]["job_id"]], pick)]
        while depth > 0:
            depth -= 1
            _, prev, pick_here = layers[depth][prev]
            picks.append((id_rank[order[depth]["job_id"]], pick_here))
        picks.sort()
        return [1 if p else 0 for _, p in picks] + [p for _, p in picks]

    frontier = {(tuple((holding[b], 0) for b in bay_ids), 0): (0, None, None)}
    for depth, job in enumerate(order):
        start, end, fam = job["start"], job["end"], job["family"]
        cut = start - lead
        nxt = {}

        def offer(lanes, crew_free, value, prev, pick):
            key = (tuple((f, e if e > cut else 0) for f, e in lanes), crew_free if crew_free > cut else 0)
            held = nxt.get(key)
            if held is None or value > held[0]:
                nxt[key] = (value, prev, pick)
            elif value == held[0] and tie_key(depth, prev, pick) < tie_key(depth, held[1], held[2]):
                nxt[key] = (value, prev, pick)

        for key, (value, _, _) in frontier.items():
            lanes, crew = key
            if job["job_id"] not in must:
                offer(lanes, crew, value, key, 0)
            for pos, bay in enumerate(bay_ids):
                if fam not in book.qualified[bay]:
                    continue
                held_fam, free = lanes[pos]
                if start < free:
                    continue
                gain = job["value"] - rate[bay] * (end - start)
                crew_free = crew
                if fam != held_fam and free == start:
                    fee, minutes = terms[(held_fam, fam)]
                    if start - minutes < max(free, crew):
                        continue
                    gain -= fee
                    crew_free = start
                lane_list = list(lanes)
                lane_list[pos] = (fam, end)
                offer(lane_list, crew_free, value + gain, key, pos + 1)
        if not nxt:
            nxt = {k: (v, k, 0) for k, (v, _, _) in frontier.items()}
        layers.append(nxt)
        frontier = nxt

    if not order:
        return {}
    last = len(order) - 1
    top = max(v for v, _, _ in frontier.values())
    key = min((k for k, (v, _, _) in frontier.items() if v == top),
              key=lambda k: tie_key(last, frontier[k][1], frontier[k][2]))
    plan = {}
    for depth in range(last, -1, -1):
        _, prev, pick = layers[depth][key]
        if pick:
            plan[order[depth]["job_id"]] = bay_ids[pick - 1]
        key = prev
    return plan


def main(argv: list) -> int:
    if len(argv) != 3:
        print("usage: derive_report.py <data_dir> <out_dir>", file=sys.stderr)
        return 2
    data, out = Path(argv[1]), Path(argv[2])
    for name in INPUTS:
        if not (data / name).is_file():
            print("missing input file: %s" % name, file=sys.stderr)
            return 1
    book = Book(data)
    rows_of = {}
    for r in book.job_rows:
        rows_of.setdefault(r["night_id"], []).append(r)
    rate = {b["bay_id"]: b["minute_rate"] for b in book.bays}
    holding = {b["bay_id"]: b["initial_family"] for b in book.bays}
    summary, audit_rows, rejected = [], [], []
    region_rows = {g: [] for g in REGIONS}
    segment_rows = {g: [] for g in SEGMENTS}

    for night in book.nights:
        nid = night["id"]
        rows = rows_of.get(nid, [])
        code = rejection(book, nid, rows)
        if code:
            rejected.append({"night_id": nid, "code": code, "message": "night %s rejected: %s" % (nid, code)})
            summary.append({"night_id": nid, "date": night["date"], "status": "rejected", "plan": [],
                            "gross": 0, "bay_charge": 0, "fees": 0, "net": 0})
            audit_rows.append({"night_id": nid, "status": "rejected", "crew_windows": [], "crew_minutes": 0,
                               "families_after": dict(holding), "flags": []})
            continue
        jobs = []
        for r in rows:
            s, e = book.windows[r["window_id"]]
            jobs.append({"job_id": r["job_id"], "start": s, "end": e, "family": r["family"],
                         "value": int(r["value"]), "client_id": r["client_id"]})
        plan = best_plan(book, nid, jobs, holding)
        running = sorted((j for j in jobs if j["job_id"] in plan), key=lambda j: (j["start"], j["job_id"]))
        last_family = dict(holding)
        last_end = {}
        lines, windows, charges = [], [], 0
        for j in running:
            bay = plan[j["job_id"]]
            fee = 0
            if j["family"] != last_family[bay] and last_end.get(bay) == j["start"]:
                fee, minutes = book.fees[(nid, last_family[bay], j["family"])]
                windows.append({"bay_id": bay, "job_id": j["job_id"], "start": j["start"] - minutes,
                                "end": j["start"]})
            last_family[bay] = j["family"]
            last_end[bay] = j["end"]
            charge = rate[bay] * (j["end"] - j["start"])
            charges += charge
            j["net"] = j["value"] - charge - fee
            lines.append({"job_id": j["job_id"], "bay_id": bay, "start": j["start"], "end": j["end"],
                          "family": j["family"], "changeover_fee": fee})
        holding = last_family
        gross = sum(j["value"] for j in running)
        fees = sum(x["changeover_fee"] for x in lines)
        net = gross - charges - fees
        summary.append({"night_id": nid, "date": night["date"], "status": "accepted", "plan": lines,
                        "gross": gross, "bay_charge": charges, "fees": fees, "net": net})
        windows.sort(key=lambda w: w["start"])
        crew_minutes = sum(w["end"] - w["start"] for w in windows)
        flags = []
        if crew_minutes > book.crew_limit:
            flags.append("crew_load_high")
        if net < book.margin_floor:
            flags.append("low_margin")
        audit_rows.append({"night_id": nid, "status": "accepted", "crew_windows": windows,
                           "crew_minutes": crew_minutes, "families_after": dict(holding), "flags": sorted(flags)})
        for groups, key_of in ((region_rows, lambda j: book.region_of[book.site_of[j["client_id"]]]),
                               (segment_rows, lambda j: book.segment_of[j["client_id"]])):
            for g, entries in groups.items():
                mine = [j for j in running if key_of(j) == g]
                entries.append({"night_id": nid, "jobs_run": len(mine), "gross": sum(j["value"] for j in mine),
                                "net": sum(j["net"] for j in mine)})

    totals = {"accepted_nights": sum(n["status"] == "accepted" for n in summary),
              "rejected_nights": len(rejected), "jobs_run": sum(len(n["plan"]) for n in summary)}
    for k in ("gross", "bay_charge", "fees", "net"):
        totals[k] = sum(n[k] for n in summary)
    docs = {"summary.json": {"nights": summary, "totals": totals},
            "policy_audit.json": {"nights": audit_rows},
            "data_quality.json": {"rejected": rejected}}
    for label, groups in (("region", region_rows), ("segment", segment_rows)):
        for g, entries in groups.items():
            docs["%s_%s.json" % (label, g)] = {
                label: g, "nights": entries,
                "totals": {k: sum(e[k] for e in entries) for k in ("jobs_run", "gross", "net")}}
    out.mkdir(parents=True, exist_ok=True)
    for name, doc in docs.items():
        (out / name).write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

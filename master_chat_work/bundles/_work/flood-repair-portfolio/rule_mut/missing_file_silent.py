"""Flood repair portfolio report: python3 derive_report.py DATA_DIR OUT_DIR (standard library only)."""
import configparser
import csv
import io
import json
import os
import sys

ROUND_FILES = ("proposals.csv", "segment_codes.tsv", "permits.csv", "exclusions.json")
STATUSES = ("held", "applied", "withdrawn")
CLASSES = ("A", "B", "C", "D")
REGIONS = ("North", "South", "West", "East")
SEGMENT_DOCS = ("commercial", "public")


class InputError(Exception):
    pass


def read_text(data_dir, name):
    with open(os.path.join(data_dir, name), encoding="utf-8", newline="") as handle:
        return handle.read()


def table(text, delimiter):
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    return [row for row in rows[1:] if row]


def load(data_dir):
    with open(os.path.join(data_dir, "manifest.json"), encoding="utf-8") as handle:
        manifest = json.load(handle)
    for name in manifest["files"]:
        if not os.path.isfile(os.path.join(data_dir, name)):
            continue
    text = {name: read_text(data_dir, name) for name in manifest["files"]}
    rates = configparser.ConfigParser()
    rates.optionxform = str
    rates.read_string(text["benefits.ini"])
    sites = {}
    for line in text["sites.jsonl"].splitlines():
        if line.strip():
            entry = json.loads(line)
            sites[entry["site"]] = entry
    return {
        "book": manifest["book"],
        "order": list(manifest["files"]),
        "proposals": table(text["proposals.csv"], ","),
        "segments": table(text["segment_codes.tsv"], "\t"),
        "permits": table(text["permits.csv"], ","),
        "exclusions": json.loads(text["exclusions.json"]),
        "sites": sites,
        "regions": dict(table(text["region_codes.csv"], ",")),
        "crews": dict(table(text["crews.tsv"], "\t")),
        "segment_rate": {k: int(v) for k, v in rates["segment_rate"].items()},
        "risk_uplift": {k: int(v) for k, v in rates["risk_uplift"].items()},
        "queries": text["audit_queries.txt"].splitlines(),
    }


class Round:
    def __init__(self, rid):
        self.rid = rid
        self.rows = []
        self.segment_of = {}
        self.permits = []
        self.exclusions = []
        self.fault = None


def group_rounds(book):
    rounds = {}
    for number, row in enumerate(book["proposals"], 1):
        rounds.setdefault(row[0], Round(row[0])).rows.append((number, row[1:]))
    return rounds


def file_faults(book, rnd, name, numbered):
    """Yield (row number, code) for every faulty row of this round in one file."""
    ids = {fields[0] for _, fields in rnd.rows}
    site_ids = {fields[1] for _, fields in rnd.rows}
    seen = set()
    for number, fields in numbered:
        code = None
        if name == "proposals.csv":
            proposal, site, crew, households, override = fields
            if proposal in seen:
                code = "DUPLICATE_PROPOSAL"
            elif not (households.isdigit() and households.isascii() and 1 <= int(households) <= 60):
                code = "INVALID_INPUT"
            elif site not in book["sites"] or crew not in book["crews"]:
                code = "INVALID_INPUT"
            elif override not in ("",) + CLASSES:
                code = "INVALID_INPUT"
            seen.add(proposal)
        elif name == "segment_codes.tsv":
            if fields[0] not in ids:
                code = "UNKNOWN_PROPOSAL"
            elif fields[1] not in book["segment_rate"]:
                code = "INVALID_INPUT"
        elif name == "permits.csv":
            if fields[1] not in ids:
                code = "UNKNOWN_PROPOSAL"
            elif fields[2] not in STATUSES:
                code = "INVALID_INPUT"
        else:
            first, second = fields
            if any(x not in ids and x not in site_ids for x in (first, second)):
                code = "UNKNOWN_PROPOSAL"
            elif first == second:
                code = "INVALID_INPUT"
        if code:
            yield number, code


def attach(book, rounds):
    per_file = {name: {} for name in ROUND_FILES}
    per_file["proposals.csv"] = {rid: rnd.rows for rid, rnd in rounds.items()}
    for number, row in enumerate(book["segments"], 1):
        per_file["segment_codes.tsv"].setdefault(row[0], []).append((number, row[1:]))
    for number, row in enumerate(book["permits"], 1):
        per_file["permits.csv"].setdefault(row[0], []).append((number, row[1:]))
    for number, entry in enumerate(book["exclusions"], 1):
        per_file["exclusions.json"].setdefault(entry["round"], []).append(
            (number, [entry["first"], entry["second"]]))
    for rid, rnd in rounds.items():
        rnd.segment_of = {f[0]: f[1] for _, f in per_file["segment_codes.tsv"].get(rid, [])}
        rnd.permits = [f for _, f in per_file["permits.csv"].get(rid, [])]
        rnd.exclusions = [f for _, f in per_file["exclusions.json"].get(rid, [])]
        for name in book["order"]:
            if name in ROUND_FILES:
                hit = next(file_faults(book, rnd, name, per_file[name].get(rid, [])), None)
                if hit:
                    rnd.fault = {"round": rid, "code": hit[1], "file": name, "row": hit[0]}
                    break


def value(book, rnd):
    rnd.ids, rnd.detail = [], {}
    for number, (proposal, site, crew, households, override) in rnd.rows:
        segment = rnd.segment_of[proposal]
        risk = override or book["sites"][site]["risk_class"]
        h = int(households)
        premium = book["sites"][site]["premium"]
        benefit = h * (book["segment_rate"][segment] + book["risk_uplift"][risk]) + premium
        rnd.ids.append(proposal)
        rnd.detail[proposal] = {"site": site, "crew": crew, "segment": segment, "risk": risk,
                                "households": h, "premium": premium, "benefit": benefit,
                                "region": book["regions"][site]}
        if benefit < 1 and rnd.fault is None:
            rnd.fault = {"round": rnd.rid, "code": "NONPOSITIVE_BENEFIT", "file": "proposals.csv",
                         "row": number}


def conflicts(book, rnd):
    """Map each conflicting pair (sorted ids) to the set of sources that make it conflict."""
    pairs = {}

    def mark(group_a, group_b, source):
        for a in group_a:
            for b in group_b:
                if a != b:
                    pairs.setdefault((min(a, b), max(a, b)), set()).add(source)

    by_crew, by_site, by_permit = {}, {}, {}
    for pid, d in rnd.detail.items():
        by_crew.setdefault(d["crew"], []).append(pid)
        by_site.setdefault(d["site"], []).append(pid)
    for crew, members in by_crew.items():
        if book["crews"][crew] == "exclusive":
            mark(members, members, "crew")
    for permit, pid, status in rnd.permits:
        if status != "withdrawn":
            by_permit.setdefault(permit, []).append(pid)
    for members in by_permit.values():
        mark(members, members, "permit")
    for first, second in rnd.exclusions:
        mark(by_site.get(first, [first]) if first not in rnd.detail else [first],
             by_site.get(second, [second]) if second not in rnd.detail else [second], "exclusion")
    return pairs


def sweep_order(vertices, adj):
    """Breadth-first order from a far vertex; keeps the start with the narrowest frontier."""
    def bfs(start):
        order, seen = [start], {start}
        for v in order:
            for u in sorted(adj[v] - seen, key=lambda x: (len(adj[x]), x)):
                seen.add(u)
                order.append(u)
        return order

    def width(order):
        pos = {v: i for i, v in enumerate(order)}
        last = {v: max([pos[u] for u in adj[v]] + [pos[v]]) for v in order}
        live, best = 0, 0
        ends = [0] * (len(order) + 1)
        for i, v in enumerate(order):
            live += 1
            ends[last[v]] += 1
            live -= ends[i]
            best = max(best, live)
        return best

    starts = [min(vertices, key=lambda x: (len(adj[x]), x))]
    for _ in range(3):
        starts.append(bfs(starts[-1])[-1])
    starts += sorted(vertices, key=lambda x: (len(adj[x]), x))[:6]
    return min((bfs(s) for s in starts), key=width)


def best_set(weights, adj, vertices):
    """Maximum total weight independent set of one connected piece, by a frontier sweep."""
    order = sweep_order(vertices, adj)
    pos = {v: i for i, v in enumerate(order)}
    last = {v: max([pos[u] for u in adj[v]] + [pos[v]]) for v in order}
    bit = {v: 1 << i for i, v in enumerate(order)}
    states = {0: (0, 0)}
    frontier = 0
    for i, v in enumerate(order):
        earlier = 0
        for u in adj[v]:
            if pos[u] < i:
                earlier |= bit[u]
        frontier |= bit[v]
        keep = frontier
        for u in order[:i + 1]:
            if last[u] <= i:
                keep &= ~bit[u]
        frontier = keep
        nxt = {}
        for key, (score, chosen) in states.items():
            for take in (False, True):
                if take and key & earlier:
                    continue
                k2 = (key | bit[v]) & keep if take else key & keep
                cand = (score + weights[v], chosen | bit[v]) if take else (score, chosen)
                old = nxt.get(k2)
                if old is None or cand[0] > old[0]:
                    nxt[k2] = cand
        states = nxt
    score, chosen = max(states.values())
    return [v for v in order if chosen & bit[v]]


def choose(rnd, pairs):
    ids = sorted(rnd.ids)
    n = len(ids)
    rank = {pid: i for i, pid in enumerate(ids)}
    weights = {pid: rnd.detail[pid]["benefit"] * (1 << n) + (1 << (n - 1 - rank[pid])) for pid in ids}
    adj = {pid: set() for pid in ids}
    for a, b in pairs:
        adj[a].add(b)
        adj[b].add(a)
    seen, picked = set(), []
    for pid in ids:
        if pid in seen:
            continue
        piece, stack = [], [pid]
        seen.add(pid)
        while stack:
            v = stack.pop()
            piece.append(v)
            for u in adj[v] - seen:
                seen.add(u)
                stack.append(u)
        picked += best_set(weights, adj, piece)
    return sorted(picked)


def build(book):
    rounds = group_rounds(book)
    attach(book, rounds)
    for rnd in rounds.values():
        if rnd.fault is None:
            value(book, rnd)
    for rnd in rounds.values():
        if rnd.fault is None:
            rnd.pairs = conflicts(book, rnd)
            rnd.selected = choose(rnd, rnd.pairs)
            rnd.total = sum(rnd.detail[p]["benefit"] for p in rnd.selected)
    return [rounds[rid] for rid in sorted(rounds)]


def documents(book, ordered):
    planned = [r for r in ordered if r.fault is None]
    docs = {}
    docs["summary.json"] = {
        "book": book["book"],
        "rounds": [{"round": r.rid, "status": "rejected" if r.fault else "planned", "proposals": len(r.rows),
                    "selected": [] if r.fault else r.selected, "total_benefit": 0 if r.fault else r.total}
                   for r in ordered],
        "planned_rounds": len(planned),
        "rejected_rounds": len(ordered) - len(planned),
        "selected_proposals": sum(len(r.selected) for r in planned),
        "total_benefit": sum(r.total for r in planned),
    }
    by_id = {r.rid: r for r in ordered}
    rows = []
    for line_no, line in enumerate(book["queries"], 1):
        parts = line.split()
        if not parts:
            continue
        rnd = by_id[parts[1]]
        row = {"line": line_no, "kind": parts[0], "round": rnd.rid,
               "status": "rejected" if rnd.fault else "planned"}
        if rnd.fault is None and parts[0] == "VALUE":
            d = rnd.detail[parts[2]]
            row.update({"proposal": parts[2], "segment": d["segment"],
                        "segment_rate": book["segment_rate"][d["segment"]], "risk_class": d["risk"],
                        "risk_uplift": book["risk_uplift"][d["risk"]], "households": d["households"],
                        "premium": d["premium"], "benefit": d["benefit"], "selected": parts[2] in rnd.selected})
        elif rnd.fault is None:
            a, b = parts[2], parts[3]
            found = rnd.pairs.get((min(a, b), max(a, b)), set())
            row.update({"first": a, "second": b,
                        "sources": [s for s in ("crew", "permit", "exclusion") if s in found],
                        "conflict": bool(found), "first_selected": a in rnd.selected,
                        "second_selected": b in rnd.selected})
        rows.append(row)
    docs["policy_audit.json"] = {"book": book["book"], "rows": rows}
    by_source = {s: sum(1 for r in planned for v in r.pairs.values() if s in v)
                 for s in ("crew", "permit", "exclusion")}
    docs["data_quality.json"] = {
        "book": book["book"],
        "rejected": [r.fault for r in ordered if r.fault],
        "planned_rounds": len(planned),
        "rejected_rounds": len(ordered) - len(planned),
        "conflict_pairs": sum(len(r.pairs) for r in planned),
        "conflicts_by_source": by_source,
        "withdrawn_permit_rows": sum(1 for r in planned for p in r.permits if p[2] == "withdrawn"),
    }
    for key, names, field in (("region", REGIONS, "region"), ("segment", SEGMENT_DOCS, "segment")):
        for name in names:
            entries = []
            for r in planned:
                mine = [p for p in r.selected if r.detail[p][field] == name]
                entries.append({"round": r.rid, "selected": mine,
                                "benefit": sum(r.detail[p]["benefit"] for p in mine)})
            docs["%s_%s.json" % (key, name)] = {
                "book": book["book"], key: name, "rounds": entries,
                "selected_proposals": sum(len(e["selected"]) for e in entries),
                "total_benefit": sum(e["benefit"] for e in entries)}
    return docs


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py DATA_DIR OUT_DIR\n")
        return 2
    try:
        book = load(argv[1])
    except InputError as exc:
        sys.stderr.write(str(exc) + "\n")
        return 1
    docs = documents(book, build(book))
    os.makedirs(argv[2], exist_ok=True)
    for name, doc in docs.items():
        with open(os.path.join(argv[2], name), "w", encoding="utf-8") as handle:
            json.dump(doc, handle, indent=2)
            handle.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

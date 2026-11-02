#!/usr/bin/env python3
"""Derive the report documents of a flood repair funding book.

Usage: python3 derive_report.py DATA_DIR OUT_DIR
"""

import csv
import json
import os
import sys

REGIONS = ("North", "South", "West", "East")
SEGMENT_DOCS = ("commercial", "public")
ROUND_SCOPED = ("proposals.csv", "segment_codes.tsv", "permits.csv", "exclusions.json")
SOURCES = ("crew", "permit", "exclusion")


def read_lines(path):
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return [ln[:-1] if ln.endswith("\r") else ln for ln in lines]


def read_table(path, delim, columns):
    """Return a list of (row_number, dict) for data rows of a delimited file."""
    lines = read_lines(path)
    if not lines:
        return []
    header = next(csv.reader([lines[0]], delimiter=delim))
    index = {}
    for pos, name in enumerate(header):
        index[name.strip()] = pos
    for pos, name in enumerate(columns):
        if name not in index:
            index[name] = pos
    out = []
    number = 0
    for raw in lines[1:]:
        if raw.strip() == "":
            continue
        number += 1
        fields = next(csv.reader([raw], delimiter=delim))
        row = {}
        for name in columns:
            pos = index[name]
            row[name] = fields[pos] if pos < len(fields) else ""
        out.append((number, row))
    return out


def read_ini(path):
    sections = {}
    current = None
    for raw in read_lines(path):
        line = raw.strip()
        if line == "" or line[0] in (";", "#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip()
            sections.setdefault(current, {})
            continue
        if current is None:
            continue
        if "=" in line:
            key, value = line.split("=", 1)
        elif ":" in line:
            key, value = line.split(":", 1)
        else:
            continue
        sections[current][key.strip()] = value.strip()
    return sections


DIGITS = frozenset("0123456789")


def is_count(text, low, high):
    if not text or not DIGITS.issuperset(text):
        return False
    return low <= int(text) <= high


class Book:
    def __init__(self, data_dir):
        self.dir = data_dir
        manifest_path = os.path.join(data_dir, "manifest.json")
        with open(manifest_path, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
        self.book = manifest["book"]
        self.declared = list(manifest["files"])
        for name in self.declared:
            if not os.path.exists(os.path.join(data_dir, name)):
                sys.stderr.write("ERROR MISSING_FILE %s\n" % name)
                sys.exit(1)
        self.load()

    def path(self, name):
        return os.path.join(self.dir, name)

    def load(self):
        self.proposal_rows = read_table(
            self.path("proposals.csv"),
            ",",
            ["round", "proposal", "site", "crew", "households", "risk_override"],
        )
        self.segment_rows = read_table(
            self.path("segment_codes.tsv"), "\t", ["round", "proposal", "segment"]
        )
        self.permit_rows = read_table(
            self.path("permits.csv"), ",", ["round", "permit", "proposal", "status"]
        )
        self.region_rows = read_table(self.path("region_codes.csv"), ",", ["site", "region"])
        self.crew_rows = read_table(self.path("crews.tsv"), "\t", ["crew", "mode"])

        self.sites = {}
        for raw in read_lines(self.path("sites.jsonl")):
            if raw.strip() == "":
                continue
            obj = json.loads(raw)
            self.sites[obj["site"]] = (obj["risk_class"], int(obj["premium"]))

        self.regions = {}
        for _, row in self.region_rows:
            self.regions[row["site"]] = row["region"]

        self.crew_mode = {}
        for _, row in self.crew_rows:
            self.crew_mode[row["crew"]] = row["mode"]

        with open(self.path("exclusions.json"), "r", encoding="utf-8") as fh:
            entries = json.load(fh)
        self.exclusion_rows = [(i + 1, obj) for i, obj in enumerate(entries)]

        ini = read_ini(self.path("benefits.ini"))
        self.segment_rate = {k: int(v) for k, v in ini.get("segment_rate", {}).items()}
        self.risk_uplift = {k: int(v) for k, v in ini.get("risk_uplift", {}).items()}

        self.query_lines = read_lines(self.path("audit_queries.txt"))

        self.by_round = {name: {} for name in ROUND_SCOPED}
        for number, row in self.proposal_rows:
            self.by_round["proposals.csv"].setdefault(row["round"], []).append((number, row))
        for number, row in self.segment_rows:
            self.by_round["segment_codes.tsv"].setdefault(row["round"], []).append(
                (number, row)
            )
        for number, row in self.permit_rows:
            self.by_round["permits.csv"].setdefault(row["round"], []).append((number, row))
        for number, obj in self.exclusion_rows:
            self.by_round["exclusions.json"].setdefault(obj.get("round"), []).append(
                (number, obj)
            )

        self.round_ids = sorted(self.by_round["proposals.csv"].keys())


def check_proposals(book, rid):
    seen = set()
    for number, row in book.by_round["proposals.csv"].get(rid, ()):
        pid = row["proposal"]
        if pid in seen:
            return ("DUPLICATE_PROPOSAL", number)
        seen.add(pid)
        if not is_count(row["households"], 1, 60):
            return ("INVALID_INPUT", number)
        if row["site"] not in book.sites:
            return ("INVALID_INPUT", number)
        if row["crew"] not in book.crew_mode:
            return ("INVALID_INPUT", number)
        if row["risk_override"] not in ("", "A", "B", "C", "D"):
            return ("INVALID_INPUT", number)
    return None


def check_segments(book, rid, proposals):
    for number, row in book.by_round["segment_codes.tsv"].get(rid, ()):
        if row["proposal"] not in proposals:
            return ("UNKNOWN_PROPOSAL", number)
        if row["segment"] not in book.segment_rate:
            return ("INVALID_INPUT", number)
    return None


def check_permits(book, rid, proposals):
    for number, row in book.by_round["permits.csv"].get(rid, ()):
        if row["proposal"] not in proposals:
            return ("UNKNOWN_PROPOSAL", number)
        if row["status"] not in ("held", "applied", "withdrawn"):
            return ("INVALID_INPUT", number)
    return None


def check_exclusions(book, rid, proposals, sites):
    for number, obj in book.by_round["exclusions.json"].get(rid, ()):
        first = obj.get("first")
        second = obj.get("second")
        for token in (first, second):
            if token not in proposals and token not in sites:
                return ("UNKNOWN_PROPOSAL", number)
        if first == second:
            return ("INVALID_INPUT", number)
    return None


def check_round(book, rid):
    proposals = set()
    sites = set()
    for _, row in book.by_round["proposals.csv"].get(rid, ()):
        proposals.add(row["proposal"])
        sites.add(row["site"])
    for name in book.declared:
        if name not in ROUND_SCOPED:
            continue
        if name == "proposals.csv":
            fault = check_proposals(book, rid)
        elif name == "segment_codes.tsv":
            fault = check_segments(book, rid, proposals)
        elif name == "permits.csv":
            fault = check_permits(book, rid, proposals)
        else:
            fault = check_exclusions(book, rid, proposals, sites)
        if fault is not None:
            return (fault[0], name, fault[1])
    return None


def value_round(book, rid):
    """Value every proposal row of a checked round."""
    segments = {}
    for _, row in book.by_round["segment_codes.tsv"].get(rid, ()):
        segments.setdefault(row["proposal"], row["segment"])
    records = []
    for number, row in book.by_round["proposals.csv"].get(rid, ()):
        site = row["site"]
        risk_class, premium = book.sites[site]
        if row["risk_override"] != "":
            risk_class = row["risk_override"]
        segment = segments[row["proposal"]]
        rate = book.segment_rate[segment]
        uplift = book.risk_uplift[risk_class]
        households = int(row["households"])
        records.append(
            {
                "row": number,
                "proposal": row["proposal"],
                "site": site,
                "crew": row["crew"],
                "households": households,
                "segment": segment,
                "segment_rate": rate,
                "risk_class": risk_class,
                "risk_uplift": uplift,
                "premium": premium,
                "benefit": households * (rate + uplift) + premium,
            }
        )
    for record in records:
        if record["benefit"] < 1:
            return records, ("NONPOSITIVE_BENEFIT", "proposals.csv", record["row"])
    return records, None


def conflict_pairs(book, rid, records):
    proposals = {r["proposal"] for r in records}
    pairs = {}

    def add(a, b, source):
        if a == b:
            return
        key = (a, b) if a < b else (b, a)
        bucket = pairs.get(key)
        if bucket is None:
            pairs[key] = {source}
        else:
            bucket.add(source)

    crews = {}
    for record in records:
        if book.crew_mode.get(record["crew"]) == "exclusive":
            crews.setdefault(record["crew"], []).append(record["proposal"])
    for members in crews.values():
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                add(members[i], members[j], "crew")

    permits = {}
    for _, row in book.by_round["permits.csv"].get(rid, ()):
        if row["status"] not in ("held", "applied"):
            continue
        members = permits.setdefault(row["permit"], [])
        if row["proposal"] not in members:
            members.append(row["proposal"])
    for members in permits.values():
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                add(members[i], members[j], "permit")

    by_site = {}
    for record in records:
        by_site.setdefault(record["site"], []).append(record["proposal"])

    def expand(token):
        if token in proposals:
            return (token,)
        return by_site.get(token, ())

    for _, obj in book.by_round["exclusions.json"].get(rid, ()):
        for a in expand(obj.get("first")):
            for b in expand(obj.get("second")):
                add(a, b, "exclusion")

    return pairs


FILL_CANDIDATES = 16


def elimination_rank(adj, size):
    """Rank the nodes by a greedy elimination order (least degree, least fill).

    Branching on the node eliminated last keeps subproblems separable, which
    makes the memoised search behave like a dynamic program over a tree
    decomposition of the conflict graph.
    """
    fill = list(adj)
    live = (1 << size) - 1
    rank = [0] * size
    step = 0
    while live:
        least = size + 1
        candidates = []
        rest = live
        while rest:
            bit = rest & -rest
            rest ^= bit
            node = bit.bit_length() - 1
            degree = bin(fill[node] & live).count("1")
            if degree < least:
                least = degree
                candidates = [node]
            elif degree == least and len(candidates) < FILL_CANDIDATES:
                candidates.append(node)
        pivot = candidates[0]
        if len(candidates) > 1:
            best = None
            for node in candidates:
                nbrs = fill[node] & live
                missing = 0
                inner = nbrs
                while inner:
                    ibit = inner & -inner
                    inner ^= ibit
                    missing += bin(
                        nbrs & ~fill[ibit.bit_length() - 1] & ~ibit
                    ).count("1")
                if best is None or missing < best:
                    best = missing
                    pivot = node
        nbrs = fill[pivot] & live
        inner = nbrs
        while inner:
            ibit = inner & -inner
            inner ^= ibit
            fill[ibit.bit_length() - 1] |= nbrs & ~ibit
        live &= ~(1 << pivot)
        rank[pivot] = step
        step += 1
    return rank


class Planner:
    """Exact maximum weight independent set over a round's conflict graph."""

    def __init__(self, adj, weight):
        self.adj = adj
        self.weight = weight
        self.size = len(weight)
        rank = elimination_rank(adj, self.size)
        self.order = sorted(range(self.size), key=lambda node: -rank[node])
        self.pairsum = []
        for node in range(self.size):
            around = []
            rest = adj[node]
            while rest:
                bit = rest & -rest
                rest ^= bit
                around.append(weight[bit.bit_length() - 1])
            around.sort()
            self.pairsum.append(sum(around[:2]))
        self.exact = {}
        self.upper = {}

    def split(self, mask):
        adj = self.adj
        out = []
        rest = mask
        while rest:
            group = rest & -rest
            frontier = group
            while frontier:
                reach = 0
                left = frontier
                while left:
                    bit = left & -left
                    left ^= bit
                    reach |= adj[bit.bit_length() - 1]
                frontier = reach & mask & ~group
                group |= frontier
            out.append(group)
            rest &= ~group
        return out

    def bound(self, mask):
        """Clique cover bound: each clique contributes its heaviest node."""
        adj = self.adj
        weight = self.weight
        total = 0
        rest = mask
        while rest:
            bit = rest & -rest
            node = bit.bit_length() - 1
            heaviest = weight[node]
            clique = bit
            candidates = adj[node] & rest
            while candidates:
                other = candidates & -candidates
                index = other.bit_length() - 1
                clique |= other
                if weight[index] > heaviest:
                    heaviest = weight[index]
                candidates &= adj[index]
            total += heaviest
            rest &= ~clique
        return total

    def solve(self, mask, alpha):
        """Solve the subgraph `mask`.

        Returns `(value, set)` with the optimum and its chosen set whenever the
        optimum reaches `alpha`; otherwise `value` is only an upper bound of the
        optimum and the set is empty. Among sets of equal value the one chosen
        is the one whose sorted id list is smaller, which here means the one
        holding the lowest node of the difference.
        """
        if mask == 0:
            return (0, 0)
        found = self.exact.get(mask)
        if found is not None:
            return found
        known = self.upper.get(mask)
        if known is not None and known < alpha:
            return (known, 0)
        weight = self.weight
        adj = self.adj
        if mask & (mask - 1) == 0:
            result = (weight[mask.bit_length() - 1], mask)
            self.exact[mask] = result
            return result
        parts = self.split(mask)
        if len(parts) > 1:
            total = 0
            union = 0
            for part in parts:
                value, chosen = self.solve(part, 0)
                total += value
                union |= chosen
            result = (total, union)
            self.exact[mask] = result
            return result
        limit = self.bound(mask)
        if limit < alpha:
            if known is None or limit < known:
                self.upper[mask] = limit
            return (limit, 0)
        forced = -1
        pairsum = self.pairsum
        rest = mask
        while rest:
            bit = rest & -rest
            rest ^= bit
            node = bit.bit_length() - 1
            nbrs = adj[node] & mask
            own = weight[node]
            if nbrs == 0:
                forced = node
                break
            if nbrs & (nbrs - 1) == 0:
                if own > weight[nbrs.bit_length() - 1]:
                    forced = node
                    break
            elif own > pairsum[node]:
                around = 0
                inner = nbrs
                while inner:
                    ibit = inner & -inner
                    inner ^= ibit
                    around += weight[ibit.bit_length() - 1]
                if own > around:
                    forced = node
                    break
        if forced >= 0:
            fbit = 1 << forced
            own = weight[forced]
            value, chosen = self.solve(mask & ~fbit & ~adj[forced], alpha - own)
            result = (value + own, chosen | fbit)
        else:
            for pivot in self.order:
                if mask >> pivot & 1:
                    break
            pbit = 1 << pivot
            own = weight[pivot]
            value, chosen = self.solve(mask & ~pbit & ~adj[pivot], alpha - own)
            result = (value + own, chosen | pbit)
            raised = result[0] if result[0] > alpha else alpha
            other, other_set = self.solve(mask & ~pbit, raised)
            if other > result[0]:
                result = (other, other_set)
            elif other == result[0] and other >= raised:
                diff = other_set ^ result[1]
                if diff & -diff & other_set:
                    result = (other, other_set)
        if result[0] >= alpha:
            self.exact[mask] = result
        else:
            if known is None or result[0] < known:
                self.upper[mask] = result[0]
            result = (result[0], 0)
        return result

    def best_set(self):
        """The optimal set that is smallest in the contract's id-list order."""
        return self.solve((1 << self.size) - 1, 0)[1]


def plan_round(records, pairs):
    ids = sorted(r["proposal"] for r in records)
    index = {pid: i for i, pid in enumerate(ids)}
    weight = [0] * len(ids)
    for record in records:
        weight[index[record["proposal"]]] = record["benefit"]
    adj = [0] * len(ids)
    for a, b in pairs:
        ia = index[a]
        ib = index[b]
        adj[ia] |= 1 << ib
        adj[ib] |= 1 << ia
    mask = Planner(adj, weight).best_set()
    return [ids[i] for i in range(len(ids)) if mask >> i & 1]


def build_rounds(book):
    rounds = []
    for rid in book.round_ids:
        info = {
            "round": rid,
            "proposals": len(book.by_round["proposals.csv"][rid]),
            "status": "rejected",
            "fault": None,
            "records": {},
            "selected": [],
            "total_benefit": 0,
            "pairs": {},
        }
        fault = check_round(book, rid)
        if fault is None:
            records, fault = value_round(book, rid)
            info["records"] = {r["proposal"]: r for r in records}
            if fault is None:
                info["status"] = "planned"
                info["pairs"] = conflict_pairs(book, rid, records)
                info["selected"] = plan_round(records, info["pairs"])
                info["total_benefit"] = sum(
                    info["records"][pid]["benefit"] for pid in info["selected"]
                )
        if fault is not None:
            info["fault"] = {
                "round": rid,
                "code": fault[0],
                "file": fault[1],
                "row": fault[2],
            }
        rounds.append(info)
    return rounds


def write_doc(out_dir, name, payload):
    with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")


def summary_doc(book, rounds):
    listing = [
        {
            "round": info["round"],
            "status": info["status"],
            "proposals": info["proposals"],
            "selected": list(info["selected"]),
            "total_benefit": info["total_benefit"],
        }
        for info in rounds
    ]
    return {
        "book": book.book,
        "rounds": listing,
        "planned_rounds": sum(1 for i in rounds if i["status"] == "planned"),
        "rejected_rounds": sum(1 for i in rounds if i["status"] == "rejected"),
        "selected_proposals": sum(len(i["selected"]) for i in rounds),
        "total_benefit": sum(i["total_benefit"] for i in rounds),
    }


def policy_doc(book, rounds):
    index = {info["round"]: info for info in rounds}
    rows = []
    for number, raw in enumerate(book.query_lines, start=1):
        if raw.strip() == "":
            continue
        parts = raw.split()
        kind = parts[0]
        rid = parts[1]
        info = index[rid]
        row = {"line": number, "kind": kind, "round": rid, "status": info["status"]}
        if info["status"] == "planned":
            chosen = set(info["selected"])
            if kind == "VALUE":
                pid = parts[2]
                record = info["records"][pid]
                row["proposal"] = pid
                row["segment"] = record["segment"]
                row["segment_rate"] = record["segment_rate"]
                row["risk_class"] = record["risk_class"]
                row["risk_uplift"] = record["risk_uplift"]
                row["households"] = record["households"]
                row["premium"] = record["premium"]
                row["benefit"] = record["benefit"]
                row["selected"] = pid in chosen
            else:
                first = parts[2]
                second = parts[3]
                key = (first, second) if first < second else (second, first)
                found = info["pairs"].get(key, ())
                row["first"] = first
                row["second"] = second
                row["sources"] = [s for s in SOURCES if s in found]
                row["conflict"] = bool(row["sources"])
                row["first_selected"] = first in chosen
                row["second_selected"] = second in chosen
        rows.append(row)
    return {"book": book.book, "rows": rows}


def quality_doc(book, rounds):
    planned = {i["round"] for i in rounds if i["status"] == "planned"}
    rejected = [i["fault"] for i in rounds if i["status"] == "rejected"]
    pair_total = 0
    by_source = {s: 0 for s in SOURCES}
    for info in rounds:
        if info["status"] != "planned":
            continue
        for sources in info["pairs"].values():
            pair_total += 1
            for source in sources:
                by_source[source] += 1
    withdrawn = 0
    for _, row in book.permit_rows:
        if row["status"] == "withdrawn" and row["round"] in planned:
            withdrawn += 1
    return {
        "book": book.book,
        "rejected": rejected,
        "planned_rounds": len(planned),
        "rejected_rounds": len(rejected),
        "conflict_pairs": pair_total,
        "conflicts_by_source": by_source,
        "withdrawn_permit_rows": withdrawn,
    }


def slice_doc(book, rounds, key, value, pick):
    listing = []
    total = 0
    count = 0
    for info in rounds:
        if info["status"] != "planned":
            continue
        chosen = [pid for pid in info["selected"] if pick(info["records"][pid])]
        benefit = sum(info["records"][pid]["benefit"] for pid in chosen)
        listing.append({"round": info["round"], "selected": chosen, "benefit": benefit})
        total += benefit
        count += len(chosen)
    return {
        "book": book.book,
        key: value,
        "rounds": listing,
        "selected_proposals": count,
        "total_benefit": total,
    }


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir, out_dir = argv[1], argv[2]
    sys.setrecursionlimit(20000)
    book = Book(data_dir)
    rounds = build_rounds(book)
    os.makedirs(out_dir, exist_ok=True)
    write_doc(out_dir, "summary.json", summary_doc(book, rounds))
    write_doc(out_dir, "policy_audit.json", policy_doc(book, rounds))
    write_doc(out_dir, "data_quality.json", quality_doc(book, rounds))
    for region in REGIONS:
        write_doc(
            out_dir,
            "region_%s.json" % region,
            slice_doc(
                book,
                rounds,
                "region",
                region,
                lambda r, region=region: book.regions.get(r["site"]) == region,
            ),
        )
    for segment in SEGMENT_DOCS:
        write_doc(
            out_dir,
            "segment_%s.json" % segment,
            slice_doc(
                book,
                rounds,
                "segment",
                segment,
                lambda r, segment=segment: r["segment"] == segment,
            ),
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

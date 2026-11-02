#!/usr/bin/env python3
"""Flood repair funding book: report deriver.

Usage: python3 derive_report.py DATA_DIR OUT_DIR
"""

import csv
import json
import os
import sys
import time
from collections import defaultdict

RISK_CLASSES = ("A", "B", "C", "D")
PERMIT_STATUSES = ("held", "applied", "withdrawn")
ROUND_FILES = ("proposals.csv", "segment_codes.tsv", "permits.csv", "exclusions.json")
REGIONS = ("North", "South", "West", "East")
SEGMENT_DOCS = ("commercial", "public")
DP_DEADLINE = 14.0
DP_RATE = 500000
DP_FLOOR = 300000
START = time.monotonic()


def dp_budget():
    """How many dynamic programming states are still affordable.

    Both planners are exact, so this time-dependent choice between them
    changes only the running time, never the chosen portfolio.
    """
    left = DP_DEADLINE - (time.monotonic() - START)
    return max(DP_FLOOR, int(left * DP_RATE))


def read_lines(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        return fh.read().splitlines()


def table_dicts(path, delimiter):
    """Return [(row_number, field_dict)] for a header-bearing table."""
    lines = read_lines(path)
    if not lines:
        return []
    header = [h.strip() for h in next(csv.reader([lines[0]], delimiter=delimiter))]
    out = []
    number = 0
    for line in lines[1:]:
        if not line.strip():
            continue
        number += 1
        fields = next(csv.reader([line], delimiter=delimiter))
        rec = {}
        for i, name in enumerate(header):
            rec[name] = fields[i] if i < len(fields) else ""
        out.append((number, rec))
    return out


def read_ini(path):
    sections = {}
    current = None
    for line in read_lines(path):
        stripped = line.strip()
        if not stripped or stripped[0] in "#;":
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            current = stripped[1:-1].strip()
            sections.setdefault(current, {})
            continue
        if current is None or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        sections[current][key.strip()] = value.strip()
    return sections


def is_count(text, low, high):
    if not text or not text.isdigit() or not text.isascii():
        return False
    return low <= int(text) <= high


class Book(object):
    def __init__(self, data_dir):
        self.data_dir = data_dir
        with open(os.path.join(data_dir, "manifest.json"), encoding="utf-8") as fh:
            manifest = json.load(fh)
        self.book = manifest["book"]
        self.declared = list(manifest["files"])
        for name in self.declared:
            if not os.path.exists(os.path.join(data_dir, name)):
                sys.stderr.write("ERROR MISSING_FILE %s\n" % name)
                sys.exit(1)
        self.load()

    def path(self, name):
        return os.path.join(self.data_dir, name)

    def load(self):
        self.sites = {}
        for line in read_lines(self.path("sites.jsonl")):
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec["site"] not in self.sites:
                self.sites[rec["site"]] = (rec["risk_class"], int(rec["premium"]))

        self.regions = {}
        for _, rec in table_dicts(self.path("region_codes.csv"), ","):
            self.regions.setdefault(rec["site"], rec["region"])

        self.crews = {}
        for _, rec in table_dicts(self.path("crews.tsv"), "\t"):
            self.crews.setdefault(rec["crew"], rec["mode"])

        benefits = read_ini(self.path("benefits.ini"))
        self.segment_rate = dict((k, int(v)) for k, v in
                                 benefits.get("segment_rate", {}).items())
        self.risk_uplift = dict((k, int(v)) for k, v in
                                benefits.get("risk_uplift", {}).items())

        self.proposal_rows = defaultdict(list)
        for number, rec in table_dicts(self.path("proposals.csv"), ","):
            self.proposal_rows[rec["round"]].append((number, rec))

        self.segment_rows = defaultdict(list)
        for number, rec in table_dicts(self.path("segment_codes.tsv"), "\t"):
            self.segment_rows[rec["round"]].append((number, rec))

        self.permit_rows = defaultdict(list)
        for number, rec in table_dicts(self.path("permits.csv"), ","):
            self.permit_rows[rec["round"]].append((number, rec))

        self.exclusion_rows = defaultdict(list)
        with open(self.path("exclusions.json"), encoding="utf-8") as fh:
            entries = json.load(fh)
        for index, entry in enumerate(entries, 1):
            self.exclusion_rows[entry["round"]].append((index, entry))

        self.queries = []
        for number, line in enumerate(read_lines(self.path("audit_queries.txt")), 1):
            if not line.strip():
                continue
            self.queries.append((number, line.split()))

        self.rounds = sorted(self.proposal_rows)


SHARED_CAP = 4

class RoundState(object):
    def __init__(self, book, rnd):
        self.book = book
        self.round = rnd
        self.rows = book.proposal_rows[rnd]
        self.ids = []
        self.first_row = {}
        self.site = {}
        self.crew = {}
        self.households = {}
        self.override = {}
        for number, rec in self.rows:
            pid = rec["proposal"]
            if pid not in self.first_row:
                self.ids.append(pid)
                self.first_row[pid] = number
                self.site[pid] = rec["site"]
                self.crew[pid] = rec["crew"]
                self.households[pid] = rec["households"]
                self.override[pid] = rec["risk_override"]
        self.id_set = set(self.ids)
        self.site_set = set(self.site.values())
        self.segment = {}
        for _, rec in book.segment_rows[rnd]:
            self.segment.setdefault(rec["proposal"], rec["segment"])
        self.fault = None
        self.status = "rejected"
        self.benefit = {}
        self.risk_class = {}
        self.selected = []
        self.total_benefit = 0
        self.pairs = {}

    # ---- checking -------------------------------------------------
    def check_proposals(self):
        seen = set()
        for number, rec in self.rows:
            pid = rec["proposal"]
            if pid in seen:
                return ("DUPLICATE_PROPOSAL", number)
            seen.add(pid)
            if not is_count(rec["households"], 1, 60):
                return ("INVALID_INPUT", number)
            if rec["site"] not in self.book.sites:
                return ("INVALID_INPUT", number)
            if rec["crew"] not in self.book.crews:
                return ("INVALID_INPUT", number)
            if rec["risk_override"] not in ("",) + RISK_CLASSES:
                return ("INVALID_INPUT", number)
        return None

    def check_segments(self):
        for number, rec in self.book.segment_rows[self.round]:
            if rec["proposal"] not in self.id_set:
                return ("UNKNOWN_PROPOSAL", number)
            if rec["segment"] not in self.book.segment_rate:
                return ("INVALID_INPUT", number)
        return None

    def check_permits(self):
        for number, rec in self.book.permit_rows[self.round]:
            if rec["proposal"] not in self.id_set:
                return ("UNKNOWN_PROPOSAL", number)
            if rec["status"] not in PERMIT_STATUSES:
                return ("INVALID_INPUT", number)
        return None

    def check_exclusions(self):
        for number, entry in self.book.exclusion_rows[self.round]:
            for name in (entry["first"], entry["second"]):
                if name not in self.id_set and name not in self.site_set:
                    return ("UNKNOWN_PROPOSAL", number)
            if entry["first"] == entry["second"]:
                return ("INVALID_INPUT", number)
        return None

    def check(self):
        checkers = {
            "proposals.csv": self.check_proposals,
            "segment_codes.tsv": self.check_segments,
            "permits.csv": self.check_permits,
            "exclusions.json": self.check_exclusions,
        }
        for name in self.book.declared:
            if name not in ROUND_FILES:
                continue
            found = checkers[name]()
            if found is not None:
                self.fault = {"round": self.round, "code": found[0],
                              "file": name, "row": found[1]}
                return False
        return True

    # ---- valuing --------------------------------------------------
    def value(self):
        book = self.book
        worst = None
        for pid in self.ids:
            risk_class, premium = book.sites[self.site[pid]]
            risk = self.override[pid] or risk_class
            rate = book.segment_rate[self.segment[pid]]
            benefit = int(self.households[pid]) * (rate + book.risk_uplift[risk]) + premium
            self.risk_class[pid] = risk
            self.benefit[pid] = benefit
            if benefit < 1 and worst is None:
                worst = self.first_row[pid]
        if worst is not None:
            self.fault = {"round": self.round, "code": "NONPOSITIVE_BENEFIT",
                          "file": "proposals.csv", "row": worst}
            return False
        return True

    # ---- conflicts ------------------------------------------------
    def build_conflicts(self):
        pairs = defaultdict(list)

        by_crew = defaultdict(list)
        for pid in self.ids:
            crew = self.crew[pid]
            if self.book.crews[crew] == "exclusive":
                by_crew[crew].append(pid)
        for members in by_crew.values():
            add_pairs(pairs, members, members, "crew")

        by_permit = defaultdict(list)
        for _, rec in self.book.permit_rows[self.round]:
            if rec["status"] in ("held", "applied"):
                members = by_permit[rec["permit"]]
                if rec["proposal"] not in members:
                    members.append(rec["proposal"])
        for members in by_permit.values():
            add_pairs(pairs, members, members, "permit")

        at_site = defaultdict(list)
        for pid in self.ids:
            at_site[self.site[pid]].append(pid)
        for _, entry in self.book.exclusion_rows[self.round]:
            left = self.expand(entry["first"], at_site)
            right = self.expand(entry["second"], at_site)
            add_pairs(pairs, left, right, "exclusion")

        self.pairs = dict(
            (key, [s for s in ("crew", "permit", "exclusion") if s in sources])
            for key, sources in pairs.items())

    def expand(self, name, at_site):
        if name in self.id_set:
            return [name]
        return at_site.get(name, [])

    # ---- planning -------------------------------------------------
    def plan(self):
        adj = dict((pid, set()) for pid in self.ids)
        for a, b in self.pairs:
            adj[a].add(b)
            adj[b].add(a)
        total, chosen = max_weight_independent_set(self.ids, adj, self.benefit)
        # A shared crew can work on at most four proposals of a portfolio: while
        # some shared crew has more than four picks, rule out its least valuable
        # pick and plan the round again.
        banned = set()
        while True:
            over = defaultdict(list)
            for pid in chosen:
                if self.book.crews[self.crew[pid]] == "shared":
                    over[self.crew[pid]].append(pid)
            extra = [ps for ps in over.values() if len(ps) > SHARED_CAP]
            if not extra:
                break
            for ps in extra:
                banned.add(min(ps, key=lambda p: (self.benefit[p], [-ord(c) for c in p])))
            keep = [p for p in self.ids if p not in banned]
            sub = dict((p, adj[p] - banned) for p in keep)
            total, chosen = max_weight_independent_set(keep, sub, self.benefit)
        self.selected = chosen
        self.total_benefit = total
        self.status = "planned"


def add_pairs(pairs, left, right, source):
    for a in left:
        for b in right:
            if a == b:
                continue
            key = (a, b) if a < b else (b, a)
            bucket = pairs[key]
            if source not in bucket:
                bucket.append(source)


def bits(mask):
    out = []
    while mask:
        low = mask & -mask
        out.append(low.bit_length() - 1)
        mask ^= low
    return out


def max_weight_independent_set(nodes, adj, benefit):
    """Portfolio of greatest total benefit, ties broken by the smaller id list.

    Each proposal gets the weight `benefit * 2**n + 2**(n-1-rank)`, the rank
    counted over ascending ids. Distinct portfolios then have distinct weight
    sums, the greatest sum has the greatest total benefit, and among equal
    totals it carries the lexicographically smallest sorted id list. The low n
    bits of a sum are exactly the membership mask of its portfolio.
    """
    order = sorted(nodes)
    n = len(order)
    if n == 0:
        return 0, []
    index = dict((pid, i) for i, pid in enumerate(order))
    weight = [benefit[pid] << n | 1 << (n - 1 - i) for i, pid in enumerate(order)]
    nbr = [0] * n
    for pid, neighbours in adj.items():
        mask = 0
        for other in neighbours:
            mask |= 1 << index[other]
        nbr[index[pid]] = mask

    def components(verts):
        found = []
        rest = verts
        while rest:
            group = rest & -rest
            frontier = group
            while frontier:
                reach = 0
                for v in bits(frontier):
                    reach |= nbr[v]
                frontier = reach & rest & ~group
                group |= frontier
            found.append(group)
            rest &= ~group
        return found

    def reduce_verts(verts):
        """Take forced proposals and drop dominated ones."""
        value = 0
        cur = verts
        while cur:
            changed = False
            for v in bits(cur):
                if not cur >> v & 1:
                    continue
                around = nbr[v] & cur
                if around == 0:
                    value += weight[v]
                    cur &= ~(1 << v)
                    changed = True
                    continue
                total = 0
                for u in bits(around):
                    total += weight[u]
                if weight[v] >= total:
                    value += weight[v]
                    cur &= ~(around | 1 << v)
                    changed = True
            if changed:
                continue
            for v in bits(cur):
                closed_v = nbr[v] & cur | 1 << v
                for u in bits(nbr[v] & cur):
                    if weight[u] <= weight[v] and \
                            closed_v & ~(nbr[u] & cur | 1 << u) == 0:
                        cur &= ~(1 << u)
                        changed = True
                        break
                if changed:
                    break
            if not changed:
                break
        return value, cur

    def subset_bound(scope, cap):
        """Upper bound on the independent subsets of a scope, via cliques."""
        total = 1
        rest = scope
        while rest:
            low = rest & -rest
            clique = low
            candidates = nbr[low.bit_length() - 1] & rest
            while candidates:
                nxt = candidates & -candidates
                clique |= nxt
                candidates &= nbr[nxt.bit_length() - 1]
            total *= bin(clique).count("1") + 1
            if total > cap:
                return total
            rest &= ~clique
        return total

    def elimination_plan(verts, budget):
        """Steps of a min-degree elimination, or None when its tables are too big."""
        around = dict((v, nbr[v] & verts) for v in bits(verts))
        alive = verts
        steps = []
        estimate = 0
        while alive:
            pivot = min(bits(alive),
                        key=lambda v: bin(around[v] & alive).count("1"))
            scope = around[pivot] & alive
            estimate += subset_bound(scope, budget)
            if estimate > budget:
                return None
            steps.append((pivot, scope))
            for u in bits(scope):
                around[u] |= scope & ~(1 << u)
            alive &= ~(1 << pivot)
        return steps

    def eliminate(steps):
        """Exact total by dynamic programming along an elimination order."""
        pending = []
        total = 0
        for pivot, scope in steps:
            bit = 1 << pivot
            msgs = [m for m in pending if m[0] & bit]
            if msgs:
                pending = [m for m in pending if not m[0] & bit]
                for scope_mask, _ in msgs:
                    scope |= scope_mask
                scope &= ~bit
            subsets = [0]
            for u in bits(scope):
                step = 1 << u
                blocked = nbr[u]
                subsets.extend([s | step for s in subsets if not s & blocked])
            table = {}
            own = nbr[pivot]
            for chosen in subsets:
                best = 0
                for scope_mask, data in msgs:
                    best += data[chosen & scope_mask]
                if not chosen & own:
                    alt = weight[pivot]
                    taken = chosen | bit
                    for scope_mask, data in msgs:
                        alt += data[taken & scope_mask]
                    if alt > best:
                        best = alt
                table[chosen] = best
            if scope:
                pending.append((scope, table))
            else:
                total += table[0]
        return total

    def clique_bound(verts):
        """Cover the vertices by greedy cliques; keep the heaviest of each."""
        total = 0
        rest = verts
        while rest:
            heaviest = max(bits(rest), key=lambda v: weight[v])
            clique = 1 << heaviest
            candidates = nbr[heaviest] & rest
            while candidates:
                nxt = max(bits(candidates), key=lambda v: weight[v])
                clique |= 1 << nxt
                candidates &= nbr[nxt]
            total += weight[heaviest]
            rest &= ~clique
        return total

    def greedy_value(verts):
        """A portfolio built by taking the best weight against degree."""
        total = 0
        cur = verts
        while cur:
            pick = max(bits(cur), key=lambda v: (
                (weight[v] >> n) / (1 + bin(nbr[v] & cur).count("1")), -v))
            total += weight[pick]
            cur &= ~(nbr[pick] | 1 << pick)
        return total

    exact_memo = {}

    def search(group):
        """Branch and bound over one connected group."""
        cached = exact_memo.get(group)
        if cached is not None:
            return cached
        best = [greedy_value(group)]

        def descend(verts, acc):
            value, cur = reduce_verts(verts)
            acc += value
            if cur == 0:
                if acc > best[0]:
                    best[0] = acc
                return
            groups = components(cur)
            if len(groups) > 1:
                for part in groups:
                    acc += exact(part)
                if acc > best[0]:
                    best[0] = acc
                return
            if acc + clique_bound(cur) <= best[0]:
                return
            pivot = max(bits(cur), key=lambda v: bin(nbr[v] & cur).count("1"))
            descend(cur & ~(nbr[pivot] | 1 << pivot), acc + weight[pivot])
            descend(cur & ~(1 << pivot), acc)

        descend(group, 0)
        exact_memo[group] = best[0]
        return best[0]

    def exact(verts):
        cached = exact_memo.get(verts)
        if cached is not None:
            return cached
        value, cur = reduce_verts(verts)
        for group in components(cur):
            value += search(group)
        exact_memo[verts] = value
        return value

    def plan_verts(verts):
        value, cur = reduce_verts(verts)
        for group in components(cur):
            steps = elimination_plan(group, dp_budget())
            value += eliminate(steps) if steps is not None else search(group)
        return value

    best = plan_verts((1 << n) - 1)
    chosen = [order[n - 1 - place] for place in bits(best & (1 << n) - 1)]
    return best >> n, sorted(chosen)


def write_json(out_dir, name, payload):
    with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def build_outputs(book, states, out_dir):
    rounds = book.rounds
    planned = [r for r in rounds if states[r].status == "planned"]
    rejected = [r for r in rounds if states[r].status == "rejected"]

    summary_rounds = []
    selected_total = 0
    benefit_total = 0
    for rnd in rounds:
        st = states[rnd]
        summary_rounds.append({
            "round": rnd,
            "status": st.status,
            "proposals": len(st.rows),
            "selected": list(st.selected),
            "total_benefit": st.total_benefit,
        })
        selected_total += len(st.selected)
        benefit_total += st.total_benefit
    write_json(out_dir, "summary.json", {
        "book": book.book,
        "rounds": summary_rounds,
        "planned_rounds": len(planned),
        "rejected_rounds": len(rejected),
        "selected_proposals": selected_total,
        "total_benefit": benefit_total,
    })

    audit_rows = []
    for line_no, parts in book.queries:
        kind, rnd = parts[0], parts[1]
        st = states[rnd]
        row = {"line": line_no, "kind": kind, "round": rnd, "status": st.status}
        if st.status == "planned":
            chosen = set(st.selected)
            if kind == "VALUE":
                pid = parts[2]
                segment = st.segment[pid]
                row["proposal"] = pid
                row["segment"] = segment
                row["segment_rate"] = book.segment_rate[segment]
                row["risk_class"] = st.risk_class[pid]
                row["risk_uplift"] = book.risk_uplift[st.risk_class[pid]]
                row["households"] = int(st.households[pid])
                row["premium"] = book.sites[st.site[pid]][1]
                row["benefit"] = st.benefit[pid]
                row["selected"] = pid in chosen
            else:
                first, second = parts[2], parts[3]
                key = (first, second) if first < second else (second, first)
                sources = st.pairs.get(key, []) if first != second else []
                row["first"] = first
                row["second"] = second
                row["sources"] = list(sources)
                row["conflict"] = bool(sources)
                row["first_selected"] = first in chosen
                row["second_selected"] = second in chosen
        audit_rows.append(row)
    write_json(out_dir, "policy_audit.json", {"book": book.book, "rows": audit_rows})

    conflict_pairs = 0
    by_source = {"crew": 0, "permit": 0, "exclusion": 0}
    withdrawn = 0
    for rnd in planned:
        st = states[rnd]
        conflict_pairs += len(st.pairs)
        for sources in st.pairs.values():
            for source in sources:
                by_source[source] += 1
        for _, rec in book.permit_rows[rnd]:
            if rec["status"] == "withdrawn":
                withdrawn += 1
    write_json(out_dir, "data_quality.json", {
        "book": book.book,
        "rejected": [states[r].fault for r in rejected],
        "planned_rounds": len(planned),
        "rejected_rounds": len(rejected),
        "conflict_pairs": conflict_pairs,
        "conflicts_by_source": by_source,
        "withdrawn_permit_rows": withdrawn,
    })

    for region in REGIONS:
        write_json(out_dir, "region_%s.json" % region,
                   slice_doc(book, states, planned, "region", region,
                             lambda st, pid: book.regions.get(st.site[pid])))
    for segment in SEGMENT_DOCS:
        write_json(out_dir, "segment_%s.json" % segment,
                   slice_doc(book, states, planned, "segment", segment,
                             lambda st, pid: st.segment.get(pid)))


def slice_doc(book, states, planned, key, value, classify):
    rounds = []
    count = 0
    total = 0
    for rnd in planned:
        st = states[rnd]
        picked = [pid for pid in st.selected if classify(st, pid) == value]
        benefit = sum(st.benefit[pid] for pid in picked)
        rounds.append({"round": rnd, "selected": picked, "benefit": benefit})
        count += len(picked)
        total += benefit
    return {"book": book.book, key: value, "rounds": rounds,
            "selected_proposals": count, "total_benefit": total}


def main(argv):
    sys.setrecursionlimit(20000)
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir, out_dir = argv[1], argv[2]
    book = Book(data_dir)
    states = {}
    for rnd in book.rounds:
        st = RoundState(book, rnd)
        if st.check() and st.value():
            st.build_conflicts()
            st.plan()
        states[rnd] = st
    os.makedirs(out_dir, exist_ok=True)
    build_outputs(book, states, out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

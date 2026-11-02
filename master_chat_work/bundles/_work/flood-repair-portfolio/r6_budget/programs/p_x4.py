#!/usr/bin/env python3
"""Flood repair funding book report deriver.

Usage: python3 derive_report.py DATA_DIR OUT_DIR
"""

import csv
import itertools
import json
import os
import re
import sys
import time
from configparser import ConfigParser

ROUND_FILES = ("proposals.csv", "segment_codes.tsv", "permits.csv", "exclusions.json")
REGIONS = ("North", "South", "West", "East")
SEGMENT_DOCS = ("commercial", "public")
RISK_CLASSES = ("A", "B", "C", "D")
PERMIT_ACTIVE = ("held", "applied")
PERMIT_STATUSES = ("held", "applied", "withdrawn")
SOURCES = ("crew", "permit", "exclusion")
SHARED_LIMIT = 4
BOOK_BUDGET = 52.0
ROUND_BUDGET = 16.0
DIGITS = re.compile(r"[0-9]+")


class Timeout(Exception):
    """Raised when the planning budget of a book is spent."""


_LIMITS = {"book": None, "round": None}


def set_book_budget(seconds):
    _LIMITS["book"] = time.monotonic() + seconds


def start_round_budget(seconds):
    whole = _LIMITS["book"]
    limit = time.monotonic() + seconds
    _LIMITS["round"] = limit if whole is None else min(whole, limit)


def check_deadline():
    limit = _LIMITS["round"]
    if limit is not None and time.monotonic() > limit:
        raise Timeout()


def fail_missing(name):
    sys.stderr.write("ERROR MISSING_FILE %s\n" % name)
    sys.exit(1)


def read_rows(path, delimiter):
    """Data rows of a delimited file as (row_number, fields); header dropped."""
    with open(path, "r", newline="", encoding="utf-8") as handle:
        lines = handle.read().split("\n")
    body = []
    seen_header = False
    for line in lines:
        if line.strip() == "":
            continue
        if not seen_header:
            seen_header = True
            continue
        body.append(line)
    return list(enumerate(csv.reader(body, delimiter=delimiter), start=1))


def field(fields, index):
    return fields[index] if index < len(fields) else ""


class Book:
    def __init__(self, data_dir):
        self.dir = data_dir
        manifest_path = os.path.join(data_dir, "manifest.json")
        if not os.path.isfile(manifest_path):
            fail_missing("manifest.json")
        with open(manifest_path, "r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        self.book = manifest["book"]
        self.declared = list(manifest["files"])
        for name in self.declared:
            if not os.path.isfile(os.path.join(data_dir, name)):
                fail_missing(name)
        self.load()

    def path(self, name):
        return os.path.join(self.dir, name)

    def load(self):
        self.sites = {}
        with open(self.path("sites.jsonl"), "r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip() == "":
                    continue
                obj = json.loads(line)
                self.sites[obj["site"]] = (obj["risk_class"], int(obj["premium"]))

        self.region = {}
        for _, fields in read_rows(self.path("region_codes.csv"), ","):
            self.region[field(fields, 0)] = field(fields, 1)

        self.crews = {}
        for _, fields in read_rows(self.path("crews.tsv"), "\t"):
            self.crews[field(fields, 0)] = field(fields, 1)

        parser = ConfigParser()
        parser.optionxform = str
        parser.read(self.path("benefits.ini"), encoding="utf-8")
        self.segment_rate = {k: int(v) for k, v in parser["segment_rate"].items()}
        self.risk_uplift = {k: int(v) for k, v in parser["risk_uplift"].items()}

        self.proposals = {}
        for number, fields in read_rows(self.path("proposals.csv"), ","):
            rnd = field(fields, 0)
            self.proposals.setdefault(rnd, []).append(
                (
                    number,
                    field(fields, 1),
                    field(fields, 2),
                    field(fields, 3),
                    field(fields, 4),
                    field(fields, 5),
                )
            )

        self.segments = {}
        for number, fields in read_rows(self.path("segment_codes.tsv"), "\t"):
            self.segments.setdefault(field(fields, 0), []).append(
                (number, field(fields, 1), field(fields, 2))
            )

        self.permits = {}
        for number, fields in read_rows(self.path("permits.csv"), ","):
            self.permits.setdefault(field(fields, 0), []).append(
                (number, field(fields, 1), field(fields, 2), field(fields, 3))
            )

        self.exclusions = {}
        with open(self.path("exclusions.json"), "r", encoding="utf-8") as handle:
            entries = json.load(handle)
        for number, entry in enumerate(entries, start=1):
            self.exclusions.setdefault(entry["round"], []).append(
                (number, entry["first"], entry["second"])
            )

        self.queries = []
        with open(self.path("audit_queries.txt"), "r", encoding="utf-8") as handle:
            for number, line in enumerate(handle.read().split("\n"), start=1):
                if line.strip() == "":
                    continue
                self.queries.append((number, line.split()))

        self.rounds = sorted(self.proposals)

    def round_file_order(self):
        return [name for name in self.declared if name in ROUND_FILES]


def valid_households(text):
    return DIGITS.fullmatch(text) is not None and 1 <= int(text) <= 60


def check_round(book, rnd):
    """First fault of a round as (code, file, row), or None."""
    rows = book.proposals[rnd]
    proposal_ids = {row[1] for row in rows}
    round_sites = {row[2] for row in rows}
    for name in book.round_file_order():
        if name == "proposals.csv":
            seen = set()
            for number, proposal, site, crew, households, override in rows:
                if proposal in seen:
                    return ("DUPLICATE_PROPOSAL", name, number)
                seen.add(proposal)
                if (
                    not valid_households(households)
                    or site not in book.sites
                    or crew not in book.crews
                    or (override != "" and override not in RISK_CLASSES)
                ):
                    return ("INVALID_INPUT", name, number)
        elif name == "segment_codes.tsv":
            for number, proposal, segment in book.segments.get(rnd, ()):
                if proposal not in proposal_ids:
                    return ("UNKNOWN_PROPOSAL", name, number)
                if segment not in book.segment_rate:
                    return ("INVALID_INPUT", name, number)
        elif name == "permits.csv":
            for number, _permit, proposal, status in book.permits.get(rnd, ()):
                if proposal not in proposal_ids:
                    return ("UNKNOWN_PROPOSAL", name, number)
                if status not in PERMIT_STATUSES:
                    return ("INVALID_INPUT", name, number)
        else:
            for number, first, second in book.exclusions.get(rnd, ()):
                if any(
                    side not in proposal_ids and side not in round_sites
                    for side in (first, second)
                ):
                    return ("UNKNOWN_PROPOSAL", name, number)
                if first == second:
                    return ("INVALID_INPUT", name, number)
    return None


def value_round(book, rnd):
    """Valuation of every proposal of a checked round, in proposal row order."""
    segment_of = {}
    for _number, proposal, segment in book.segments.get(rnd, ()):
        segment_of[proposal] = segment
    valued = []
    for number, proposal, site, crew, households, override in book.proposals[rnd]:
        risk_class, premium = book.sites[site]
        if override != "":
            risk_class = override
        segment = segment_of[proposal]
        rate = book.segment_rate[segment]
        uplift = book.risk_uplift[risk_class]
        count = int(households)
        valued.append(
            {
                "row": number,
                "proposal": proposal,
                "site": site,
                "crew": crew,
                "households": count,
                "segment": segment,
                "segment_rate": rate,
                "risk_class": risk_class,
                "risk_uplift": uplift,
                "premium": premium,
                "benefit": count * (rate + uplift) + premium,
            }
        )
    return valued


def conflict_sources(book, rnd, valued):
    """Conflicting pairs of a round mapped to their sources, and crew groups."""
    id_set = {item["proposal"] for item in valued}
    pairs = {}

    def join(a, b, source):
        if a == b:
            return
        key = (a, b) if a < b else (b, a)
        bucket = pairs.setdefault(key, set())
        bucket.add(source)

    def clique(members, source):
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                join(members[i], members[j], source)

    by_crew = {}
    for item in valued:
        by_crew.setdefault(item["crew"], []).append(item["proposal"])
    for crew, members in by_crew.items():
        if book.crews.get(crew) == "exclusive":
            clique(members, "crew")

    by_permit = {}
    for _number, permit, proposal, status in book.permits.get(rnd, ()):
        if status in PERMIT_ACTIVE and proposal in id_set:
            members = by_permit.setdefault(permit, [])
            if proposal not in members:
                members.append(proposal)
    for members in by_permit.values():
        clique(members, "permit")

    by_site = {}
    for item in valued:
        by_site.setdefault(item["site"], []).append(item["proposal"])
    for _number, first, second in book.exclusions.get(rnd, ()):
        left = [first] if first in id_set else by_site.get(first, [])
        right = [second] if second in id_set else by_site.get(second, [])
        for a in left:
            for b in right:
                join(a, b, "exclusion")

    ordered = {
        key: [s for s in SOURCES if s in bucket] for key, bucket in pairs.items()
    }
    return ordered, by_crew


class Planner:
    """Exact portfolio chooser of one planned round.

    Proposal `i` of the ascending id list is bit `count - 1 - i` of a mask, so
    of two portfolios of equal benefit the one with the greater mask is the one
    with the smaller sorted id list.
    """

    STATE_CAP = 1000000
    LEAF_CAP = 120000
    COMBO_CAP = 256

    def __init__(self, ids, benefit_of, pair_keys, shared_groups):
        self.ids = ids
        self.count = len(ids)
        self.bits = [1 << (self.count - 1 - i) for i in range(self.count)]
        self.bit_index = {self.bits[i]: i for i in range(self.count)}
        index = {name: i for i, name in enumerate(ids)}
        self.weights = [benefit_of[name] for name in ids]

        self.adjacency = [0] * self.count
        for first, second in pair_keys:
            i, j = index[first], index[second]
            self.adjacency[i] |= self.bits[j]
            self.adjacency[j] |= self.bits[i]

        self.group_members = [sorted(index[name] for name in members)
                              for members in shared_groups]
        self.group_masks = []
        self.groups_of = [[] for _ in range(self.count)]
        for group, members in enumerate(self.group_members):
            mask = 0
            for i in members:
                mask |= self.bits[i]
                self.groups_of[i].append(group)
            self.group_masks.append(mask)

        self.group_total = 0
        for mask in self.group_masks:
            self.group_total |= mask

        self.coupling = list(self.adjacency)
        for mask in self.group_masks:
            rest = mask
            while rest:
                low = rest & -rest
                rest ^= low
                self.coupling[self.bit_index[low]] |= mask & ~low

        self.memo = {}
        self.dp_limit = self.count

    def choose(self):
        full = (1 << self.count) - 1
        caps = tuple(SHARED_LIMIT for _ in self.group_masks)
        try:
            if self.group_masks:
                result = self.capped_dp(full)
            else:
                result = self.dp(full)
            if result is None:
                result = self.branch_and_bound(full)
        except Timeout:
            result = self.greedy(full, caps)
        benefit, chosen = result
        selected = [self.ids[i] for i in range(self.count) if chosen & self.bits[i]]
        return selected, benefit

    def capped_dp(self, allowed):
        """Optimum under the shared crew limits, by forcing surplus members out."""
        choices = []
        for members in self.group_members:
            drop = len(members) - SHARED_LIMIT
            masks = []
            for combo in itertools.combinations(members, drop):
                mask = 0
                for i in combo:
                    mask |= self.bits[i]
                masks.append(mask)
            choices.append(masks)
        product = 1
        for masks in choices:
            product *= len(masks)
        if product > self.COMBO_CAP:
            return None
        best = None
        for combo in itertools.product(*choices):
            forced = 0
            for mask in combo:
                forced |= mask
            result = self.dp(allowed & ~forced)
            if result is None:
                return None
            if best is None or result > best:
                best = result
        return best

    def elimination(self, allowed, by_fill):
        """Elimination order of `allowed` and the bag of later neighbours of each."""
        bits = self.bits
        bit_index = self.bit_index
        work = list(self.adjacency)
        remaining = allowed
        order = []
        bags = [0] * self.count
        while remaining:
            pick = -1
            least = None
            rest = remaining
            while rest:
                low = rest & -rest
                rest ^= low
                i = bit_index[low]
                around = work[i] & remaining & ~low
                degree = around.bit_count()
                if by_fill:
                    missing = 0
                    inner = around
                    while inner:
                        other = inner & -inner
                        inner ^= other
                        j = bit_index[other]
                        missing += (around & ~work[j] & ~other).bit_count()
                    cost = (missing, degree)
                else:
                    cost = (degree,)
                if least is None or cost < least:
                    least = cost
                    pick = i
            neighbours = work[pick] & remaining & ~bits[pick]
            bags[pick] = neighbours
            order.append(pick)
            rest = neighbours
            while rest:
                low = rest & -rest
                rest ^= low
                work[bit_index[low]] |= neighbours & ~low
            remaining &= ~bits[pick]
        return order, bags

    def dp(self, allowed):
        """Optimum of the conflict graph on `allowed`, by elimination order DP."""
        for by_fill in (False, True):
            order, bags = self.elimination(allowed, by_fill)
            result = self.dp_pass(order, bags, self.STATE_CAP)
            if result is not None:
                return result
        return None

    def dp_pass(self, order, bags, cap):
        """One run of the DP; None when the state count passes `cap`."""
        bits = self.bits
        bit_index = self.bit_index
        adjacency = self.adjacency
        weights = self.weights

        position = {v: k for k, v in enumerate(order)}
        children = [[] for _ in range(self.count)]
        parent = {}
        for v in order:
            if bags[v]:
                head = -1
                rest = bags[v]
                while rest:
                    low = rest & -rest
                    rest ^= low
                    u = bit_index[low]
                    if head < 0 or position[u] < position[head]:
                        head = u
                parent[v] = head
                children[head].append(v)

        tables = [None] * self.count
        states = 0
        for v in order:
            check_deadline()
            members = []
            rest = bags[v]
            while rest:
                low = rest & -rest
                rest ^= low
                members.append(bit_index[low])
            subsets = [0]
            for i in members:
                bit = bits[i]
                blocked = adjacency[i]
                subsets.extend([s | bit for s in subsets if not s & blocked])
                if len(subsets) > cap:
                    return None
            states += len(subsets)
            if states > cap:
                return None
            kids = [(bags[c], tables[c]) for c in children[v]]
            own_bit = bits[v]
            own_adjacency = adjacency[v]
            own_weight = weights[v]
            table = {}
            for state in subsets:
                benefit = 0
                mask = 0
                for bag, kid in kids:
                    sub = kid[state & bag]
                    benefit += sub[0]
                    mask |= sub[1]
                best = (benefit, mask)
                if not state & own_adjacency:
                    benefit = own_weight
                    mask = own_bit
                    taken = state | own_bit
                    for bag, kid in kids:
                        sub = kid[taken & bag]
                        benefit += sub[0]
                        mask |= sub[1]
                    if (benefit, mask) > best:
                        best = (benefit, mask)
                table[state] = best
            tables[v] = table
            for c in children[v]:
                tables[c] = None

        total = 0
        chosen = 0
        for v in order:
            if v not in parent:
                benefit, mask = tables[v][0]
                total += benefit
                chosen |= mask
        return (total, chosen)

    def components(self, mask):
        parts = []
        rest = mask
        while rest:
            seed = rest & -rest
            component = seed
            frontier = seed
            while frontier:
                low = frontier & -frontier
                frontier ^= low
                found = self.coupling[self.bit_index[low]] & rest & ~component
                component |= found
                frontier |= found
            parts.append(component)
            rest &= ~component
        return parts

    def weight_sum(self, mask):
        total = 0
        rest = mask
        while rest:
            low = rest & -rest
            rest ^= low
            total += self.weights[self.bit_index[low]]
        return total

    def take(self, mask, caps, pick):
        """Mask and shared crew capacities left after choosing `pick`."""
        allowed = mask & ~self.adjacency[pick] & ~self.bits[pick]
        if not self.groups_of[pick]:
            return allowed, caps
        left = list(caps)
        for group in self.groups_of[pick]:
            left[group] -= 1
            if left[group] == 0:
                allowed &= ~self.group_masks[group]
        return allowed, tuple(left)

    def clique_bound(self, mask):
        """Upper bound on the benefit of a portfolio inside `mask`."""
        adjacency = self.adjacency
        weights = self.weights
        bit_index = self.bit_index
        total = 0
        rest = mask
        while rest:
            low = rest & -rest
            rest ^= low
            i = bit_index[low]
            best = weights[i]
            clique = low
            candidates = adjacency[i] & rest
            while candidates:
                other = candidates & -candidates
                candidates ^= other
                j = bit_index[other]
                clique |= other
                if weights[j] > best:
                    best = weights[j]
                candidates &= adjacency[j]
            rest &= ~clique
            total += best
        return total

    def greedy(self, mask, caps):
        """A feasible portfolio of `mask`, heaviest proposals first."""
        order = sorted(range(self.count), key=lambda i: -self.weights[i])
        total = 0
        chosen = 0
        allowed = mask
        for i in order:
            if allowed & self.bits[i]:
                total += self.weights[i]
                chosen |= self.bits[i]
                allowed, caps = self.take(allowed, caps, i)
        return (total, chosen)

    def best_portfolio(self, mask, caps):
        """Optimum of `mask` under `caps`, over its connected components."""
        if mask == 0:
            return (0, 0)
        key = (mask, tuple(cap if self.group_masks[g] & mask else SHARED_LIMIT
                           for g, cap in enumerate(caps)))
        cached = self.memo.get(key)
        if cached is not None:
            return cached
        parts = self.components(mask)
        if len(parts) > 1:
            benefit = 0
            chosen = 0
            for part in parts:
                part_benefit, part_chosen = self.best_portfolio(part, caps)
                benefit += part_benefit
                chosen |= part_chosen
            value = (benefit, chosen)
        else:
            value = self.search(mask, caps)
        self.memo[key] = value
        return value

    def search(self, mask, caps):
        """Optimum of one connected component, by search with DP leaves."""
        best = [self.greedy(mask, caps)]
        bits = self.bits
        bit_index = self.bit_index
        adjacency = self.adjacency
        weights = self.weights

        def dfs(allowed, acc, picked, caps):
            check_deadline()
            while True:
                rest = allowed
                found = -1
                while rest:
                    low = rest & -rest
                    rest ^= low
                    i = bit_index[low]
                    if self.groups_of[i]:
                        continue
                    neighbours = adjacency[i] & allowed
                    if weights[i] > self.weight_sum(neighbours):
                        found = i
                        break
                if found < 0:
                    break
                acc += weights[found]
                picked |= bits[found]
                allowed &= ~(adjacency[found] | bits[found])
            if allowed == 0:
                if (acc, picked) > best[0]:
                    best[0] = (acc, picked)
                return
            if (acc + self.clique_bound(allowed), picked | allowed) <= best[0]:
                return
            parts = self.components(allowed)
            if len(parts) > 1:
                benefit = acc
                chosen = picked
                for part in parts:
                    part_benefit, part_chosen = self.best_portfolio(part, caps)
                    benefit += part_benefit
                    chosen |= part_chosen
                if (benefit, chosen) > best[0]:
                    best[0] = (benefit, chosen)
                return
            size = allowed.bit_count()
            if size <= self.dp_limit and not self.group_total & allowed:
                order, bags = self.elimination(allowed, False)
                result = self.dp_pass(order, bags, self.LEAF_CAP)
                if result is None:
                    self.dp_limit = size - 1
                else:
                    candidate = (acc + result[0], picked | result[1])
                    if candidate > best[0]:
                        best[0] = candidate
                    return
            pick = -1
            degree = -1
            rest = allowed
            while rest:
                low = rest & -rest
                rest ^= low
                i = bit_index[low]
                own = (self.coupling[i] & allowed).bit_count()
                if own > degree:
                    degree = own
                    pick = i
            inner, inner_caps = self.take(allowed, caps, pick)
            dfs(inner, acc + weights[pick], picked | bits[pick], inner_caps)
            dfs(allowed & ~bits[pick], acc, picked, caps)

        try:
            dfs(mask, 0, 0, caps)
        except Timeout:
            pass
        return best[0]

    def branch_and_bound(self, allowed):
        """Optimum by search, used when the elimination DP is out of reach."""
        caps = tuple(SHARED_LIMIT for _ in self.group_masks)
        return self.best_portfolio(allowed, caps)


def plan_round(book, valued, pairs, by_crew):
    """Chosen portfolio of a planned round, and its total benefit."""
    start_round_budget(ROUND_BUDGET)
    ids = sorted(item["proposal"] for item in valued)
    benefit_of = {item["proposal"]: item["benefit"] for item in valued}
    shared_groups = [
        members
        for crew, members in by_crew.items()
        if book.crews.get(crew) == "shared" and len(members) > SHARED_LIMIT
    ]
    return Planner(ids, benefit_of, pairs.keys(), shared_groups).choose()


def derive(book):
    rounds = {}
    for rnd in book.rounds:
        fault = check_round(book, rnd)
        record = {
            "round": rnd,
            "proposals": len(book.proposals[rnd]),
            "valued": None,
            "pairs": {},
            "selected": [],
            "total_benefit": 0,
            "fault": fault,
        }
        if fault is None:
            valued = value_round(book, rnd)
            record["valued"] = valued
            low = next((item for item in valued if item["benefit"] < 1), None)
            if low is not None:
                record["fault"] = ("NONPOSITIVE_BENEFIT", "proposals.csv", low["row"])
            else:
                pairs, by_crew = conflict_sources(book, rnd, valued)
                record["pairs"] = pairs
                selected, total = plan_round(book, valued, pairs, by_crew)
                record["selected"] = selected
                record["total_benefit"] = total
        record["status"] = "rejected" if record["fault"] else "planned"
        rounds[rnd] = record
    return rounds


def write_json(out_dir, name, payload):
    with open(os.path.join(out_dir, name), "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def write_summary(book, rounds, out_dir):
    entries = []
    planned = 0
    rejected = 0
    selected_total = 0
    benefit_total = 0
    for rnd in book.rounds:
        record = rounds[rnd]
        entries.append(
            {
                "round": rnd,
                "status": record["status"],
                "proposals": record["proposals"],
                "selected": record["selected"],
                "total_benefit": record["total_benefit"],
            }
        )
        if record["status"] == "planned":
            planned += 1
        else:
            rejected += 1
        selected_total += len(record["selected"])
        benefit_total += record["total_benefit"]
    write_json(
        out_dir,
        "summary.json",
        {
            "book": book.book,
            "rounds": entries,
            "planned_rounds": planned,
            "rejected_rounds": rejected,
            "selected_proposals": selected_total,
            "total_benefit": benefit_total,
        },
    )


def write_policy_audit(book, rounds, out_dir):
    rows = []
    for line, parts in book.queries:
        kind, rnd = parts[0], parts[1]
        record = rounds[rnd]
        row = {"line": line, "kind": kind, "round": rnd, "status": record["status"]}
        if record["status"] == "planned":
            chosen = set(record["selected"])
            if kind == "VALUE":
                name = parts[2]
                item = next(i for i in record["valued"] if i["proposal"] == name)
                row["proposal"] = name
                row["segment"] = item["segment"]
                row["segment_rate"] = item["segment_rate"]
                row["risk_class"] = item["risk_class"]
                row["risk_uplift"] = item["risk_uplift"]
                row["households"] = item["households"]
                row["premium"] = item["premium"]
                row["benefit"] = item["benefit"]
                row["selected"] = name in chosen
            else:
                first, second = parts[2], parts[3]
                key = (first, second) if first < second else (second, first)
                sources = [] if first == second else record["pairs"].get(key, [])
                row["first"] = first
                row["second"] = second
                row["sources"] = list(sources)
                row["conflict"] = len(sources) > 0
                row["first_selected"] = first in chosen
                row["second_selected"] = second in chosen
        rows.append(row)
    write_json(out_dir, "policy_audit.json", {"book": book.book, "rows": rows})


def write_data_quality(book, rounds, out_dir):
    rejected = []
    planned = 0
    pair_count = 0
    by_source = {"crew": 0, "permit": 0, "exclusion": 0}
    withdrawn = 0
    for rnd in book.rounds:
        record = rounds[rnd]
        if record["status"] == "rejected":
            code, name, number = record["fault"]
            rejected.append({"round": rnd, "code": code, "file": name, "row": number})
            continue
        planned += 1
        pair_count += len(record["pairs"])
        for sources in record["pairs"].values():
            for source in sources:
                by_source[source] += 1
        for _number, _permit, _proposal, status in book.permits.get(rnd, ()):
            if status == "withdrawn":
                withdrawn += 1
    write_json(
        out_dir,
        "data_quality.json",
        {
            "book": book.book,
            "rejected": rejected,
            "planned_rounds": planned,
            "rejected_rounds": len(rejected),
            "conflict_pairs": pair_count,
            "conflicts_by_source": by_source,
            "withdrawn_permit_rows": withdrawn,
        },
    )


def write_slice(book, rounds, out_dir, name, key, value, keep):
    entries = []
    selected_total = 0
    benefit_total = 0
    for rnd in book.rounds:
        record = rounds[rnd]
        if record["status"] != "planned":
            continue
        chosen = set(record["selected"])
        picked = []
        benefit = 0
        for item in record["valued"]:
            if item["proposal"] in chosen and keep(item):
                picked.append(item["proposal"])
                benefit += item["benefit"]
        picked.sort()
        entries.append({"round": rnd, "selected": picked, "benefit": benefit})
        selected_total += len(picked)
        benefit_total += benefit
    write_json(
        out_dir,
        name,
        {
            "book": book.book,
            key: value,
            "rounds": entries,
            "selected_proposals": selected_total,
            "total_benefit": benefit_total,
        },
    )


def write_slices(book, rounds, out_dir):
    for region in REGIONS:
        write_slice(
            book,
            rounds,
            out_dir,
            "region_%s.json" % region,
            "region",
            region,
            lambda item, region=region: book.region.get(item["site"]) == region,
        )
    for segment in SEGMENT_DOCS:
        write_slice(
            book,
            rounds,
            out_dir,
            "segment_%s.json" % segment,
            "segment",
            segment,
            lambda item, segment=segment: item["segment"] == segment,
        )


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir, out_dir = argv[1], argv[2]
    sys.setrecursionlimit(10000)
    set_book_budget(BOOK_BUDGET)
    book = Book(data_dir)
    rounds = derive(book)
    os.makedirs(out_dir, exist_ok=True)
    write_summary(book, rounds, out_dir)
    write_policy_audit(book, rounds, out_dir)
    write_data_quality(book, rounds, out_dir)
    write_slices(book, rounds, out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

#!/usr/bin/env python3
"""Author reference; installed as the bundle's derive_report.py."""
from __future__ import annotations
import csv
import json
import math
import shutil
import tempfile
import sys
from collections import defaultdict
from pathlib import Path


def table(root, name):
    with (root / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def document(root, name):
    return json.loads((root / name).read_text(encoding="utf-8"))


def calibrated(root):
    sources = table(root, "sources.csv")
    epochs = table(root, "epochs.csv")
    terms = defaultdict(list)
    transforms = {}
    for row in table(root, "clock_terms.csv"):
        terms[(row["epoch"], row["equation"])].append(row)
        key = (row["epoch"], row["source"])
        transform = (int(row["power"]), int(row["shift"]) % 41)
        if transform[0] <= 0 or math.gcd(transform[0], 40) != 1:
            raise ValueError("invalid clock transform")
        if key in transforms and transforms[key] != transform:
            raise ValueError("inconsistent clock transform")
        transforms[key] = transform
    residues = table(root, "clock_residues.csv")
    by_epoch = defaultdict(list)
    names = sorted(r["source"] for r in sources)
    index = {s: i for i, s in enumerate(names)}
    for row in residues:
        line = [0] * len(names)
        for term in terms[(row["epoch"], row["equation"])]:
            line[index[term["source"]]] += int(term["coefficient"])
        by_epoch[row["epoch"]].append([v % 41 for v in line] + [int(row["residue"])])
    answers = {}
    for epoch in epochs:
        matrix = by_epoch[epoch["epoch"]]
        pivot = 0
        positions = []
        for col in range(len(names)):
            found = next((i for i in range(pivot, len(matrix)) if matrix[i][col] % 41), None)
            if found is None:
                continue
            matrix[pivot], matrix[found] = matrix[found], matrix[pivot]
            inverse = pow(matrix[pivot][col], -1, 41)
            matrix[pivot] = [(v * inverse) % 41 for v in matrix[pivot]]
            for i in range(len(matrix)):
                if i != pivot:
                    factor = matrix[i][col]
                    matrix[i] = [(a - factor * b) % 41 for a, b in zip(matrix[i], matrix[pivot])]
            positions.append(col)
            pivot += 1
        if any(not any(r[:-1]) and r[-1] for r in matrix):
            raise ValueError("inconsistent clock evidence")
        # With at most eleven coordinates, excluding residues 39 and 40
        # removes at most 22/41 of a positive-dimensional affine space.
        # Such a space has either zero admissible vectors (a fixed coordinate
        # is forbidden) or at least nineteen; it cannot have exactly one.
        if len(positions) < len(names):
            raise ValueError("clock assignment is empty or ambiguous")
        transformed = [0] * len(names)
        for row_number, column in enumerate(positions):
            transformed[column] = matrix[row_number][-1]
        vector = []
        for source, value in zip(names, transformed):
            key = (epoch["epoch"], source)
            if key not in transforms:
                raise ValueError("missing clock transform")
            power, shift = transforms[key]
            matches = [offset for offset in range(39) if pow((offset + shift) % 41, power, 41) == value]
            if len(matches) != 1:
                raise ValueError("clock assignment is outside the admissible range")
            vector.append(matches[0])
        answers[epoch["epoch"]] = dict(zip(names, vector))
    return answers, sorted(epochs, key=lambda e: int(e["start"]))


def allocations(root):
    groups = table(root, "allocation_groups.csv")
    candidates = table(root, "allocation_candidates.csv")
    candidate_scopes = defaultdict(list)
    candidate_groups = defaultdict(list)
    for candidate in candidates:
        candidate_scopes[(candidate["board"], candidate["component"])].append(candidate)
        candidate_groups[(candidate["board"], candidate["component"], candidate["group"])].append(candidate)
    components = defaultdict(list)
    for group in groups:
        components[(group["board"], group["component"])].append(group)
    chosen = {}
    solved_shapes = {}
    for (board, component), members in sorted(components.items()):
        members = sorted(members, key=lambda row: row["group"])
        wanted_groups = {g["group"] for g in members}
        atoms = {a for g in members for a in atom_set(g["atoms"])}
        rows_by_group = {}
        for group in members:
            rows_by_group[group["group"]] = sorted(candidate_groups[(board, component, group["group"])], key=lambda row: row["candidate"])
        ordered_rows = [row for group in members for row in rows_by_group[group["group"]]]
        incidence = defaultdict(int)
        for row_number, row in enumerate(ordered_rows):
            for atom in atom_set(row["atoms"]) & atoms:
                incidence[atom] |= 1 << row_number
        shape = (
            tuple(tuple(sorted(incidence[atom] for atom in atom_set(group["atoms"]))) for group in members),
            tuple(tuple((row["candidate"], tuple(sorted(incidence[atom] for atom in atom_set(row["atoms"]) if atom in atoms)), len(atom_set(row["atoms"]) - atoms)) for row in rows_by_group[group["group"]]) for group in members),
        )
        if shape in solved_shapes:
            selected_names = solved_shapes[shape]
            for group, candidate_name in zip(members, selected_names):
                matches = [row for row in rows_by_group[group["group"]] if row["candidate"] == candidate_name]
                if len(matches) != 1:
                    raise ValueError("allocation shape mismatch")
                chosen[(board, group["group"])] = int(matches[0]["value"])
            continue
        columns = sorted({("g", g) for g in wanted_groups} | {("a", a) for a in atoms})
        column_index = {column: i for i, column in enumerate(columns)}
        options = []
        for row in candidate_scopes[(board, component)]:
            cover = {("g", row["group"])} | {("a", a) for a in atom_set(row["atoms"])}
            if cover <= column_index.keys():
                mask = sum(1 << column_index[column] for column in cover)
                options.append((row, mask))
        lookup = [0] * len(columns)
        for i, (_, cover) in enumerate(options):
            remaining = cover
            while remaining:
                bit = remaining & -remaining
                lookup[bit.bit_length() - 1] |= 1 << i
                remaining -= bit
        results = []
        def search(uncovered, active, selected):
            if len(results) > 1:
                return
            if not uncovered:
                results.append(selected.copy())
                return
            remaining = uncovered
            col = -1
            count = len(options) + 1
            while remaining:
                bit = remaining & -remaining
                candidate = bit.bit_length() - 1
                size = (lookup[candidate] & active).bit_count()
                if size < count:
                    col, count = candidate, size
                remaining -= bit
            available = lookup[col] & active
            while available:
                option_bit = available & -available
                option = option_bit.bit_length() - 1
                occupied = options[option][1]
                conflicts = 0
                covered = occupied
                while covered:
                    bit = covered & -covered
                    conflicts |= lookup[bit.bit_length() - 1]
                    covered -= bit
                search(uncovered & ~occupied, active & ~conflicts, selected + [option])
                if len(results) > 1:
                    return
                available -= option_bit
        search((1 << len(columns)) - 1, (1 << len(options)) - 1, [])
        if len(results) != 1:
            raise ValueError("allocation is empty or ambiguous")
        selected = {options[option][0]["group"]: options[option][0]["candidate"] for option in results[0]}
        solved_shapes[shape] = tuple(selected[group["group"]] for group in members)
        for option in results[0]:
            row = options[option][0]
            chosen[(board, row["group"])] = int(row["value"])
    return chosen


def atom_set(text):
    atoms = text.split("|") if text else []
    if len(atoms) != len(set(atoms)):
        raise ValueError("repeated atom")
    return set(atoms)


def orbit(state, steps, transition):
    history = []
    seen = {}
    while steps and state not in seen:
        seen[state] = len(history)
        history.append(state)
        state = transition(state)
        steps -= 1
    if steps:
        length = len(history) - seen[state]
        return history[seen[state] + steps % length]
    return state


def fibonacci_pair(index, modulus):
    """Return F(index), F(index+1), reduced modulo modulus."""
    if index == 0:
        return 0, 1
    a, b = fibonacci_pair(index // 2, modulus)
    c = a * ((2 * b - a) % modulus) % modulus
    d = (a * a + b * b) % modulus
    return (d, (c + d) % modulus) if index & 1 else (c, d)


def settle_stream(x, y, modulus, a, b, c, rounds):
    if modulus == 1000000007:
        if (a, b, c) != (1, 1, 0):
            raise ValueError("invalid large stream")
        if rounds == 0:
            return x, y
        period = modulus - 1
        fn, fn1 = fibonacci_pair(rounds, period)
        fnm1 = (fn1 - fn) % period
        u, v = (x + 1) % modulus, (y + 1) % modulus
        def powered(base, reduced_exponent, positive):
            return 0 if base == 0 and positive else pow(base, reduced_exponent, modulus)
        # The only true zero Fibonacci exponent used here is F(0), when n=1.
        left_u = powered(u, fnm1, rounds > 1)
        new_u = left_u * powered(v, fn, True) % modulus
        new_v = powered(u, fn, True) * powered(v, fn1, True) % modulus
        return (new_u - 1) % modulus, (new_v - 1) % modulus
    if modulus > 127:
        raise ValueError("invalid small stream")
    def step(pair):
        old_x, old_y = pair
        return old_y, (a * old_x + b * old_y + c + old_x * old_y) % modulus
    return orbit((x, y), rounds, step)


def compose(first, second, modulus):
    return second[0] * first[0] % modulus, (second[0] * first[1] + second[1]) % modulus


class ForestNode:
    __slots__ = ("record", "a", "b", "left", "right", "parent", "reverse", "forward", "backward")
    def __init__(self, record, a, b, modulus):
        self.record, self.a, self.b = record, a % modulus, b % modulus
        self.left = self.right = self.parent = None
        self.reverse = False
        self.forward = self.backward = (self.a, self.b)


def replay(root):
    spec = document(root, "replay.json")
    modulus = spec["modulus"]
    rows = sorted(table(root, "fold_records.csv"), key=lambda r: int(r["position"]))
    def pair(node, backward=False):
        return (node.backward if backward else node.forward) if node else (1, 0)
    def pull(node):
        node.forward = compose(compose(pair(node.left), (node.a, node.b), modulus), pair(node.right), modulus)
        node.backward = compose(compose(pair(node.right, True), (node.a, node.b), modulus), pair(node.left, True), modulus)
    def flip(node):
        if node:
            node.left, node.right = node.right, node.left
            node.forward, node.backward = node.backward, node.forward
            node.reverse = not node.reverse
    def push(node):
        if node and node.reverse:
            flip(node.left)
            flip(node.right)
            node.reverse = False
    def auxiliary_root(node):
        return node.parent is None or (node.parent.left is not node and node.parent.right is not node)
    def rotate(node):
        parent = node.parent
        grand = parent.parent
        if not auxiliary_root(parent):
            if grand.left is parent:
                grand.left = node
            else:
                grand.right = node
        if parent.left is node:
            parent.left = node.right
            if node.right:
                node.right.parent = parent
            node.right = parent
        else:
            parent.right = node.left
            if node.left:
                node.left.parent = parent
            node.left = parent
        parent.parent = node
        node.parent = grand
        pull(parent)
        pull(node)
    def splay(node):
        path = [node]
        cursor = node
        while not auxiliary_root(cursor):
            cursor = cursor.parent
            path.append(cursor)
        for cursor in reversed(path):
            push(cursor)
        while not auxiliary_root(node):
            parent = node.parent
            grand = parent.parent
            if not auxiliary_root(parent):
                if (parent.left is node) == (grand.left is parent):
                    rotate(parent)
                else:
                    rotate(node)
            rotate(node)
    def access(node):
        last = None
        cursor = node
        while cursor:
            splay(cursor)
            cursor.right = last
            if last:
                last.parent = cursor
            pull(cursor)
            last = cursor
            cursor = cursor.parent
        splay(node)
    def make_root(node):
        access(node)
        flip(node)
    def find_root(node):
        access(node)
        while True:
            push(node)
            if node.left is None:
                break
            node = node.left
        splay(node)
        return node
    def connected(first, second):
        return first is second or find_root(first) is find_root(second)
    def link(first, second):
        make_root(first)
        if find_root(second) is first:
            return False
        first.parent = second
        return True
    def cut(first, second):
        make_root(first)
        access(second)
        if second.left is not first or first.right is not None:
            return False
        second.left.parent = None
        second.left = None
        pull(second)
        return True
    def update(node, a, b):
        access(node)
        node.a, node.b = a % modulus, b % modulus
        pull(node)
    def path_value(first, second):
        if not connected(first, second):
            return spec["initial"] % modulus
        make_root(first)
        access(second)
        return (second.forward[0] * spec["initial"] + second.forward[1]) % modulus
    nodes = {}
    for row in rows:
        node = ForestNode(row["record"], int(row["a"]), int(row["b"]), modulus)
        nodes[node.record] = node
    for before, after in zip(rows, rows[1:]):
        if not link(nodes[before["record"]], nodes[after["record"]]):
            raise ValueError("invalid initial forest")
    versions = {}
    total = 0
    revised = 0
    last = path_value(nodes[rows[0]["record"]], nodes[rows[-1]["record"]]) if rows else spec["initial"] % modulus
    accepted = []
    corrections = sorted(table(root, "fold_corrections.csv"), key=lambda r: (int(r["arrival"]), int(r["amendment"])))
    for c in corrections:
        record = c["record"]
        if record not in nodes:
            accepted.append({"amendment": int(c["amendment"]), "status": "orphan", "state": last})
        elif int(c["revision"]) <= versions.get(record, -1):
            accepted.append({"amendment": int(c["amendment"]), "status": "superseded", "state": last})
        else:
            versions[record] = int(c["revision"])
            node = nodes[record]
            update(node, int(c["a"]), int(c["b"]))
            action = c["action"]
            if action == "keep":
                if any(c[name] for name in ("cut_left", "cut_right", "link_left", "link_right")):
                    raise ValueError("keep action has edge operands")
            elif action == "swap_edge":
                endpoints = [nodes.get(c[name]) for name in ("cut_left", "cut_right", "link_left", "link_right")]
                if all(endpoints):
                    cut_left, cut_right, link_left, link_right = endpoints
                    if cut(cut_left, cut_right):
                        if not link(link_left, link_right):
                            if not link(cut_left, cut_right):
                                raise ValueError("cannot restore forest edge")
            else:
                raise ValueError("unknown forest action")
            query_start, query_end = nodes.get(c["query_start"]), nodes.get(c["query_end"])
            last = path_value(query_start, query_end) if query_start and query_end else spec["initial"] % modulus
            revised += 1
            accepted.append({"amendment": int(c["amendment"]), "status": "applied", "state": last})
        total += int(c["amendment"]) * last
    return {"state": last, "weighted_states": total, "revised": revised}, accepted


def build(root):
    policy = document(root, "policy.json")
    settings, epochs = calibrated(root)
    aliases = table(root, "aliases.csv")
    source_units = {r["source"]: int(r["unit_numerator"]) for r in table(root, "sources.csv")}
    normalized = []
    for row in table(root, "events.csv"):
        epoch = next((e for e in epochs if int(e["start"]) <= int(row["captured"]) < int(e["end"])), None)
        if epoch is None:
            raise ValueError("event outside epochs")
        event_time = int(row["stamp"]) - settings[epoch["epoch"]][row["source"]]
        identities = [a for a in aliases if a["alias"] == row["alias"] and int(a["start"]) <= event_time < int(a["end"])]
        if len(identities) != 1:
            raise ValueError("identity is empty or ambiguous")
        units = int(row["quantity"]) * source_units[row["source"]]
        normalized.append({"event": int(row["event"]), "instant": event_time, "identity": identities[0]["identity"], "units": units})
    normalized.sort(key=lambda r: (r["instant"], r["event"]))
    state = 0
    for row in normalized:
        state = (state * policy["clock_multiplier"] + row["units"] + row["instant"] * row["event"]) % policy["clock_modulus"]
        row["state"] = state
    north = {"name": "North", "in_scope": bool(normalized), "events": normalized, "final_state": state, "units": sum(r["units"] for r in normalized)}
    recovered = {s: settings[epochs[-1]["epoch"]][s] for s in sorted(source_units)}
    audit = {"final_offsets": recovered, "identity_totals": {i: sum(r["units"] for r in normalized if r["identity"] == i) for i in sorted({r["identity"] for r in normalized})}, "weighted_state": sum(r["event"] * r["state"] for r in normalized)}
    assignment = allocations(root)
    requests = table(root, "allocation_requests.csv")
    credits = []
    for row in requests:
        amount = int(row["quantity"]) * assignment[(row["board"], row["group"])]
        credits.append({"request": int(row["request"]), "credit": amount, "account": row["account"]})
    credits.sort(key=lambda r: r["request"])
    east = {"name": "East", "in_scope": bool(credits), "credits": credits, "total": sum(r["credit"] for r in credits)}
    commercial = {"name": "commercial", "in_scope": bool(credits), "accounts": {a: sum(r["credit"] for r in credits if r["account"] == a) for a in sorted({r["account"] for r in credits})}, "weighted_credit": sum(r["request"] * r["credit"] for r in credits)}
    cycles = []
    for row in table(root, "cycles.csv"):
        m, a, b, c = (int(row[k]) for k in ("modulus", "a", "b", "c"))
        x, y = settle_stream(int(row["x"]), int(row["y"]), m, a, b, c, int(row["rounds"]))
        cycles.append({"stream": row["stream"], "x": x, "y": y, "units": int(row["quantity"]) * (x + m * y)})
    cycles.sort(key=lambda r: r["stream"])
    south = {"name": "South", "in_scope": bool(cycles), "streams": cycles, "total": sum(r["units"] for r in cycles)}
    public = {"name": "public", "in_scope": bool(cycles), "settlement": sum((i + 1) * r["units"] for i, r in enumerate(cycles)), "eligible": [r["stream"] for r in cycles if r["units"] >= policy["eligibility_threshold"]]}
    west_values, history = replay(root)
    west = {"name": "West", "in_scope": bool(history), **west_values}
    quality = {"amendments": history, "orphan_count": sum(r["status"] == "orphan" for r in history), "superseded_count": sum(r["status"] == "superseded" for r in history), "applied_count": sum(r["status"] == "applied" for r in history)}
    parts = {"North": north["final_state"], "East": east["total"], "South": south["total"], "West": west["state"]}
    repeated = 0
    for event in normalized:
        repeated = (repeated * policy["clock_multiplier"] + event["units"] + event["instant"] * event["event"]) % policy["clock_modulus"]
    summary = {"report_id": policy["report_id"], "parts": parts, "total": sum(parts.values()), "residual": sum(parts.values()) - (sum(row["units"] for row in normalized) + sum(r["credit"] for r in credits) + sum(r["units"] for r in cycles) + west_values["state"])}
    return dict(zip(("summary.json", "policy_audit.json", "data_quality.json", "region_North.json", "region_South.json", "region_West.json", "region_East.json", "segment_commercial.json", "segment_public.json"), (summary, audit, quality, north, south, west, east, commercial, public)))



def _edit_copy(root: Path, number: int):
    # Every question first removes the supplied allocation's ordinary seal
    # atoms, exposing the repeated branching matrix before its lane-specific
    # edit is applied.
    for seal_name in ("allocation_groups.csv", "allocation_candidates.csv"):
        seal_path = root / seal_name
        with seal_path.open(encoding="utf-8", newline="") as stream:
            seal_reader = csv.DictReader(stream)
            seal_header = seal_reader.fieldnames
            seal_rows = list(seal_reader)
        for seal_row in seal_rows:
            seal_row["atoms"] = "|".join(atom for atom in seal_row["atoms"].split("|") if atom and not atom.startswith("seal-"))
        with seal_path.open("w", encoding="utf-8", newline="") as stream:
            seal_writer = csv.DictWriter(stream, fieldnames=seal_header, lineterminator="\n")
            seal_writer.writeheader()
            seal_writer.writerows(seal_rows)
    names = {1: "events.csv", 2: "clock_residues.csv", 3: "cycles.csv", 4: "cycles.csv", 5: "fold_corrections.csv", 6: "fold_records.csv", 7: "allocation_requests.csv", 8: "allocation_candidates.csv"}
    target = root / names[number]
    with target.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        header = reader.fieldnames
        rows = list(reader)
    if number == 1:
        for r in rows:
            if int(r["event"]) % 2 == 0:
                r["stamp"] = str(int(r["stamp"]) + 17)
    elif number == 2:
        with (root / "clock_terms.csv").open(encoding="utf-8", newline="") as stream:
            terms = list(csv.DictReader(stream))
        for r in rows:
            coefficient = sum(int(t["coefficient"]) for t in terms if t["source"] == "S00" and t["epoch"] == r["epoch"] and t["equation"] == r["equation"])
            r["residue"] = str((int(r["residue"]) + 3 * coefficient) % 41)
    elif number == 3:
        for r in rows:
            r["rounds"] = "999999999999999963"
    elif number == 4:
        for r in rows:
            if r["stream"] == "stream-00":
                r["quantity"] = str(-int(r["quantity"]))
    elif number == 5:
        for r in rows:
            if int(r["amendment"]) % 7 == 0:
                r["revision"] = "-1"
    elif number == 6:
        rows = [r for r in rows if int(r["position"]) % 7]
    elif number == 7:
        for r in rows:
            if int(r["request"]) % 5 == 0:
                r["quantity"] = str(int(r["quantity"]) * 3)
    elif number == 8:
        for r in rows:
            if "p00" in r["atoms"].split("|"):
                r["value"] = str(int(r["value"]) + 30)
    with target.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_result(result, output):
    output.mkdir(parents=True, exist_ok=True)
    for name, value in result.items():
        (output / name).write_text(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")


def verification_run(data, output):
    # All changed inputs and their reports live below OUT_DIR. Observed counts
    # are computed from files rather than stated as unexecuted expectations.
    opened = set()
    def note(event, args):
        if event == "open" and isinstance(args[0], (str, bytes)):
            opened.add(str(args[0]))
    sys.addaudithook(note)
    base = build(data)
    _write_result(base, output)
    for name, value in base.items():
        assert json.loads((output / name).read_text(encoding="utf-8")) == value
    work = Path(tempfile.mkdtemp(prefix="_verification-", dir=output))
    fields = (("policy_audit.json", "weighted_state"), ("region_North.json", "final_state"), ("segment_public.json", "settlement"), ("region_South.json", "total"), ("region_West.json", "weighted_states"), ("region_West.json", "weighted_states"), ("segment_commercial.json", "weighted_credit"), ("region_East.json", "total"))
    answers = {}
    counts = {}
    for question, (name, field) in enumerate(fields, 1):
        changed = work / ("input-" + str(question))
        if changed.exists():
            raise FileExistsError("verification copy already exists; use a fresh output directory")
        shutil.copytree(data, changed)
        _edit_copy(changed, question)
        reports = build(changed)
        destination = work / ("out-" + str(question))
        _write_result(reports, destination)
        for report_name, value in reports.items():
            assert json.loads((destination / report_name).read_text(encoding="utf-8")) == value
        answers[str(question)] = reports[name][field]
        counts[str(question)] = {"reports": len(reports), "events": len(table(changed, "events.csv")), "requests": len(table(changed, "allocation_requests.csv")), "streams": len(table(changed, "cycles.csv")), "records": len(table(changed, "fold_records.csv")), "amendments": len(table(changed, "fold_corrections.csv"))}
    print(json.dumps({"answers": answers, "report_count": len(base), "changed_copy_checks": counts, "open_check": {"distinct_paths": len(opened), "paths": sorted(opened)}} ,sort_keys=True))


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "--verify-and-answer":
        verification_run(Path(sys.argv[2]), Path(sys.argv[3]))
        return
    if len(sys.argv) != 3:
        raise SystemExit("usage: derive_report.py DATA_DIR OUT_DIR")
    result = build(Path(sys.argv[1]))
    _write_result(result, Path(sys.argv[2]))


if __name__ == "__main__":
    main()

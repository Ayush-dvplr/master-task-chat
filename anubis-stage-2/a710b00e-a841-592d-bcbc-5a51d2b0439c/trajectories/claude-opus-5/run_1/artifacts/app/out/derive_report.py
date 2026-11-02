#!/usr/bin/env python3
"""Reconcile a telemetry extract into the nine contract reports."""

import csv
import json
import os
import sys

RES_MOD = 41
OFFSET_LIMIT = 39
LARGE_MODULUS = 1000000007
SMALL_LIMIT = 127


class ExtractError(Exception):
    pass


# ---------------------------------------------------------------- input ----

def read_csv(data_dir, name, fields):
    path = os.path.join(data_dir, name)
    with open(path, "r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            raise ExtractError("%s: missing header" % name)
        if header != fields:
            raise ExtractError("%s: unexpected header %r" % (name, header))
        rows = []
        width = len(fields)
        for raw in reader:
            if len(raw) != width:
                raise ExtractError("%s: bad row width" % name)
            rows.append(dict(zip(fields, raw)))
        return rows


def read_table(data_dir, name, fields):
    """Like read_csv but yields positional rows, for the large tables."""
    path = os.path.join(data_dir, name)
    with open(path, "r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            raise ExtractError("%s: missing header" % name)
        if header != fields:
            raise ExtractError("%s: unexpected header %r" % (name, header))
        rows = list(reader)
    width = len(fields)
    for row in rows:
        if len(row) != width:
            raise ExtractError("%s: bad row width" % name)
    return rows


def read_json(data_dir, name):
    with open(os.path.join(data_dir, name), "r", encoding="utf-8") as handle:
        return json.load(handle)


def to_int(text, name):
    try:
        return int(text)
    except ValueError:
        raise ExtractError("%s: not an integer: %r" % (name, text))


def parse_atoms(cell, where):
    if cell == "":
        return []
    members = cell.split("|")
    if len(set(members)) != len(members):
        raise ExtractError("%s: repeated set member" % where)
    return members


# ---------------------------------------------------------------- clock ----

def row_reduce(matrix, width, mod):
    """Row reduce in place over GF(mod); return the pivot columns."""
    pivots = []
    row = 0
    for col in range(width):
        sel = None
        for r in range(row, len(matrix)):
            if matrix[r][col]:
                sel = r
                break
        if sel is None:
            continue
        matrix[row], matrix[sel] = matrix[sel], matrix[row]
        inv = pow(matrix[row][col], mod - 2, mod)
        matrix[row] = [(v * inv) % mod for v in matrix[row]]
        base = matrix[row]
        for r in range(len(matrix)):
            if r != row and matrix[r][col]:
                factor = matrix[r][col]
                matrix[r] = [(matrix[r][i] - factor * base[i]) % mod
                             for i in range(width + 1)]
        pivots.append(col)
        row += 1
        if row == len(matrix):
            break
    for r in range(row, len(matrix)):
        if matrix[r][width]:
            raise ExtractError("clock: inconsistent equations")
    return pivots


def solve_epoch_offsets(epoch, source_names, residue_rows, term_rows):
    """Return the unique offset vector for one epoch, or raise."""
    powers = {}
    shifts = {}
    coeffs = {}
    residues = {}
    for row in residue_rows:
        eq = row["equation"]
        if eq in residues:
            raise ExtractError("clock: duplicate residue row")
        residues[eq] = to_int(row["residue"], "clock_residues.residue") % RES_MOD
    for row in term_rows:
        src = row["source"]
        if src not in source_names:
            raise ExtractError("clock: unknown source %r" % src)
        power = to_int(row["power"], "clock_terms.power")
        shift = to_int(row["shift"], "clock_terms.shift")
        if power <= 0:
            raise ExtractError("clock: non-positive power")
        if src in powers and (powers[src] != power or shifts[src] != shift):
            raise ExtractError("clock: mixed power or shift for one source")
        powers[src] = power
        shifts[src] = shift
        key = (row["equation"], src)
        coeffs[key] = (coeffs.get(key, 0)
                       + to_int(row["coefficient"], "clock_terms.coefficient"))

    allowed = {}
    for src in source_names:
        power = powers.get(src, 1)
        shift = shifts.get(src, 0)
        table = {}
        for off in range(OFFSET_LIMIT):
            table[pow((off + shift) % RES_MOD, power, RES_MOD)] = off
        allowed[src] = table

    order = list(source_names)
    width = len(order)
    matrix = []
    for eq in sorted(residues):
        row = [0] * (width + 1)
        for col, src in enumerate(order):
            row[col] = coeffs.get((eq, src), 0) % RES_MOD
        row[width] = residues[eq]
        matrix.append(row)
    if not matrix:
        matrix = [[0] * (width + 1)]
    pivots = row_reduce(matrix, width, RES_MOD)
    pivot_set = set(pivots)
    free = [c for c in range(width) if c not in pivot_set]
    free_rank = {c: i for i, c in enumerate(free)}

    rules = {}
    for r, col in enumerate(pivots):
        support = [(c, matrix[r][c]) for c in free if matrix[r][c]]
        trigger = max([free_rank[c] for c, _ in support], default=-1)
        rules.setdefault(trigger, []).append((col, matrix[r][width], support))

    values = [None] * width
    solutions = []

    def place(rule):
        col, const, support = rule
        total = const
        for c, coef in support:
            total -= coef * values[c]
        val = total % RES_MOD
        if val not in allowed[order[col]]:
            return False
        values[col] = val
        return True

    def record():
        solutions.append([allowed[order[i]][values[i]] for i in range(width)])

    def recurse(depth):
        if depth == len(free):
            record()
            return
        col = free[depth]
        for val in sorted(allowed[order[col]]):
            values[col] = val
            done = []
            ok = True
            for rule in rules.get(depth, ()):
                if place(rule):
                    done.append(rule[0])
                else:
                    ok = False
                    break
            if ok:
                recurse(depth + 1)
            for c in done:
                values[c] = None
            values[col] = None
            if len(solutions) >= 2:
                return

    seeded = True
    for rule in rules.get(-1, ()):
        if not place(rule):
            seeded = False
            break
    if seeded:
        if free:
            recurse(0)
        else:
            record()

    if not solutions:
        raise ExtractError("clock: no admissible offsets for epoch %s" % epoch)
    if len(solutions) > 1:
        raise ExtractError("clock: ambiguous offsets for epoch %s" % epoch)
    return dict(zip(order, solutions[0]))


# ------------------------------------------------------------ north lane ----

def build_north(data_dir, policy):
    epoch_rows = read_csv(data_dir, "epochs.csv", ["epoch", "start", "end"])
    source_rows = read_csv(data_dir, "sources.csv", ["source", "unit_numerator"])
    alias_rows = read_csv(data_dir, "aliases.csv",
                          ["alias", "start", "end", "identity"])
    residue_rows = read_csv(data_dir, "clock_residues.csv",
                            ["epoch", "equation", "residue"])
    term_rows = read_csv(data_dir, "clock_terms.csv",
                         ["epoch", "equation", "source", "coefficient",
                          "power", "shift"])
    event_rows = read_csv(data_dir, "events.csv",
                          ["event", "source", "captured", "stamp", "alias",
                           "quantity"])

    epochs = [(row["epoch"], to_int(row["start"], "epochs.start"),
               to_int(row["end"], "epochs.end")) for row in epoch_rows]
    if len(set(e[0] for e in epochs)) != len(epochs):
        raise ExtractError("epochs: duplicate epoch name")

    units = {}
    for row in source_rows:
        src = row["source"]
        if src in units:
            raise ExtractError("sources: duplicate source")
        units[src] = to_int(row["unit_numerator"], "sources.unit_numerator")
    source_names = sorted(units)

    aliases = {}
    for row in alias_rows:
        aliases.setdefault(row["alias"], []).append(
            (to_int(row["start"], "aliases.start"),
             to_int(row["end"], "aliases.end"),
             row["identity"]))

    residues_by_epoch = {}
    terms_by_epoch = {}
    for row in residue_rows:
        residues_by_epoch.setdefault(row["epoch"], []).append(row)
    for row in term_rows:
        terms_by_epoch.setdefault(row["epoch"], []).append(row)

    offsets = {}
    for name, _start, _end in epochs:
        offsets[name] = solve_epoch_offsets(name, source_names,
                                            residues_by_epoch.get(name, []),
                                            terms_by_epoch.get(name, []))

    events = []
    seen = set()
    for row in event_rows:
        ident = to_int(row["event"], "events.event")
        if ident in seen:
            raise ExtractError("events: duplicate event identifier")
        seen.add(ident)
        src = row["source"]
        if src not in units:
            raise ExtractError("events: unknown source %r" % src)
        captured = to_int(row["captured"], "events.captured")
        stamp = to_int(row["stamp"], "events.stamp")
        quantity = to_int(row["quantity"], "events.quantity")
        hits = [e[0] for e in epochs if e[1] <= captured < e[2]]
        if len(hits) != 1:
            raise ExtractError("events: event %d has no unique epoch" % ident)
        instant = stamp - offsets[hits[0]][src]
        found = [a[2] for a in aliases.get(row["alias"], ())
                 if a[0] <= instant < a[1]]
        if len(found) != 1:
            raise ExtractError("events: event %d identity is not unique" % ident)
        events.append({"event": ident, "instant": instant,
                       "identity": found[0], "units": quantity * units[src]})

    events.sort(key=lambda e: (e["instant"], e["event"]))
    modulus = policy["clock_modulus"]
    multiplier = policy["clock_multiplier"]
    state = 0
    for item in events:
        state = (state * multiplier + item["units"]
                 + item["instant"] * item["event"]) % modulus
        item["state"] = state

    final_offsets = {}
    if epochs:
        final_offsets = dict(offsets[max(epochs, key=lambda e: e[1])[0]])

    identity_totals = {}
    for item in events:
        identity_totals[item["identity"]] = (
            identity_totals.get(item["identity"], 0) + item["units"])

    return {
        "events": events,
        "final_state": state,
        "units": sum(e["units"] for e in events),
        "final_offsets": final_offsets,
        "identity_totals": identity_totals,
        "weighted_state": sum(e["event"] * e["state"] for e in events),
    }


# ------------------------------------------------------------- east lane ----

def solve_component(cand_lists, natoms):
    """Return the unique candidate index per group, or raise.

    Exact cover by bitmask search.  One candidate is chosen per group, their
    atom sets must be disjoint and together cover atoms 0..natoms-1.  Every
    atom carries a sentinel bit above the candidate bits, so a covered atom
    leaves a zero word while an uncoverable one leaves just its sentinel.
    """
    ngroups = len(cand_lists)
    masks = []
    gids = []
    locs = []
    for g, cands in enumerate(cand_lists):
        for i, entry in enumerate(cands):
            masks.append(entry[0])
            gids.append(g)
            locs.append(i)
    ncands = len(masks)
    cand_all = (1 << ncands) - 1
    atom_cands = [1 << (ncands + a) for a in range(natoms)]
    for ci, m in enumerate(masks):
        while m:
            low = m & -m
            atom_cands[low.bit_length() - 1] |= 1 << ci
            m ^= low
    group_cands = [0] * ngroups
    for ci, g in enumerate(gids):
        group_cands[g] |= 1 << ci
    conflict = []
    for ci, m in enumerate(masks):
        bad = group_cands[gids[ci]]
        while m:
            low = m & -m
            bad |= atom_cands[low.bit_length() - 1]
            m ^= low
        conflict.append(bad)
    empties = [[i for i, entry in enumerate(cands) if entry[0] == 0]
               for cands in cand_lists]
    live0 = cand_all
    for a in range(natoms):
        live0 |= 1 << (ncands + a)
    solutions = []

    def finish(chosen):
        picks = [None] * ngroups
        for ci in chosen:
            picks[gids[ci]] = locs[ci]
        multiplicity = 1
        for g in range(ngroups):
            if picks[g] is None:
                if not empties[g]:
                    return
                multiplicity *= len(empties[g])
                picks[g] = empties[g][0]
        solutions.append(picks)
        if multiplicity > 1:
            solutions.append(picks)

    def search(live, atoms, chosen):
        while True:
            best = 0
            bestcount = 1 << 30
            forced = None
            for entry in atoms:
                opts = live & entry
                count = opts.bit_count()
                if count < 2:
                    return
                if count == 2:
                    if forced is None:
                        forced = [opts & cand_all]
                    else:
                        forced.append(opts & cand_all)
                elif count < bestcount:
                    bestcount = count
                    best = opts
            if forced is None:
                break
            applied = 0
            for opts in forced:
                if opts & applied:
                    continue
                if not live & opts:
                    return
                applied |= opts
                ci = opts.bit_length() - 1
                live &= ~conflict[ci]
                chosen = chosen + [ci]
            atoms = [entry for entry in atoms if live & entry]
            if not atoms:
                finish(chosen)
                return
        if not best:
            finish(chosen)
            return
        opts = best & cand_all
        while opts:
            low = opts & -opts
            opts ^= low
            ci = low.bit_length() - 1
            nlive = live & ~conflict[ci]
            search(nlive, [e for e in atoms if nlive & e], chosen + [ci])
            if len(solutions) > 1:
                return

    search(live0, list(atom_cands), [])
    if not solutions:
        raise ExtractError("allocation: a component has no assignment")
    if len(solutions) > 1:
        raise ExtractError("allocation: a component has several assignments")
    return solutions[0]


def build_east(data_dir):
    group_rows = read_table(data_dir, "allocation_groups.csv",
                            ["board", "component", "group", "atoms"])
    cand_rows = read_table(data_dir, "allocation_candidates.csv",
                           ["board", "component", "group", "candidate",
                            "atoms", "value"])
    request_rows = read_table(data_dir, "allocation_requests.csv",
                              ["request", "board", "group", "account",
                               "quantity"])

    required = {}
    for board, component, group, atoms in group_rows:
        slot = required.setdefault((board, component), {})
        if group in slot:
            raise ExtractError("allocation: duplicate group row")
        slot[group] = parse_atoms(atoms, "allocation_groups.atoms")
    board_groups = set()
    for board, component in required:
        for group in required[(board, component)]:
            if (board, group) in board_groups:
                raise ExtractError("allocation: group repeated within a board")
            board_groups.add((board, group))

    cands = {}
    for row in cand_rows:
        key = (row[0], row[1])
        slot = required.get(key)
        if slot is None or row[2] not in slot:
            continue
        cands.setdefault(key, {}).setdefault(row[2], []).append(row)

    chosen = {}
    for key in sorted(required):
        groups = sorted(required[key])
        bits = {}
        for group in groups:
            for atom in required[key][group]:
                if atom not in bits:
                    bits[atom] = 1 << len(bits)
        comp_cands = cands.get(key, {})
        cand_lists = []
        for group in groups:
            entries = comp_cands.get(group, ())
            names = set()
            usable = []
            for row in entries:
                if row[3] in names:
                    raise ExtractError("allocation: duplicate candidate name")
                names.add(row[3])
                mask = 0
                for atom in parse_atoms(row[4],
                                        "allocation_candidates.atoms"):
                    bit = bits.get(atom)
                    if bit is None:
                        mask = None
                        break
                    mask |= bit
                if mask is not None:
                    usable.append((mask,
                                   to_int(row[5],
                                          "allocation_candidates.value")))
            cand_lists.append(usable)
        picks = solve_component(cand_lists, len(bits))
        for gi, group in enumerate(groups):
            chosen[(key[0], group)] = cand_lists[gi][picks[gi]][1]

    credits = []
    seen = set()
    for row in request_rows:
        ident = to_int(row[0], "allocation_requests.request")
        if ident in seen:
            raise ExtractError("allocation: duplicate request identifier")
        seen.add(ident)
        key = (row[1], row[2])
        if key not in chosen:
            raise ExtractError("allocation: request %d names an absent group"
                               % ident)
        quantity = to_int(row[4], "allocation_requests.quantity")
        credits.append({"request": ident, "account": row[3],
                        "credit": quantity * chosen[key]})
    credits.sort(key=lambda r: r["request"])

    accounts = {}
    for row in credits:
        accounts[row["account"]] = accounts.get(row["account"], 0) + row["credit"]

    return {
        "credits": credits,
        "total": sum(r["credit"] for r in credits),
        "accounts": accounts,
        "weighted_credit": sum(r["request"] * r["credit"] for r in credits),
    }


# ------------------------------------------------------------ south lane ----

def settle_small(x, y, m, a, b, c, rounds):
    seen = {}
    seq = []
    cur = (x, y)
    step = 0
    while step < rounds:
        if cur in seen:
            start = seen[cur]
            cycle = step - start
            return seq[start + (rounds - start) % cycle]
        seen[cur] = step
        seq.append(cur)
        x0, y0 = cur
        cur = (y0, (a * x0 + b * y0 + c + x0 * y0) % m)
        step += 1
    return cur


def fib_matrix(n, mod):
    """[[0,1],[1,1]] raised to n, modulo mod."""
    ra, rb, rc, rd = 1, 0, 0, 1
    ba, bb, bc, bd = 0, 1, 1, 1
    while n:
        if n & 1:
            ra, rb, rc, rd = ((ba * ra + bb * rc) % mod,
                              (ba * rb + bb * rd) % mod,
                              (bc * ra + bd * rc) % mod,
                              (bc * rb + bd * rd) % mod)
        ba, bb, bc, bd = ((ba * ba + bb * bc) % mod,
                          (ba * bb + bb * bd) % mod,
                          (bc * ba + bd * bc) % mod,
                          (bc * bb + bd * bd) % mod)
        n >>= 1
    return ra, rb, rc, rd


def settle_large(x, y, rounds):
    p = LARGE_MODULUS
    u = (x + 1) % p
    v = (y + 1) % p
    if u == 0 or v == 0:
        for _ in range(min(rounds, 2)):
            u, v = v, u * v % p
        return (u - 1) % p, (v - 1) % p
    ea, eb, ec, ed = fib_matrix(rounds, p - 1)
    un = pow(u, ea, p) * pow(v, eb, p) % p
    vn = pow(u, ec, p) * pow(v, ed, p) % p
    return (un - 1) % p, (vn - 1) % p


def build_south(data_dir, policy):
    rows = read_csv(data_dir, "cycles.csv",
                    ["stream", "x", "y", "modulus", "a", "b", "c", "rounds",
                     "quantity"])
    streams = []
    names = set()
    for row in rows:
        name = row["stream"]
        if name in names:
            raise ExtractError("cycles: duplicate stream identifier")
        names.add(name)
        m = to_int(row["modulus"], "cycles.modulus")
        x = to_int(row["x"], "cycles.x")
        y = to_int(row["y"], "cycles.y")
        a = to_int(row["a"], "cycles.a")
        b = to_int(row["b"], "cycles.b")
        c = to_int(row["c"], "cycles.c")
        rounds = to_int(row["rounds"], "cycles.rounds")
        quantity = to_int(row["quantity"], "cycles.quantity")
        if m <= 0:
            raise ExtractError("cycles: non-positive modulus")
        if rounds < 0:
            raise ExtractError("cycles: negative round count")
        if not (0 <= x < m and 0 <= y < m):
            raise ExtractError("cycles: initial pair outside the modulus")
        if m <= SMALL_LIMIT:
            sx, sy = settle_small(x, y, m, a, b, c, rounds)
        elif m == LARGE_MODULUS and a == 1 and b == 1 and c == 0:
            sx, sy = settle_large(x, y, rounds)
        else:
            raise ExtractError("cycles: stream %r fits no permitted family"
                               % name)
        streams.append({"stream": name, "x": sx, "y": sy,
                        "units": quantity * (sx + m * sy)})
    streams.sort(key=lambda s: s["stream"])
    threshold = policy["eligibility_threshold"]
    return {
        "streams": streams,
        "total": sum(s["units"] for s in streams),
        "settlement": sum((i + 1) * s["units"] for i, s in enumerate(streams)),
        "eligible": [s["stream"] for s in streams if s["units"] >= threshold],
    }


# ------------------------------------------------------------- west lane ----

class LinkCutForest:
    """Link-cut trees carrying directed affine path products."""

    def __init__(self, coeffs, mod):
        size = len(coeffs) + 1
        self.mod = mod
        self.left = [0] * size
        self.right = [0] * size
        self.up = [0] * size
        self.rev = [False] * size
        self.sa = [1] * size
        self.sb = [0] * size
        self.fa = [1] * size
        self.fb = [0] * size
        self.ba = [1] * size
        self.bb = [0] * size
        for i, (a, b) in enumerate(coeffs, start=1):
            self.sa[i] = self.fa[i] = self.ba[i] = a % mod
            self.sb[i] = self.fb[i] = self.bb[i] = b % mod

    def _pull(self, x):
        mod = self.mod
        left = self.left[x]
        right = self.right[x]
        a = self.sa[x]
        b = self.sb[x]
        if left:
            a, b = a * self.fa[left] % mod, (a * self.fb[left] + b) % mod
        if right:
            a, b = (self.fa[right] * a % mod,
                    (self.fa[right] * b + self.fb[right]) % mod)
        self.fa[x] = a
        self.fb[x] = b
        a = self.sa[x]
        b = self.sb[x]
        if right:
            a, b = a * self.ba[right] % mod, (a * self.bb[right] + b) % mod
        if left:
            a, b = (self.ba[left] * a % mod,
                    (self.ba[left] * b + self.bb[left]) % mod)
        self.ba[x] = a
        self.bb[x] = b

    def _flip(self, x):
        self.rev[x] = not self.rev[x]
        self.fa[x], self.ba[x] = self.ba[x], self.fa[x]
        self.fb[x], self.bb[x] = self.bb[x], self.fb[x]

    def _push(self, x):
        if self.rev[x]:
            left = self.left[x]
            right = self.right[x]
            self.left[x] = right
            self.right[x] = left
            if left:
                self._flip(left)
            if right:
                self._flip(right)
            self.rev[x] = False

    def _is_root(self, x):
        p = self.up[x]
        return p == 0 or (self.left[p] != x and self.right[p] != x)

    def _rotate(self, x):
        p = self.up[x]
        g = self.up[p]
        p_was_root = self._is_root(p)
        if self.left[p] == x:
            child = self.right[x]
            self.left[p] = child
            self.right[x] = p
        else:
            child = self.left[x]
            self.right[p] = child
            self.left[x] = p
        if child:
            self.up[child] = p
        self.up[p] = x
        self.up[x] = g
        if not p_was_root:
            if self.left[g] == p:
                self.left[g] = x
            elif self.right[g] == p:
                self.right[g] = x
        self._pull(p)
        self._pull(x)

    def _splay(self, x):
        chain = [x]
        node = x
        while not self._is_root(node):
            node = self.up[node]
            chain.append(node)
        while chain:
            self._push(chain.pop())
        while not self._is_root(x):
            p = self.up[x]
            if not self._is_root(p):
                g = self.up[p]
                if (self.left[g] == p) == (self.left[p] == x):
                    self._rotate(p)
                else:
                    self._rotate(x)
            self._rotate(x)

    def _access(self, x):
        last = 0
        node = x
        while node:
            self._splay(node)
            self.right[node] = last
            self._pull(node)
            last = node
            node = self.up[node]
        self._splay(x)

    def make_root(self, x):
        self._access(x)
        self._flip(x)
        self._push(x)

    def find_root(self, x):
        self._access(x)
        while self.left[x]:
            self._push(x)
            x = self.left[x]
        self._splay(x)
        return x

    def connected(self, x, y):
        return self.find_root(x) == self.find_root(y)

    def link(self, x, y):
        self.make_root(x)
        self.up[x] = y

    def cut(self, x, y):
        self.make_root(x)
        self._access(y)
        self.left[y] = 0
        self.up[x] = 0
        self._pull(y)

    def set_coeffs(self, x, a, b):
        self._access(x)
        self.sa[x] = a % self.mod
        self.sb[x] = b % self.mod
        self._pull(x)

    def path_apply(self, u, v, start):
        self.make_root(u)
        self._access(v)
        return (self.fa[v] * start + self.fb[v]) % self.mod


def build_west(data_dir, replay):
    record_rows = read_csv(data_dir, "fold_records.csv",
                           ["record", "position", "a", "b"])
    amend_rows = read_csv(data_dir, "fold_corrections.csv",
                          ["amendment", "arrival", "record", "revision", "a",
                           "b", "action", "cut_left", "cut_right", "link_left",
                           "link_right", "query_start", "query_end"])
    modulus = replay["modulus"]
    initial = replay["initial"]
    if modulus <= 0:
        raise ExtractError("replay: non-positive modulus")

    records = [(to_int(row["position"], "fold_records.position"),
                row["record"],
                to_int(row["a"], "fold_records.a"),
                to_int(row["b"], "fold_records.b")) for row in record_rows]
    if len(set(r[0] for r in records)) != len(records):
        raise ExtractError("fold_records: duplicate position")
    if len(set(r[1] for r in records)) != len(records):
        raise ExtractError("fold_records: duplicate record identifier")
    records.sort()
    index = {r[1]: i + 1 for i, r in enumerate(records)}
    forest = LinkCutForest([(r[2], r[3]) for r in records], modulus)
    edges = set()
    for i in range(1, len(records)):
        forest.link(i, i + 1)
        edges.add((i, i + 1))

    def path_state(start_name, end_name):
        u = index.get(start_name)
        v = index.get(end_name)
        if u is None or v is None or not forest.connected(u, v):
            return initial % modulus
        return forest.path_apply(u, v, initial)

    if records:
        state = path_state(records[0][1], records[-1][1])
    else:
        state = initial % modulus

    accepted = {r[1]: -1 for r in records}
    ordered = []
    seen = set()
    for row in amend_rows:
        ident = to_int(row["amendment"], "fold_corrections.amendment")
        if ident in seen:
            raise ExtractError("fold_corrections: duplicate amendment")
        seen.add(ident)
        ordered.append((to_int(row["arrival"], "fold_corrections.arrival"),
                        ident, row))
    ordered.sort(key=lambda item: (item[0], item[1]))

    amendments = []
    orphan = 0
    superseded = 0
    applied = 0
    for _arrival, ident, row in ordered:
        name = row["record"]
        revision = to_int(row["revision"], "fold_corrections.revision")
        if name not in index:
            status = "orphan"
            orphan += 1
        elif revision <= accepted[name]:
            status = "superseded"
            superseded += 1
        else:
            status = "applied"
            applied += 1
            accepted[name] = revision
            forest.set_coeffs(index[name],
                              to_int(row["a"], "fold_corrections.a"),
                              to_int(row["b"], "fold_corrections.b"))
            action = row["action"]
            if action == "swap_edge":
                cut_l = index.get(row["cut_left"])
                cut_r = index.get(row["cut_right"])
                link_l = index.get(row["link_left"])
                link_r = index.get(row["link_right"])
                if None not in (cut_l, cut_r, link_l, link_r):
                    edge = (min(cut_l, cut_r), max(cut_l, cut_r))
                    if edge in edges:
                        forest.cut(cut_l, cut_r)
                        edges.discard(edge)
                        if link_l != link_r and not forest.connected(link_l,
                                                                     link_r):
                            forest.link(link_l, link_r)
                            edges.add((min(link_l, link_r),
                                       max(link_l, link_r)))
                        else:
                            forest.link(cut_l, cut_r)
                            edges.add(edge)
            elif action != "keep":
                raise ExtractError("fold_corrections: unknown action %r"
                                   % action)
            state = path_state(row["query_start"], row["query_end"])
        amendments.append({"amendment": ident, "status": status,
                           "state": state})

    return {
        "state": state,
        "weighted_states": sum(a["amendment"] * a["state"]
                               for a in amendments),
        "revised": applied,
        "amendments": amendments,
        "orphan_count": orphan,
        "superseded_count": superseded,
        "applied_count": applied,
        "in_scope": bool(amendments),
    }


# --------------------------------------------------------------- output ----

def dump(out_dir, name, obj):
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False) + "\n"
    path = os.path.join(out_dir, name)
    if os.path.islink(path):
        os.unlink(path)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def build_reports(data_dir):
    policy = read_json(data_dir, "policy.json")
    replay = read_json(data_dir, "replay.json")

    north = build_north(data_dir, policy)
    east = build_east(data_dir)
    south = build_south(data_dir, policy)
    west = build_west(data_dir, replay)

    parts = {
        "North": north["final_state"],
        "East": east["total"],
        "South": south["total"],
        "West": west["state"],
    }
    total = sum(parts.values())
    residual = (total - sum(north["identity_totals"].values())
                - sum(east["accounts"].values())
                - south["total"] - west["state"])

    return {
        "region_North.json": {
            "name": "North",
            "in_scope": bool(north["events"]),
            "events": [{"event": e["event"], "instant": e["instant"],
                        "identity": e["identity"], "units": e["units"],
                        "state": e["state"]} for e in north["events"]],
            "final_state": north["final_state"],
            "units": north["units"],
        },
        "policy_audit.json": {
            "final_offsets": north["final_offsets"],
            "identity_totals": north["identity_totals"],
            "weighted_state": north["weighted_state"],
        },
        "region_East.json": {
            "name": "East",
            "in_scope": bool(east["credits"]),
            "credits": east["credits"],
            "total": east["total"],
        },
        "segment_commercial.json": {
            "name": "commercial",
            "in_scope": bool(east["credits"]),
            "accounts": east["accounts"],
            "weighted_credit": east["weighted_credit"],
        },
        "region_South.json": {
            "name": "South",
            "in_scope": bool(south["streams"]),
            "streams": south["streams"],
            "total": south["total"],
        },
        "segment_public.json": {
            "name": "public",
            "in_scope": bool(south["streams"]),
            "settlement": south["settlement"],
            "eligible": south["eligible"],
        },
        "region_West.json": {
            "name": "West",
            "in_scope": west["in_scope"],
            "state": west["state"],
            "weighted_states": west["weighted_states"],
            "revised": west["revised"],
        },
        "data_quality.json": {
            "amendments": west["amendments"],
            "orphan_count": west["orphan_count"],
            "superseded_count": west["superseded_count"],
            "applied_count": west["applied_count"],
        },
        "summary.json": {
            "report_id": policy["report_id"],
            "parts": parts,
            "total": total,
            "residual": residual,
        },
    }


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir = argv[1]
    out_dir = argv[2]
    reports = build_reports(data_dir)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    for name in sorted(reports):
        dump(out_dir, name, reports[name])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except ExtractError as exc:
        sys.stderr.write("error: %s\n" % exc)
        sys.exit(1)

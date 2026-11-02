#!/usr/bin/env python3
"""Reconcile a telemetry extract into the nine reports defined by its contracts.

Usage:
    python3 derive_report.py DATA_DIR OUT_DIR

The program reads only DATA_DIR, writes only the nine report files into
OUT_DIR, and leaves the extract untouched.  Nothing here depends on the
particular extract: every bound, name and value is taken from the extract.
"""

import csv
import json
import os
import re
import sys

CLOCK_PRIME = 41
CLOCK_GROUP = 40
OFFSET_LIMIT = 38
LARGE_MODULUS = 1000000007
ORBIT_BUDGET = 2000000
PROBE = 16
SMALL_MODULUS_LIMIT = 127
SOLUTION_CAP = 2

REPORT_FILES = (
    'region_North.json',
    'policy_audit.json',
    'region_East.json',
    'segment_commercial.json',
    'region_South.json',
    'segment_public.json',
    'region_West.json',
    'data_quality.json',
    'summary.json',
)

_INTEGER = re.compile(r'\A[+-]?[0-9]+\Z')


class ContractError(Exception):
    """The extract does not reconcile; no report is written."""


# --------------------------------------------------------------------------
# shared helpers
# --------------------------------------------------------------------------

def read_table(data_dir, filename, columns):
    """Return (column index map, rows) for one CSV table of the extract."""
    path = os.path.join(data_dir, filename)
    try:
        handle = open(path, 'r', encoding='utf-8', newline='')
    except OSError as exc:
        raise ContractError('%s: %s' % (filename, exc))
    with handle:
        rows = [row for row in csv.reader(handle)]
    if not rows:
        raise ContractError('%s: missing header row' % filename)
    header = rows[0]
    index = {}
    for position, name in enumerate(header):
        index[name] = position
    missing = [name for name in columns if name not in index]
    if missing:
        raise ContractError('%s: missing column(s) %s' % (filename, ','.join(missing)))
    width = len(header)
    body = []
    for row in rows[1:]:
        if not any(row):
            continue
        if len(row) != width:
            raise ContractError('%s: row has %d cells, header has %d'
                                % (filename, len(row), width))
        body.append(row)
    return index, body


def cell_int(value, where):
    if not _INTEGER.match(value):
        raise ContractError('%s: %r is not a decimal integer' % (where, value))
    return int(value)


def cell_set(value, where):
    """Parse a vertical-bar separated set cell."""
    if value == '':
        return frozenset()
    members = value.split('|')
    result = frozenset(members)
    if len(result) != len(members):
        raise ContractError('%s: repeated member in set %r' % (where, value))
    return result


def load_json(data_dir, filename, spec):
    """Load a JSON object, checking that every listed key has its stated type."""
    path = os.path.join(data_dir, filename)
    try:
        handle = open(path, 'r', encoding='utf-8')
    except OSError as exc:
        raise ContractError('%s: %s' % (filename, exc))
    with handle:
        try:
            obj = json.load(handle)
        except ValueError as exc:
            raise ContractError('%s: invalid JSON (%s)' % (filename, exc))
    if not isinstance(obj, dict):
        raise ContractError('%s: expected a JSON object' % filename)
    values = {}
    for key, kind in spec:
        if key not in obj:
            raise ContractError('%s: missing key %r' % (filename, key))
        value = obj[key]
        if kind is int:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ContractError('%s: %r must be an integer' % (filename, key))
        elif kind is str:
            if not isinstance(value, str):
                raise ContractError('%s: %r must be text' % (filename, key))
        values[key] = value
    return values


def affine_apply(mapping, state, mod):
    a, b = mapping
    return (a * state + b) % mod


def _gcd(a, b):
    while b:
        a, b = b, a % b
    return a


# --------------------------------------------------------------------------
# clock lane: offsets, instants, identities and the North state
# --------------------------------------------------------------------------

def solve_linear_mod(prime, rows, rhs, width):
    """Reduce an augmented system over GF(prime).

    Returns (rank, solution) where solution is None when the system is
    inconsistent.  When rank < width the solution is one particular point of
    an affine subspace of positive dimension.
    """
    work = []
    for row, value in zip(rows, rhs):
        work.append([cell % prime for cell in row] + [value % prime])
    rank = 0
    pivots = []
    for col in range(width):
        pivot = -1
        for i in range(rank, len(work)):
            if work[i][col]:
                pivot = i
                break
        if pivot < 0:
            continue
        work[rank], work[pivot] = work[pivot], work[rank]
        row = work[rank]
        inverse = pow(row[col], prime - 2, prime)
        for j in range(col, width + 1):
            row[j] = row[j] * inverse % prime
        for i in range(len(work)):
            if i != rank and work[i][col]:
                factor = work[i][col]
                other = work[i]
                for j in range(col, width + 1):
                    other[j] = (other[j] - factor * row[j]) % prime
        pivots.append(col)
        rank += 1
    for i in range(rank, len(work)):
        if work[i][width]:
            return rank, None
    solution = [0] * width
    for i, col in enumerate(pivots):
        solution[col] = work[i][width]
    return rank, solution


def load_clock(data_dir):
    """Solve every epoch's offset assignment; error unless each is unique."""
    source_index, source_rows = read_table(data_dir, 'sources.csv',
                                           ('source', 'unit_numerator'))
    sources = []
    numerator = {}
    for row in source_rows:
        name = row[source_index['source']]
        if name in numerator:
            raise ContractError('sources.csv: duplicate source %r' % name)
        numerator[name] = cell_int(row[source_index['unit_numerator']],
                                   'sources.csv unit_numerator')
        sources.append(name)

    epoch_index, epoch_rows = read_table(data_dir, 'epochs.csv',
                                         ('epoch', 'start', 'end'))
    epochs = []
    names = set()
    for row in epoch_rows:
        name = row[epoch_index['epoch']]
        if name in names:
            raise ContractError('epochs.csv: duplicate epoch %r' % name)
        names.add(name)
        start = cell_int(row[epoch_index['start']], 'epochs.csv start')
        end = cell_int(row[epoch_index['end']], 'epochs.csv end')
        epochs.append((name, start, end))
    if not epochs:
        raise ContractError('epochs.csv: the epoch list is empty')
    by_start = sorted(range(len(epochs)), key=lambda i: (epochs[i][1], epochs[i][2]))
    for prev, cur in zip(by_start, by_start[1:]):
        if epochs[cur][1] < epochs[prev][2]:
            raise ContractError('epochs.csv: %r and %r overlap'
                                % (epochs[prev][0], epochs[cur][0]))

    residue_index, residue_rows = read_table(data_dir, 'clock_residues.csv',
                                             ('epoch', 'equation', 'residue'))
    residues = {}
    for row in residue_rows:
        epoch = row[residue_index['epoch']]
        equation = row[residue_index['equation']]
        if epoch not in names:
            raise ContractError('clock_residues.csv: unknown epoch %r' % epoch)
        value = cell_int(row[residue_index['residue']],
                         'clock_residues.csv residue')
        key = (epoch, equation)
        if key in residues and residues[key] != value:
            raise ContractError('clock_residues.csv: conflicting residues for %r'
                                % equation)
        residues[key] = value

    term_index, term_rows = read_table(data_dir, 'clock_terms.csv',
                                       ('epoch', 'equation', 'source',
                                        'coefficient', 'power', 'shift'))
    coefficients = {}
    specs = {}
    for row in term_rows:
        epoch = row[term_index['epoch']]
        equation = row[term_index['equation']]
        source = row[term_index['source']]
        if epoch not in names:
            raise ContractError('clock_terms.csv: unknown epoch %r' % epoch)
        if source not in numerator:
            raise ContractError('clock_terms.csv: unknown source %r' % source)
        coefficient = cell_int(row[term_index['coefficient']],
                               'clock_terms.csv coefficient')
        power = cell_int(row[term_index['power']], 'clock_terms.csv power')
        shift = cell_int(row[term_index['shift']], 'clock_terms.csv shift')
        if power <= 0 or _gcd(power, CLOCK_GROUP) != 1:
            raise ContractError('clock_terms.csv: power %d is not relatively '
                                'prime to %d' % (power, CLOCK_GROUP))
        key = (epoch, source)
        spec = (power, shift % CLOCK_PRIME)
        if key in specs and specs[key] != spec:
            raise ContractError('clock_terms.csv: source %r has differing '
                                'power or shift in epoch %r' % (source, epoch))
        specs[key] = spec
        coefficients[(epoch, equation, source)] = \
            coefficients.get((epoch, equation, source), 0) + coefficient

    offsets = {}
    for name, _start, _end in epochs:
        equations = sorted(equation for (epoch, equation) in residues
                           if epoch == name)
        rows = []
        rhs = []
        for equation in equations:
            rows.append([coefficients.get((name, equation, source), 0)
                         for source in sources])
            rhs.append(residues[(name, equation)])
        width = len(sources)
        rank, solution = solve_linear_mod(CLOCK_PRIME, rows, rhs, width)
        if solution is None:
            raise ContractError('clock evidence for epoch %r is inconsistent'
                                % name)
        if rank < width:
            # A free direction admits at least 41 - 2*len(sources) >= 19
            # offset vectors in range, so the assignment cannot be unique.
            raise ContractError('clock evidence for epoch %r is ambiguous'
                                % name)
        allowed = {}
        for source in sources:
            spec = specs.get((name, source))
            if spec is None:
                raise ContractError('clock evidence for epoch %r is ambiguous'
                                    % name)
            power, shift = spec
            table = {}
            for offset in range(OFFSET_LIMIT + 1):
                table[pow((offset + shift) % CLOCK_PRIME, power, CLOCK_PRIME)] = offset
            allowed[source] = table
        epoch_offsets = {}
        for position, source in enumerate(sources):
            value = solution[position]
            table = allowed[source]
            if value not in table:
                raise ContractError('clock evidence for epoch %r admits no '
                                    'offset for source %r' % (name, source))
        # Solve directly: one equation per source keeps the vector unique.
        for position, source in enumerate(sources):
            spec = specs[(name, source)]
            power, shift = spec
            table = allowed[source]
            value = solution[position]
            if value not in table:
                raise ContractError('clock evidence for epoch %r admits no '
                                    'offset for source %r' % (name, source))
            epoch_offsets[source] = table[value]
        offsets[name] = epoch_offsets
    return sources, numerator, epochs, offsets


def derive_north(data_dir, policy, clock):
    sources, numerator, epochs, offsets = clock
    event_index, event_rows = read_table(data_dir, 'events.csv',
                                         ('event', 'source', 'captured',
                                          'stamp', 'alias', 'quantity'))
    alias_index, alias_rows = read_table(data_dir, 'aliases.csv',
                                        ('alias', 'start', 'end', 'identity'))
    identities = {}
    for row in alias_rows:
        alias = row[alias_index['alias']]
        start = cell_int(row[alias_index['start']], 'aliases.csv start')
        end = cell_int(row[alias_index['end']], 'aliases.csv end')
        identities.setdefault(alias, []).append((start, end,
                                                 row[alias_index['identity']]))
    modulus = policy['clock_modulus']
    multiplier = policy['clock_multiplier']
    events = []
    seen = set()
    for row in event_rows:
        where = 'events.csv'
        identifier = cell_int(row[event_index['event']], where + ' event')
        if identifier in seen:
            raise ContractError('%s: duplicate event identifier %d'
                                % (where, identifier))
        seen.add(identifier)
        source = row[event_index['source']]
        if source not in numerator:
            raise ContractError('%s: unknown source %r' % (where, source))
        captured = cell_int(row[event_index['captured']], where + ' captured')
        stamp = cell_int(row[event_index['stamp']], where + ' stamp')
        alias = row[event_index['alias']]
        quantity = cell_int(row[event_index['quantity']], where + ' quantity')
        matched = [name for name, start, end in epochs if start <= captured < end]
        if len(matched) != 1:
            raise ContractError('%s: event %d is outside every epoch'
                                % (where, identifier))
        instant = stamp - offsets[matched[0]][source]
        unit = quantity * numerator[source]
        candidates = [text for start, end, text in identities.get(alias, ())
                      if start <= instant < end]
        if len(candidates) != 1:
            raise ContractError('%s: event %d has %d matching identities'
                                % (where, identifier, len(candidates)))
        events.append((instant, identifier, candidates[0], unit))
    events.sort(key=lambda item: (item[0], item[1]))
    state = 0
    rows = []
    totals = {}
    weighted = 0
    units_sum = 0
    for instant, identifier, identity, unit in events:
        state = (state * multiplier + unit + instant * identifier) % modulus
        rows.append({'event': identifier, 'instant': instant,
                     'identity': identity, 'units': unit, 'state': state})
        totals[identity] = totals.get(identity, 0) + unit
        weighted += identifier * state
        units_sum += unit
    return {
        'events': rows,
        'in_scope': bool(rows),
        'final_state': state,
        'units': units_sum,
        'identity_totals': totals,
        'weighted_state': weighted,
    }


# --------------------------------------------------------------------------
# allocation lane: exact cover of the required atoms, then credits
# --------------------------------------------------------------------------

def solve_component(groups, atoms_of, candidates_of):
    """Return the component's assignments, at most SOLUTION_CAP of them.

    The component is an exact cover: each group chooses one candidate, the
    chosen atom sets are pairwise disjoint and their union is the required
    set.  Candidates are numbered as slots, availability is one integer over
    all slots, and each slot's conflict mask (every other slot sharing an
    atom, plus the rest of its own group) is precomputed, so a choice costs a
    couple of integer operations with no undo bookkeeping.  Atom bit positions
    follow the number of slots that can cover them, so the branching atom is
    the first one whose available slots are fewest.
    """
    required = set()
    for group in groups:
        required |= atoms_of[group]
    order = sorted(required)
    bit = dict((atom, i) for i, atom in enumerate(order))
    n = len(order)
    count = len(groups)
    slots = []
    group_lo = []
    group_hi = []
    for gi, group in enumerate(groups):
        group_lo.append(len(slots))
        seen_names = set()
        for name, atoms, value in candidates_of.get(group, ()):
            if name in seen_names:
                raise ContractError('allocation_candidates.csv: candidate %r '
                                    'is not unique within group %r'
                                    % (name, group))
            seen_names.add(name)
            mask = 0
            admissible = True
            for atom in atoms:
                position = bit.get(atom)
                if position is None:
                    admissible = False
                    break
                mask |= 1 << position
            if admissible:
                slots.append((gi, name, mask, value))
        group_hi.append(len(slots))
    total = len(slots)
    if total == 0:
        return [{}] if (n == 0 and count == 0) else []
    for gi in range(count):
        if group_hi[gi] == group_lo[gi]:
            return []

    atom_slots = [0] * n
    for si, (gi, name, mask, value) in enumerate(slots):
        rest = mask
        while rest:
            low = rest & -rest
            atom_slots[low.bit_length() - 1] |= 1 << si
            rest ^= low
    # rank atoms by how many slots can cover them, so bit extraction walks
    # them in that order; the slot bitsets themselves need no relabelling
    ranked = sorted(range(n), key=lambda a: (atom_slots[a].bit_count(), a))
    position_of = dict((a, i) for i, a in enumerate(ranked))
    atom_bits = [0] * n
    for a in range(n):
        atom_bits[position_of[a]] = atom_slots[a]
    group_bits = [0] * count
    for si, (gi, name, mask, value) in enumerate(slots):
        group_bits[gi] |= 1 << si
    conflict = []
    for si, (gi, name, mask, value) in enumerate(slots):
        combined = group_bits[gi]
        rest = mask
        while rest:
            low = rest & -rest
            combined |= atom_slots[low.bit_length() - 1]
            rest ^= low
        conflict.append(combined & ~(1 << si))
    for si, (gi, name, mask, value) in enumerate(slots):
        rest = mask
        new = 0
        while rest:
            low = rest & -rest
            new |= 1 << position_of[low.bit_length() - 1]
            rest ^= low
        slots[si] = (gi, name, new, value)

    solutions = []
    acc = []
    full = (1 << n) - 1
    all_avail = (1 << total) - 1
    chosen_groups = [0] * count
    group_range = list(range(count))

    def search(uncov, avail, slots=slots, conflict=conflict,
               atom_bits=atom_bits, group_lo=group_lo, group_hi=group_hi,
               chosen_groups=chosen_groups, solutions=solutions, acc=acc,
               group_range=group_range, count=count, cap=SOLUTION_CAP):
        mark = len(acc)
        try:
            while True:
                if uncov == 0:
                    pools = []
                    for gi in group_range:
                        if chosen_groups[gi]:
                            continue
                        pool = [(slots[si][1], slots[si][3])
                                for si in range(group_lo[gi], group_hi[gi])
                                if slots[si][2] == 0 and (avail >> si) & 1]
                        if not pool:
                            return
                        pools.append((gi, pool))

                    def assign(i, base, pools=pools, solutions=solutions,
                               cap=cap):
                        if len(solutions) >= cap:
                            return
                        if i == len(pools):
                            solutions.append(base)
                            return
                        gi, pool = pools[i]
                        for name, value in pool:
                            assign(i + 1, base + [(gi, name, value)])
                    assign(0, list(acc))
                    return
                best_slots = 0
                best_count = None
                rest = uncov
                seen = 0
                while rest:
                    low = rest & -rest
                    cur = avail & atom_bits[low.bit_length() - 1]
                    c = cur.bit_count()
                    if c == 0:
                        return
                    if best_count is None or c < best_count:
                        best_count = c
                        best_slots = cur
                        if c == 1:
                            break
                    seen += 1
                    if seen >= PROBE:
                        break
                    rest ^= low
                if best_count == 1:
                    # forced: apply it here rather than recursing
                    si = best_slots.bit_length() - 1
                    gi, name, mask, value = slots[si]
                    chosen_groups[gi] += 1
                    acc.append((gi, name, value))
                    uncov &= ~mask
                    avail &= ~conflict[si]
                    continue
                rest = best_slots
                while rest:
                    low = rest & -rest
                    si = low.bit_length() - 1
                    gi, name, mask, value = slots[si]
                    chosen_groups[gi] += 1
                    acc.append((gi, name, value))
                    search(uncov & ~mask, avail & ~conflict[si])
                    acc.pop()
                    chosen_groups[gi] -= 1
                    if len(solutions) >= cap:
                        return
                    rest ^= low
                return
        finally:
            # undo the choices this entry applied by itself
            while len(acc) > mark:
                gi, _name, _value = acc.pop()
                chosen_groups[gi] -= 1

    search(full, all_avail)
    return [dict((groups[gi], (name, value)) for gi, name, value in sol)
            for sol in solutions]


def derive_east(data_dir):
    group_index, group_rows = read_table(data_dir, 'allocation_groups.csv',
                                         ('board', 'component', 'group', 'atoms'))
    atoms_of = {}
    components = {}
    board_of = {}
    for row in group_rows:
        board = row[group_index['board']]
        component = row[group_index['component']]
        group = row[group_index['group']]
        atoms = cell_set(row[group_index['atoms']],
                         'allocation_groups.csv atoms')
        key = (board, component)
        if group in components.setdefault(key, {}):
            raise ContractError('allocation_groups.csv: group %r repeats in '
                                'component %r of board %r'
                                % (group, component, board))
        components[key][group] = atoms
        atoms_of[(board, component, group)] = atoms
        if (board, group) in board_of:
            raise ContractError('allocation_groups.csv: group %r is not unique '
                                'within board %r' % (group, board))
        board_of[(board, group)] = component

    candidate_index, candidate_rows = read_table(
        data_dir, 'allocation_candidates.csv',
        ('board', 'component', 'group', 'candidate', 'atoms', 'value'))
    candidates = {}
    known = set(atoms_of)
    board_col = candidate_index['board']
    component_col = candidate_index['component']
    group_col = candidate_index['group']
    name_col = candidate_index['candidate']
    atoms_col = candidate_index['atoms']
    value_col = candidate_index['value']
    for row in candidate_rows:
        board = row[board_col]
        component = row[component_col]
        group = row[group_col]
        key = (board, component, group)
        if key not in known:
            continue
        candidates.setdefault(key, []).append(
            (row[name_col], cell_set(row[atoms_col],
                                     'allocation_candidates.csv atoms'),
             cell_int(row[value_col], 'allocation_candidates.csv value')))

    chosen = {}
    for key in sorted(components):
        board, component = key
        groups = sorted(components[key])
        atoms_by_group = dict((group, atoms_of[(board, component, group)])
                               for group in groups)
        lists = dict((group, candidates.get((board, component, group), ()))
                     for group in groups)
        assignments = solve_component(groups, atoms_by_group, lists)
        if not assignments:
            raise ContractError('allocation: component %r of board %r admits no '
                                'assignment' % (component, board))
        if len(assignments) > 1:
            raise ContractError('allocation: component %r of board %r admits '
                                'multiple assignments' % (component, board))
        for group, (_name, value) in assignments[0].items():
            chosen[(board, group)] = value

    request_index, request_rows = read_table(
        data_dir, 'allocation_requests.csv',
        ('request', 'board', 'group', 'account', 'quantity'))
    requests = []
    seen = set()
    for row in request_rows:
        where = 'allocation_requests.csv'
        identifier = cell_int(row[request_index['request']], where + ' request')
        if identifier in seen:
            raise ContractError('%s: duplicate request identifier %d'
                                % (where, identifier))
        seen.add(identifier)
        board = row[request_index['board']]
        group = row[request_index['group']]
        account = row[request_index['account']]
        quantity = cell_int(row[request_index['quantity']], where + ' quantity')
        key = (board, group)
        if key not in chosen:
            raise ContractError('%s: board %r has no group %r'
                                % (where, board, group))
        requests.append((identifier, account, quantity * chosen[key]))
    requests.sort(key=lambda item: item[0])
    credits = [{'request': identifier, 'account': account, 'credit': credit}
               for identifier, account, credit in requests]
    total = 0
    accounts = {}
    weighted = 0
    for identifier, account, credit in requests:
        total += credit
        accounts[account] = accounts.get(account, 0) + credit
        weighted += identifier * credit
    return {
        'in_scope': bool(requests),
        'credits': credits,
        'total': total,
        'accounts': accounts,
        'weighted_credit': weighted,
    }


# --------------------------------------------------------------------------
# replay lane: cycles (South)
# --------------------------------------------------------------------------

def fib_pair(n, modulus):
    """Return (F(n) mod modulus, F(n+1) mod modulus)."""
    a, b = 0, 1
    if n == 0:
        return a, b
    for digit in bin(n)[2:]:
        c = a * ((2 * b - a) % modulus) % modulus
        d = (a * a + b * b) % modulus
        if digit == '1':
            a, b = d, (c + d) % modulus
        else:
            a, b = c, d
    return a, b


def settle_large(x, y, rounds, modulus):
    """Settle a large stream: (u,v) -> (v, u*v) with u = x+1, v = y+1.

    After k rounds u is u^F(k-1) v^F(k) and v is u^F(k) v^F(k+1), so the
    exponents can be reduced modulo the order of the multiplicative group.
    """
    if rounds == 0:
        return x % modulus, y % modulus
    group_order = modulus - 1
    fib_prev, fib = fib_pair(rounds - 1, group_order)
    _fib, fib_next = fib_pair(rounds, group_order)
    u = (x + 1) % modulus
    v = (y + 1) % modulus
    # F(k) = 0 only for k = 0, so a positive exponent that reduces to zero
    # must still be treated as positive: 0^positive is 0, not 1.
    first = group_power(u, (fib_prev, rounds == 1), modulus) * \
        group_power(v, (fib, False), modulus) % modulus
    second = group_power(u, (fib, False), modulus) * \
        group_power(v, (fib_next, False), modulus) % modulus
    return (first - 1) % modulus, (second - 1) % modulus


def group_power(base, exponent, modulus):
    """base ** exponent in the multiplicative group, given (value, is_zero)."""
    value, is_zero = exponent
    if is_zero:
        return 1 % modulus
    if value == 0:
        return 0 if base == 0 else 1 % modulus
    return pow(base, value, modulus)


def settle_generic(x, y, a, b, c, rounds, modulus):
    start = (x % modulus, y % modulus)
    if rounds == 0:
        return start
    sequence = [start]
    seen = {start: 0}
    current = start
    steps = 0
    while steps < rounds and steps < ORBIT_BUDGET:
        first, second = current
        nxt = (second,
               (a * first + b * second + c + first * second) % modulus)
        steps += 1
        previous = seen.get(nxt)
        if previous is not None:
            cycle = steps - previous
            target = previous + (rounds - previous) % cycle
            return sequence[target]
        seen[nxt] = steps
        sequence.append(nxt)
        current = nxt
    if steps >= rounds:
        return current
    raise ContractError('cycles.csv: stream orbit exceeds the supported budget')


def derive_south(data_dir, policy):
    stream_index, stream_rows = read_table(
        data_dir, 'cycles.csv',
        ('stream', 'x', 'y', 'modulus', 'a', 'b', 'c', 'rounds', 'quantity'))
    where = 'cycles.csv'
    streams = []
    seen = set()
    for row in stream_rows:
        name = row[stream_index['stream']]
        if name in seen:
            raise ContractError('%s: duplicate stream %r' % (where, name))
        seen.add(name)
        x = cell_int(row[stream_index['x']], where + ' x')
        y = cell_int(row[stream_index['y']], where + ' y')
        modulus = cell_int(row[stream_index['modulus']], where + ' modulus')
        a = cell_int(row[stream_index['a']], where + ' a')
        b = cell_int(row[stream_index['b']], where + ' b')
        c = cell_int(row[stream_index['c']], where + ' c')
        rounds = cell_int(row[stream_index['rounds']], where + ' rounds')
        quantity = cell_int(row[stream_index['quantity']], where + ' quantity')
        if modulus <= 0:
            raise ContractError('%s: modulus must be positive' % where)
        if rounds < 0:
            raise ContractError('%s: rounds must be nonnegative' % where)
        if not 0 <= x < modulus or not 0 <= y < modulus:
            raise ContractError('%s: stream %r has an initial pair outside '
                                'zero through modulus minus one'
                                % (where, name))
        if modulus > SMALL_MODULUS_LIMIT and modulus != LARGE_MODULUS:
            raise ContractError('%s: stream %r is neither a small stream nor a '
                                'large stream' % (where, name))
        if modulus == LARGE_MODULUS:
            if (a, b, c) != (1, 1, 0):
                raise ContractError('%s: large stream %r must have a=1, b=1, '
                                    'c=0' % (where, name))
            settled = settle_large(x, y, rounds, modulus)
        else:
            settled = settle_generic(x, y, a, b, c, rounds, modulus)
        streams.append((name, settled[0], settled[1],
                        quantity * (settled[0] + modulus * settled[1])))
    streams.sort(key=lambda item: item[0])
    threshold = policy['eligibility_threshold']
    rows = [{'stream': name, 'x': x, 'y': y, 'units': units}
            for name, x, y, units in streams]
    total = sum(item[3] for item in streams)
    settlement = 0
    eligible = []
    for position, (name, _x, _y, units) in enumerate(streams):
        settlement += units * (position + 1)
        if units >= threshold:
            eligible.append(name)
    return {
        'in_scope': bool(streams),
        'streams': rows,
        'total': total,
        'settlement': settlement,
        'eligible': eligible,
    }


# --------------------------------------------------------------------------
# amendment lane (West): forest of records with path folds
# --------------------------------------------------------------------------

class AffineForest:
    """Link-cut forest carrying one affine map per record.

    Every preferred path is held in a splay tree ordered by depth; each node
    keeps both the forward and the backward composition of its splay subtree,
    so a lazy reversal stays exact for a non-commutative aggregate.
    """

    def __init__(self, count, modulus, maps):
        self.modulus = modulus
        self.left = [-1] * count
        self.right = [-1] * count
        self.parent = [-1] * count
        self.flip = [0] * count
        self.first = [a % modulus for a, _b in maps]
        self.second = [b % modulus for _a, b in maps]
        self.fwd_a = [a % modulus for a, _b in maps]
        self.fwd_b = [b % modulus for _a, b in maps]
        self.bwd_a = [a % modulus for a, _b in maps]
        self.bwd_b = [b % modulus for _a, b in maps]

    def push_up(self, x):
        mod = self.modulus
        va = self.first[x]
        vb = self.second[x]
        left = self.left[x]
        right = self.right[x]
        if left >= 0:
            la = self.fwd_a[left]
            lb = self.fwd_b[left]
            ta = va * la % mod
            tb = (va * lb + vb) % mod
        else:
            ta = va
            tb = vb
        if right >= 0:
            ra = self.fwd_a[right]
            rb = self.fwd_b[right]
            self.fwd_a[x] = ra * ta % mod
            self.fwd_b[x] = (ra * tb + rb) % mod
        else:
            self.fwd_a[x] = ta
            self.fwd_b[x] = tb
        if right >= 0:
            ra = self.bwd_a[right]
            rb = self.bwd_b[right]
            ta = va * ra % mod
            tb = (va * rb + vb) % mod
        else:
            ta = va
            tb = vb
        if left >= 0:
            la = self.bwd_a[left]
            lb = self.bwd_b[left]
            self.bwd_a[x] = la * ta % mod
            self.bwd_b[x] = (la * tb + lb) % mod
        else:
            self.bwd_a[x] = ta
            self.bwd_b[x] = tb

    def push_down(self, x):
        if self.flip[x]:
            left = self.left[x]
            right = self.right[x]
            if left >= 0:
                self.reverse(left)
            if right >= 0:
                self.reverse(right)
            self.flip[x] = 0

    def reverse(self, x):
        self.left[x], self.right[x] = self.right[x], self.left[x]
        self.fwd_a[x], self.bwd_a[x] = self.bwd_a[x], self.fwd_a[x]
        self.fwd_b[x], self.bwd_b[x] = self.bwd_b[x], self.fwd_b[x]
        self.flip[x] ^= 1

    def is_root(self, x):
        parent = self.parent[x]
        if parent < 0:
            return True
        return self.left[parent] != x and self.right[parent] != x

    def rotate(self, x):
        left = self.left
        right = self.right
        parent = self.parent
        y = parent[x]
        z = parent[y]
        if left[y] == x:
            child = right[x]
            left[y] = child
            if child >= 0:
                parent[child] = y
            right[x] = y
        else:
            child = left[x]
            right[y] = child
            if child >= 0:
                parent[child] = y
            left[x] = y
        parent[y] = x
        parent[x] = z
        if z >= 0:
            if left[z] == y:
                left[z] = x
            elif right[z] == y:
                right[z] = x
        self.push_up(y)
        self.push_up(x)

    def splay(self, x):
        stack = []
        node = x
        while not self.is_root(node):
            stack.append(node)
            node = self.parent[node]
        self.push_down(node)
        for item in reversed(stack):
            self.push_down(item)
        left = self.left
        right = self.right
        parent = self.parent
        while True:
            y = parent[x]
            if y < 0:
                break
            if left[y] != x and right[y] != x:
                break
            z = parent[y]
            if z >= 0 and (left[z] == y or right[z] == y):
                if (left[z] == y) == (left[y] == x):
                    self.rotate(y)
                else:
                    self.rotate(x)
            self.rotate(x)

    def access(self, x):
        right = self.right
        parent = self.parent
        last = -1
        while x >= 0:
            self.splay(x)
            right[x] = last
            self.push_up(x)
            last = x
            x = parent[x]

    def make_root(self, x):
        self.access(x)
        self.splay(x)
        self.reverse(x)

    def link(self, u, v):
        self.make_root(u)
        self.parent[u] = v

    def try_cut(self, u, v):
        """Remove the undirected edge u--v when it exists."""
        if u == v:
            return False
        self.make_root(u)
        self.access(v)
        self.splay(v)
        if self.left[v] != u:
            return False
        if self.left[u] >= 0 or self.right[u] >= 0:
            return False
        self.left[v] = -1
        self.parent[u] = -1
        self.push_up(v)
        return True

    def find_root(self, x):
        self.access(x)
        self.splay(x)
        left = self.left
        while True:
            self.push_down(x)
            child = left[x]
            if child < 0:
                break
            x = child
        self.splay(x)
        return x

    def set_map(self, x, a, b):
        self.splay(x)
        self.first[x] = a % self.modulus
        self.second[x] = b % self.modulus
        self.push_up(x)

    def path_composite(self, u, v):
        """Composite of the u to v path in visiting order, else None."""
        self.make_root(u)
        self.access(v)
        self.splay(v)
        left = self.left
        node = v
        while True:
            self.push_down(node)
            child = left[node]
            if child < 0:
                break
            node = child
        self.splay(node)
        if node != u:
            return None
        return (self.fwd_a[node], self.fwd_b[node])


def derive_west(data_dir, replay):
    modulus = replay['modulus']
    initial = replay['initial'] % modulus
    record_index, record_rows = read_table(data_dir, 'fold_records.csv',
                                          ('record', 'position', 'a', 'b'))
    where = 'fold_records.csv'
    positions = {}
    node_of = {}
    records = []
    seen = set()
    for row in record_rows:
        name = row[record_index['record']]
        position = cell_int(row[record_index['position']], where + ' position')
        if position in seen:
            raise ContractError('%s: duplicate position %d' % (where, position))
        seen.add(position)
        a = cell_int(row[record_index['a']], where + ' a')
        b = cell_int(row[record_index['b']], where + ' b')
        positions[name] = position
        records.append((position, name, a, b))
    records.sort()
    for node, (_position, name, _a, _b) in enumerate(records):
        node_of[name] = node

    count = len(records)
    forest = None
    if count:
        forest = AffineForest(count, modulus,
                              [(a, b) for _p, _n, a, b in records])
        for node in range(count - 1):
            forest.link(node, node + 1)

    amendment_index, amendment_rows = read_table(
        data_dir, 'fold_corrections.csv',
        ('amendment', 'arrival', 'record', 'revision', 'a', 'b', 'action',
         'cut_left', 'cut_right', 'link_left', 'link_right', 'query_start',
         'query_end'))
    where = 'fold_corrections.csv'
    amendments = []
    seen = set()
    for row in amendment_rows:
        identifier = cell_int(row[amendment_index['amendment']],
                              where + ' amendment')
        if identifier in seen:
            raise ContractError('%s: duplicate amendment %d' % (where, identifier))
        seen.add(identifier)
        amendments.append((
            cell_int(row[amendment_index['arrival']], where + ' arrival'),
            identifier,
            row[amendment_index['record']],
            cell_int(row[amendment_index['revision']], where + ' revision'),
            cell_int(row[amendment_index['a']], where + ' a'),
            cell_int(row[amendment_index['b']], where + ' b'),
            row[amendment_index['action']],
            row[amendment_index['cut_left']],
            row[amendment_index['cut_right']],
            row[amendment_index['link_left']],
            row[amendment_index['link_right']],
            row[amendment_index['query_start']],
            row[amendment_index['query_end']],
        ))
    amendments.sort(key=lambda item: (item[0], item[1]))

    accepted = [-1] * count
    previous = initial
    if count:
        composite = forest.path_composite(0, count - 1)
        if composite is not None:
            previous = affine_apply(composite, initial, modulus)
    rows = []
    weighted = 0
    applied = 0
    orphan = 0
    superseded = 0
    for (_arrival, identifier, record, revision, a, b, action,
         cut_left, cut_right, link_left, link_right, query_start, query_end
         ) in amendments:
        node = node_of.get(record)
        if node is None:
            status = 'orphan'
            state = previous
            orphan += 1
        elif revision <= accepted[node]:
            status = 'superseded'
            state = previous
            superseded += 1
        else:
            status = 'applied'
            applied += 1
            accepted[node] = revision
            forest.set_map(node, a, b)
            if action == 'swap_edge':
                first = node_of.get(cut_left)
                second = node_of.get(cut_right)
                third = node_of.get(link_left)
                fourth = node_of.get(link_right)
                if (first is not None and second is not None
                        and third is not None and fourth is not None
                        and forest.try_cut(first, second)):
                    if forest.find_root(third) != forest.find_root(fourth):
                        forest.link(third, fourth)
                    else:
                        forest.link(first, second)
            elif action != 'keep':
                raise ContractError('%s: amendment %d has unknown action %r'
                                    % (where, identifier, action))
            start = node_of.get(query_start)
            end = node_of.get(query_end)
            state = initial
            if start is not None and end is not None:
                composite = forest.path_composite(start, end)
                if composite is not None:
                    state = affine_apply(composite, initial, modulus)
            previous = state
        weighted += identifier * state
        rows.append({'amendment': identifier, 'status': status, 'state': state})
    return {
        'in_scope': bool(amendments),
        'state': previous,
        'weighted_states': weighted,
        'revised': applied,
        'amendments': rows,
        'orphan_count': orphan,
        'superseded_count': superseded,
        'applied_count': applied,
    }


# --------------------------------------------------------------------------
# reports
# --------------------------------------------------------------------------

def build_reports(data_dir):
    policy = load_json(data_dir, 'policy.json',
                       (('report_id', str), ('clock_multiplier', int),
                        ('clock_modulus', int), ('eligibility_threshold', int)))
    replay = load_json(data_dir, 'replay.json',
                       (('initial', int), ('modulus', int)))
    clock = load_clock(data_dir)
    north = derive_north(data_dir, policy, clock)
    east = derive_east(data_dir)
    south = derive_south(data_dir, policy)
    west = derive_west(data_dir, replay)

    sources, _numerator, epochs, offsets = clock
    last = max(range(len(epochs)),
               key=lambda i: (epochs[i][1], epochs[i][2], i))
    final_offsets = dict((source, offsets[epochs[last][0]][source])
                         for source in sources)

    parts = {
        'North': north['final_state'],
        'East': east['total'],
        'South': south['total'],
        'West': west['state'],
    }
    total = sum(parts.values())
    operands = (sum(north['identity_totals'].values())
                + sum(east['accounts'].values())
                + south['total'] + west['state'])

    reports = {}
    reports['region_North.json'] = {
        'name': 'North',
        'in_scope': north['in_scope'],
        'events': north['events'],
        'final_state': north['final_state'],
        'units': north['units'],
    }
    reports['policy_audit.json'] = {
        'final_offsets': final_offsets,
        'identity_totals': north['identity_totals'],
        'weighted_state': north['weighted_state'],
    }
    reports['region_East.json'] = {
        'name': 'East',
        'in_scope': east['in_scope'],
        'credits': east['credits'],
        'total': east['total'],
    }
    reports['segment_commercial.json'] = {
        'name': 'commercial',
        'in_scope': east['in_scope'],
        'accounts': east['accounts'],
        'weighted_credit': east['weighted_credit'],
    }
    reports['region_South.json'] = {
        'name': 'South',
        'in_scope': south['in_scope'],
        'streams': south['streams'],
        'total': south['total'],
    }
    reports['segment_public.json'] = {
        'name': 'public',
        'in_scope': south['in_scope'],
        'settlement': south['settlement'],
        'eligible': south['eligible'],
    }
    reports['region_West.json'] = {
        'name': 'West',
        'in_scope': west['in_scope'],
        'state': west['state'],
        'weighted_states': west['weighted_states'],
        'revised': west['revised'],
    }
    reports['data_quality.json'] = {
        'amendments': west['amendments'],
        'orphan_count': west['orphan_count'],
        'superseded_count': west['superseded_count'],
        'applied_count': west['applied_count'],
    }
    reports['summary.json'] = {
        'report_id': policy['report_id'],
        'parts': parts,
        'total': total,
        'residual': total - operands,
    }
    return reports


def encode_report(report):
    text = json.dumps(report, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'))
    return (text + '\n').encode('utf-8')


def write_reports(out_dir, reports):
    try:
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)
    except OSError as exc:
        raise ContractError('cannot create %s: %s' % (out_dir, exc))
    for filename in REPORT_FILES:
        path = os.path.join(out_dir, filename)
        try:
            if os.path.islink(path):
                os.unlink(path)
            with open(path, 'wb') as handle:
                handle.write(encode_report(reports[filename]))
        except OSError as exc:
            raise ContractError('cannot write %s: %s' % (path, exc))


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: derive_report.py DATA_DIR OUT_DIR\n')
        return 2
    data_dir, out_dir = argv[1], argv[2]
    if not os.path.isdir(data_dir):
        sys.stderr.write('derive_report: %s is not a directory\n' % data_dir)
        return 2
    try:
        reports = build_reports(data_dir)
        write_reports(out_dir, reports)
    except ContractError as exc:
        sys.stderr.write('derive_report: %s\n' % exc)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))

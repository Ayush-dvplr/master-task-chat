"""Fast, exact rating aggregator for the usage rating desk's metered-cloud extracts.

``aggregate(events_path, rules_path)`` rates one scenario workload with the rules file
and the files that rules file names, and returns the result object the extract's
documents define.  The module also runs as a command, printing that object on
standard output as one line.

Only the Python standard library is used.  The module creates, changes and deletes
nothing, carries no clock and no randomness, and its output depends on nothing but
the workload, the rules file and the files the rules file names.
"""

import csv
import json
import os
import sys

# Row layout: the cells of a rated row, by index.
TS, OID, ID, BOOKED, KIND, AMOUNT, UNITS, LATENCY, FLAG, AMENDED, WRITTEN = range(11)
REGION, BASE, CARRIED, PENALTY, FINAL, LIVE = range(11, 17)

VOID, REVIVE = 'void', 'revive'


# ---------------------------------------------------------------- file helpers


def _read_csv(path):
    with open(path, 'r', encoding='utf-8-sig', newline='') as handle:
        return list(csv.reader(handle))


def _read_json(path):
    with open(path, 'r', encoding='utf-8') as handle:
        return json.load(handle)


def _read_jsonl(path):
    out = []
    with open(path, 'r', encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


# ----------------------------------------------------------- standing policies

# A standing policy is (count, total, comparison, from_largest):
#   count  'O' judges every ordinary row of the account, 'L' only its live ones.
#   total  'U' the unwaived total, 'C' the carried total, 'S' the unwaived total
#          plus the waivable penalty when the account's sponsor is in the set and
#          the unwaived total otherwise.
#   comparison  '>=' passes at the floor, '>' only strictly above it.
#   from_largest  reach the set from every judged account instead of from none.
# The policy the legacy engine used is the first entry; the rest are only a
# fallback for extracts whose standing journal says otherwise.

STANDING_RULE = ('O', 'S', '>=', False)
STANDING_CANDIDATES = (
    STANDING_RULE,
    ('O', 'S', '>=', True),
    ('O', 'S', '>', False),
    ('O', 'S', '>', True),
    ('O', 'U', '>=', False),
    ('O', 'U', '>', False),
    ('O', 'C', '>=', False),
    ('O', 'C', '>', False),
    ('L', 'S', '>=', False),
    ('L', 'S', '>=', True),
    ('L', 'S', '>', False),
    ('L', 'S', '>', True),
    ('L', 'U', '>=', False),
    ('L', 'U', '>', False),
    ('L', 'C', '>=', False),
    ('L', 'C', '>', False),
)


def _standing_set(per, judged, sponsors, floor, rule):
    """The accounts a standing policy passes.

    ``per[account]`` is (ordinary rows, live ordinary rows, unwaived total, waivable
    penalty, carried total); ``sponsors[account]`` is the account's sponsor or None.
    """
    count_key, total_key, comparison, from_largest = rule
    at_least = comparison == '>='
    if total_key != 'S':
        out = set()
        for account in judged:
            item = per[account]
            n = item[0 if count_key == 'O' else 1]
            if n <= 0:
                continue
            total = item[2] if total_key == 'U' else item[4]
            if (total >= floor * n) if at_least else (total > floor * n):
                out.add(account)
        return out
    current = set(judged) if from_largest else set()
    while True:
        nxt = set()
        for account in judged:
            item = per[account]
            n = item[0 if count_key == 'O' else 1]
            if n <= 0:
                continue
            sponsor = sponsors[account]
            if sponsor is not None and sponsor in current:
                total = item[2] + item[3]
            else:
                total = item[2]
            if (total >= floor * n) if at_least else (total > floor * n):
                nxt.add(account)
        if nxt == current:
            return current
        current = nxt


# ----------------------------------------------------------------- withdrawal


def _void_choice(live, kind, table, weights):
    """The live row a void row of ``kind`` withdraws, or None when it may withdraw none.

    The rows of the void's own kind rank ahead of the rows of every other kind; the
    own-kind rows are taken by metered charge, larger first, and then by position,
    later first, and the rows of other kinds by metered charge, smaller first, and
    then by position, earlier first.
    """
    own = []
    other = []
    for row in live:
        row_kind = row[KIND]
        if row_kind == kind or table.get((kind, row_kind)):
            if row_kind == kind:
                own.append(row)
            else:
                other.append(row)
    if own:
        best = own[0]
        best_key = (best[AMOUNT] * best[UNITS] * weights[best[KIND]], best[TS], best[OID])
        for row in own[1:]:
            key = (row[AMOUNT] * row[UNITS] * weights[row[KIND]], row[TS], row[OID])
            if key > best_key:
                best = row
                best_key = key
        return best
    if other:
        best = other[0]
        best_key = (best[AMOUNT] * best[UNITS] * weights[best[KIND]], best[TS], best[OID])
        for row in other[1:]:
            key = (row[AMOUNT] * row[UNITS] * weights[row[KIND]], row[TS], row[OID])
            if key < best_key:
                best = row
                best_key = key
        return best
    return None


def _journal_void_choice(live, kind, table, weights):
    """The same pick for the plain lists of a closing journal."""
    own = []
    other = []
    for row in live:
        row_kind = row[2]
        if row_kind == kind or table.get((kind, row_kind)):
            if row_kind == kind:
                own.append(row)
            else:
                other.append(row)
    if own:
        best = own[0]
        best_key = (best[3] * best[4] * weights[best[2]], best[0], best[1])
        for row in own[1:]:
            key = (row[3] * row[4] * weights[row[2]], row[0], row[1])
            if key > best_key:
                best = row
                best_key = key
        return best
    if other:
        best = other[0]
        best_key = (best[3] * best[4] * weights[best[2]], best[0], best[1])
        for row in other[1:]:
            key = (row[3] * row[4] * weights[row[2]], row[0], row[1])
            if key < best_key:
                best = row
                best_key = key
        return best
    return None


# ------------------------------------------------------- rules of one extract


class Rules(object):
    """The rules file, the files it names, and what those files settle."""

    def __init__(self, rules_path):
        self.path = rules_path
        self.base_dir = os.path.dirname(os.path.abspath(rules_path))
        rules = _read_json(rules_path)
        self.rules = rules
        self.label = rules['label']
        self.kinds = list(rules['kinds'])
        self.region_offsets = rules['region_offsets']
        self.flag_penalties = rules['flag_penalties']
        self.carry_modulus = rules['carry_modulus']
        self.latency_quantum = rules['latency_quantum']
        self.premium_floor = rules['premium_floor']
        self.top_n = rules['top_n']
        self.weights = self._kind_weights()
        self._identity()
        self.table = self._cancellation_table()
        self.standing_rule = self._standing_rule()
        self.amendments = self._amendments()

    def file(self, key):
        return os.path.join(self.base_dir, self.rules[key])

    # -- kind weights: the rate card lines and the published figures settle them

    def _kind_weights(self):
        kinds = self.kinds
        count = len(kinds)
        index = dict((kind, i) for i, kind in enumerate(kinds))
        rows = {}
        for line in _read_csv(self.file('rate_card_file'))[1:]:
            batch, kind, amount, units = line
            if kind not in index:
                continue
            terms = rows.setdefault(batch, [0] * count)
            terms[index[kind]] += int(amount) * int(units)
        figures = _read_json(self.file('rate_figures_file'))['figures']
        equations = []
        for batch, figure in figures.items():
            terms = rows.get(batch)
            if terms is not None and any(terms):
                equations.append(terms + [figure])
        if not equations:
            raise ValueError('the rate card and the figures settle no kind weight')
        width = count
        matrix = [list(line) for line in equations]
        pivots = []
        rank = 0
        for column in range(width):
            pivot = None
            for i in range(rank, len(matrix)):
                if matrix[i][column]:
                    pivot = i
                    break
            if pivot is None:
                continue
            matrix[rank], matrix[pivot] = matrix[pivot], matrix[rank]
            lead = matrix[rank][column]
            for i in range(len(matrix)):
                if i == rank:
                    continue
                other = matrix[i]
                if other[column]:
                    scale = other[column]
                    for j in range(len(other)):
                        other[j] = other[j] * lead - matrix[rank][j] * scale
            pivots.append(column)
            rank += 1
        if len(pivots) != count:
            raise ValueError('the rate card and the figures leave kind weights open')
        for i in range(rank, len(matrix)):
            for value in matrix[i]:
                if value:
                    raise ValueError('the rate card and the figures disagree')
        weights = {}
        for i, column in enumerate(pivots):
            lead = matrix[i][column]
            value = matrix[i][width]
            if lead < 0:
                lead = -lead
                value = -value
            if value % lead:
                raise ValueError('the kind weights are not whole numbers')
            weights[kinds[column]] = value // lead
        return weights

    # -- identity: governing records, merge resolution, sponsors

    def _identity(self):
        governing = {}
        for line in _read_csv(self.file('registry_file'))[1:]:
            account, home, sponsor, updated = line
            prev = governing.get(account)
            if prev is None or updated >= prev[0]:
                governing[account] = (updated, home, sponsor)
        self._governing = dict(
            (account, (value[1], value[2])) for account, value in governing.items()
        )
        export = _read_json(self.file('export_file'))
        self._export = dict(
            (record['account'], (record['home_region'], record['sponsor']))
            for record in export.get('accounts', [])
        )
        merges = {}
        for line in _read_csv(self.file('merges_file'))[1:]:
            account, merged_into, effective = line
            merges.setdefault(account, []).append((int(effective), merged_into))
        for records in merges.values():
            records.sort()
        self._merges = merges
        self._resolved = {}
        self._sponsor_of = {}
        self._regions = {}
        self._final_stamp = 0
        for records in merges.values():
            for effective, _ in records:
                if effective >= self._final_stamp:
                    self._final_stamp = effective + 1

    def governing(self, account):
        record = self._governing.get(account)
        if record is None:
            record = self._export.get(account)
        return record

    def is_registered(self, account):
        return self.governing(account) is not None

    def billing_region(self, account):
        region = self._regions.get(account)
        if region is not None:
            return region
        record = self.governing(account)
        region = None if record is None else record[0]
        self._regions[account] = region
        return region

    def resolve(self, account, ts):
        """The account a row written on ``account`` is booked to at stamp ``ts``."""
        key = (account, ts)
        cached = self._resolved.get(key)
        if cached is not None:
            return cached
        merges = self._merges
        current = account
        seen = None
        while True:
            records = merges.get(current)
            target = None
            if records:
                for effective, merged_into in reversed(records):
                    if ts > effective:
                        target = merged_into
                        break
            if not target:
                result = current
                break
            if seen is None:
                seen = set([current])
            elif current in seen:
                result = current
                break
            else:
                seen.add(current)
            current = target
        self._resolved[key] = result
        return result

    def sponsor(self, account):
        cached = self._sponsor_of.get(account)
        if cached is not None:
            return cached[0]
        record = self.governing(account)
        sponsor = None
        if record is not None and record[1]:
            sponsor = self.resolve(record[1], self._final_stamp)
        self._sponsor_of[account] = (sponsor,)
        return sponsor

    # -- cancellation table: settled by the legacy engine's withdrawal journal

    def _cancellation_table(self):
        """Recover the extract's cancellation table from the withdrawal journal.

        For every account the journal states which rows ended live or withdrawn and
        which control rows withdrew, restored or did nothing.  Every withdrawal
        history of an account that agrees with those states settles some pairs of
        kinds: a void that withdrew a row settles that pair, and a void that withdrew
        nothing settles that it may withdraw none of the kinds that were live then.
        A pair every history needs is a fact; the facts of all accounts together
        settle the table.
        """
        weights = self.weights
        kinds = self.kinds
        entries = {}
        for line in _read_csv(self.file('withdrawals_journal_file'))[1:]:
            account = line[1]
            entries.setdefault(account, []).append(
                [int(line[2]), int(line[3][1:]), line[4], int(line[5]), int(line[6]),
                 line[7], line[8]]
            )
        for records in entries.values():
            records.sort()

        settled = {}
        for a in kinds:
            for b in kinds:
                settled[(a, b)] = True if a == b else None

        def choice_facts(kind, live, chosen):
            """The pairs a void of ``kind`` withdrawing ``chosen`` settles."""
            chosen_kind = chosen[2]
            chosen_key = (chosen[3] * chosen[4] * weights[chosen_kind], chosen[0], chosen[1])
            facts = {}
            if chosen_kind == kind:
                # the void's own kind is always withdrawable, so its rows rank first
                facts[(kind, chosen_kind)] = True
                for row in live:
                    if row[2] == kind:
                        key = (row[3] * row[4] * weights[row[2]], row[0], row[1])
                        if key > chosen_key:
                            pair = (kind, kind)
                            if facts.get(pair) is True:
                                return None
                            facts[pair] = False
                if facts.get((kind, kind)) is False:
                    return None
            else:
                # no live row of the void's own kind may be withdrawable
                for row in live:
                    if row[2] == kind:
                        pair = (kind, kind)
                        if facts.get(pair) is True:
                            return None
                        facts[pair] = False
                if facts.get((kind, kind)) is True:
                    return None
                pair = (kind, chosen_kind)
                if facts.get(pair) is False:
                    return None
                facts[pair] = True
                for row in live:
                    row_kind = row[2]
                    if row_kind != kind:
                        key = (row[3] * row[4] * weights[row_kind], row[0], row[1])
                        if key < chosen_key:
                            pair = (kind, row_kind)
                            if facts.get(pair) is True:
                                return None
                            facts[pair] = False
            return facts

        def histories(records):
            """Every withdrawal history of one account that agrees with the journal."""
            out = []

            def walk(i, live, stack, facts):
                if len(out) > 50000:
                    return
                if i == len(records):
                    for record in records:
                        if record[5] in (VOID, REVIVE):
                            continue
                        state = 'withdrawn'
                        for row in live:
                            if row is record:
                                state = 'live'
                                break
                        if state != record[6]:
                            return
                    out.append(facts)
                    return
                record = records[i]
                flag = record[5]
                if flag == VOID:
                    kind = record[2]
                    if record[6] == 'orphan':
                        merged = dict(facts)
                        for row in live:
                            merged[(kind, row[2])] = False
                        walk(i + 1, live, stack, merged)
                        return
                    for chosen in live:
                        facts2 = choice_facts(kind, live, chosen)
                        if facts2 is None:
                            continue
                        bad = False
                        for pair, value in facts2.items():
                            known = settled[pair]
                            if known is not None and known != value:
                                bad = True
                                break
                            prev = facts.get(pair)
                            if prev is not None and prev != value:
                                bad = True
                                break
                        if bad:
                            continue
                        merged = dict(facts)
                        merged.update(facts2)
                        walk(i + 1, [row for row in live if row is not chosen],
                             stack + [chosen], merged)
                elif flag == REVIVE:
                    if record[6] == 'applied':
                        if stack:
                            walk(i + 1, live + [stack[-1]], stack[:-1], facts)
                    elif not stack:
                        walk(i + 1, live, stack, facts)
                else:
                    walk(i + 1, live + [record], stack, facts)

            walk(0, [], [], {})
            return out

        changed = True
        while changed:
            changed = False
            for account in sorted(entries):
                found = histories(entries[account])
                if not found:
                    raise ValueError('withdrawal journal disagrees at account %s' % account)
                common = found[0]
                for other in found[1:]:
                    for pair in list(common):
                        if other.get(pair) != common[pair]:
                            del common[pair]
                for pair, value in common.items():
                    if settled[pair] is None:
                        settled[pair] = value
                        changed = True
        for pair, value in settled.items():
            if value is None:
                settled[pair] = self._settle_pair(pair, settled, entries, weights)
        return settled

    def _settle_pair(self, pair, settled, entries, weights):
        """Settle a pair the withdrawal journal leaves open.

        A value is kept when it leaves the withdrawal journal consistent and the
        standing journal, whose period was rated with the same cancellation table,
        still fits the standing policy the legacy engine used.
        """
        for candidate in (True, False):
            settled[pair] = candidate
            if self._journal_agrees(entries, settled, weights) and self._standing_agrees():
                return candidate
        for candidate in (True, False):
            settled[pair] = candidate
            if self._journal_agrees(entries, settled, weights):
                return candidate
        settled[pair] = False
        return False

    @staticmethod
    def _journal_agrees(entries, table, weights):
        """True when a full replay of the journal reproduces every recorded state."""
        for account, records in entries.items():
            live = []
            stack = []
            for record in records:
                flag = record[5]
                if flag == VOID:
                    chosen = _journal_void_choice(live, record[2], table, weights)
                    if chosen is None:
                        if record[6] != 'orphan':
                            return False
                    else:
                        if record[6] != 'applied':
                            return False
                        live.remove(chosen)
                        stack.append(chosen)
                elif flag == REVIVE:
                    if stack:
                        if record[6] != 'applied':
                            return False
                        live.append(stack.pop())
                    elif record[6] != 'orphan':
                        return False
                else:
                    live.append(record)
            for record in records:
                if record[5] in (VOID, REVIVE):
                    continue
                state = 'withdrawn'
                for row in live:
                    if row is record:
                        state = 'live'
                        break
                if state != record[6]:
                    return False
        return True

    # -- standing policy: checked against the legacy engine's standing journal

    def _standing_rule(self):
        """Read the standing policy off the legacy engine's standing journal.

        The journal's period was rated with the extract's own kinds, weights and
        cancellation table, with a floor of 2000 and no carry between rows, so its
        accounts can be judged again and compared with the standing it records.
        """
        figures = self._standing_figures(self.table)
        rule = self._fitting_policy(figures)
        if rule is None:
            # the standing policy is the same in every extract, so a journal that
            # fits no policy is read as a record that no longer agrees with itself
            return STANDING_RULE
        return rule

    def _standing_agrees(self):
        """True when the standing journal still fits a standing policy."""
        try:
            return self._fitting_policy(self._standing_figures(self.table)) is not None
        except Exception:
            return False

    def _fitting_policy(self, figures):
        """The standing policy the standing journal fits, or None when none fits."""
        per, judged, sponsors, truth = figures
        for rule in STANDING_CANDIDATES:
            passed = _standing_set(per, judged, sponsors, 2000, rule)
            good = True
            for account in judged:
                if ('premium' if account in passed else 'standard') != truth[account]:
                    good = False
                    break
            if good:
                return rule
        return None

    def _standing_figures(self, table):
        """Judge every account of the standing journal again, under ``table``."""
        rows = _read_csv(self.file('standing_journal_file'))
        head = dict((name, i) for i, name in enumerate(rows[0]))
        accounts = {}
        for line in rows[1:]:
            accounts.setdefault(line[head['account']], []).append(
                [int(line[head['ts']]), int(line[head['row']][1:]), line[head['kind']],
                 int(line[head['amount']]), int(line[head['units']]), line[head['flag']],
                 int(line[head['latency_ms']]), line[head['region']],
                 line[head['sponsor']], line[head['standing']]]
            )
        for records in accounts.values():
            records.sort()
        weights = self.weights
        offsets = self.region_offsets
        penalties = self.flag_penalties
        quantum = self.latency_quantum
        per = {}
        sponsors = {}
        truth = {}
        for account, records in accounts.items():
            live = []
            stack = []
            for record in records:
                flag = record[5]
                if flag == VOID:
                    chosen = _journal_void_choice(live, record[2], table, weights)
                    if chosen is not None:
                        live.remove(chosen)
                        stack.append(chosen)
                elif flag == REVIVE:
                    if stack:
                        live.append(stack.pop())
                else:
                    live.append(record)
            ordinary = live_ordinary = unwaived = waivable = carried = 0
            for record in records:
                flag = record[5]
                if flag == VOID or flag == REVIVE:
                    continue
                ordinary += 1
                base = (record[3] * record[4] * weights[record[2]]
                        + offsets[record[7]] - record[6] // quantum)
                penalty = penalties.get(flag, 0)
                is_live = False
                for row in live:
                    if row is record:
                        is_live = True
                        break
                if is_live:
                    live_ordinary += 1
                    carried += base
                    waivable += penalty
                    unwaived += base - penalty
            per[account] = (ordinary, live_ordinary, unwaived, waivable, carried)
            sponsors[account] = records[0][8] or None
            truth[account] = records[0][9]
        return per, list(accounts), sponsors, truth

    # -- errata: the net state of the errata file

    def _amendments(self):
        lines = _read_jsonl(self.file('errata_file'))
        reverted = set()
        for entry in lines:
            if 'reverts' in entry:
                reverted.add(entry['reverts'])
        effective = {}
        for entry in lines:
            if 'reverts' in entry:
                continue
            erratum = entry['erratum']
            if erratum in reverted:
                continue
            number = int(erratum.split('-', 1)[1])
            key = (entry['booked_account'], int(entry['ts']), entry['field'])
            prev = effective.get(key)
            if prev is None or number < prev[0]:
                effective[key] = (number, entry['value'])
        rows = {}
        for (account, ts, field), (number, value) in effective.items():
            rows.setdefault((account, ts), []).append((field, value))
        return rows


# ------------------------------------------------------------------- the rating


def rate(events_path, rules):
    """Rate one workload: the result object and every figure the reports need."""
    weights = rules.weights
    table = rules.table
    amendments = rules.amendments
    resolve = rules.resolve
    registered = rules.is_registered
    region_of = rules.billing_region
    sponsor_of = rules.sponsor
    offsets = rules.region_offsets
    penalties = rules.flag_penalties
    quantum = rules.latency_quantum
    modulus = rules.carry_modulus

    with open(events_path, 'rb') as handle:
        text = handle.read().decode('utf-8-sig')
    lines = text.splitlines()
    reader = csv.reader(lines)
    header = next(reader)
    column = dict((name, i) for i, name in enumerate(header))
    latency_column = None
    for name, i in column.items():
        if name.startswith('latency_'):
            latency_column = i
            microseconds = name[8:] != 'ms'
    id_column = column['id']
    ts_column = column['ts']
    account_column = column['account']
    kind_column = column['kind']
    amount_column = column['amount']
    units_column = column['units']
    flag_column = column['flag']

    event_count = 0
    unregistered_rows = 0
    unpriced_rows = 0
    rows = []
    for cells in reader:
        if not cells:
            continue
        event_count += 1
        ts = int(cells[ts_column])
        account = cells[account_column].strip().upper()
        booked = resolve(account, ts)
        amount = cells[amount_column]
        units = int(cells[units_column])
        kind = cells[kind_column].strip().lower()
        flag = cells[flag_column].strip().lower()
        latency = int(cells[latency_column])
        if microseconds:
            latency = (latency + 500) // 1000
        amended = False
        change = amendments.get((booked, ts))
        if change is not None:
            amended = True
            for field, value in change:
                if field == 'amount':
                    amount = value
                elif field == 'units':
                    units = int(value)
                else:
                    flag = value.strip().lower()
        if not registered(booked):
            unregistered_rows += 1
            continue
        if amount.strip() == '':
            unpriced_rows += 1
            continue
        row = [ts, int(cells[id_column][1:]), cells[id_column], booked, kind,
               int(amount), units, latency, flag, amended, account]
        row.extend([None, 0, 0, 0, 0, True])
        rows.append(row)

    rows.sort(key=lambda row: (row[TS], row[OID]))
    processed = len(rows)

    # billing regions, base values, then the carry chains of the ordinary rows
    regions = {}
    carry = {}
    for row in rows:
        account = row[BOOKED]
        region = regions.get(account)
        if region is None:
            region = region_of(account)
            regions[account] = region
        row[REGION] = region
        flag = row[FLAG]
        if flag == VOID or flag == REVIVE:
            row[AMOUNT] = 0
            row[UNITS] = 0
        base = (row[AMOUNT] * row[UNITS] * weights[row[KIND]] + offsets[region]
                - row[LATENCY] // quantum)
        row[BASE] = base
        if flag == VOID or flag == REVIVE:
            row[CARRIED] = base
        else:
            carried = base + carry.get(region, 0)
            row[CARRIED] = carried
            carry[region] = carried % modulus
        row[PENALTY] = penalties.get(flag, 0)

    # withdrawals and restorations
    live = {}
    stacks = {}
    orphan_voids = 0
    orphan_revives = 0
    for row in rows:
        flag = row[FLAG]
        if flag == VOID:
            account = row[BOOKED]
            current = live.get(account)
            chosen = _void_choice(current, row[KIND], table, weights) if current else None
            if chosen is None:
                orphan_voids += 1
            else:
                current.remove(chosen)
                chosen[LIVE] = False
                stacks.setdefault(account, []).append(chosen)
        elif flag == REVIVE:
            account = row[BOOKED]
            stack = stacks.get(account)
            if stack:
                restored = stack.pop()
                restored[LIVE] = True
                current = live.get(account)
                if current is None:
                    live[account] = [restored]
                else:
                    current.append(restored)
            else:
                orphan_revives += 1
        else:
            account = row[BOOKED]
            current = live.get(account)
            if current is None:
                live[account] = [row]
            else:
                current.append(row)

    # the figures the standing policy judges: ordinary rows, live rows, U, W and C
    per = {}
    sponsors = {}
    judged = []
    for row in rows:
        flag = row[FLAG]
        if flag == VOID or flag == REVIVE:
            continue
        account = row[BOOKED]
        item = per.get(account)
        if item is None:
            item = [0, 0, 0, 0, 0]
            per[account] = item
            judged.append(account)
            sponsors[account] = sponsor_of(account)
        item[0] += 1
        if row[LIVE]:
            item[1] += 1
            carried = row[CARRIED]
            penalty = row[PENALTY]
            item[2] += carried - penalty
            item[3] += penalty
            item[4] += carried

    premium = _standing_set(per, judged, sponsors, rules.premium_floor,
                            rules.standing_rule)

    # final values, with the waivers premium standing grants
    waived_penalty = 0
    for row in rows:
        flag = row[FLAG]
        carried = row[CARRIED]
        if flag == VOID or flag == REVIVE:
            row[FINAL] = carried - row[PENALTY]
            continue
        sponsor = sponsors.get(row[BOOKED])
        if sponsor is not None and sponsor in premium:
            waived_penalty += row[PENALTY]
            row[FINAL] = carried
        else:
            row[FINAL] = carried - row[PENALTY]

    account_totals = {}
    region_totals = {}
    kind_totals = {}
    flag_counts = {}
    for account in judged:
        account_totals[account] = 0
    cancelled_score = 0
    for row in rows:
        flag = row[FLAG]
        if flag == VOID or flag == REVIVE:
            flag_counts[flag] = flag_counts.get(flag, 0) + 1
            continue
        final = row[FINAL]
        if row[LIVE]:
            account_totals[row[BOOKED]] += final
            region_totals[row[REGION]] = region_totals.get(row[REGION], 0) + final
            kind_totals[row[KIND]] = kind_totals.get(row[KIND], 0) + final
            flag_counts[flag] = flag_counts.get(flag, 0) + 1
        else:
            cancelled_score += final
            if flag not in flag_counts:
                flag_counts[flag] = 0
            if row[REGION] not in region_totals:
                region_totals[row[REGION]] = 0
            if row[KIND] not in kind_totals:
                kind_totals[row[KIND]] = 0

    checksum = 0
    for position, row in enumerate(rows, 1):
        checksum = (checksum * 1315423911 + row[FINAL] * position + row[OID]) & 0xFFFFFFFF

    ordered = sorted(account_totals.items(), key=lambda item: (-item[1], item[0]))
    top_accounts = [[account, total] for account, total in ordered[:rules.top_n]]
    total_score = sum(account_totals.values())
    live_count = 0
    for row in rows:
        if row[LIVE] and row[FLAG] != VOID and row[FLAG] != REVIVE:
            live_count += 1

    result = {
        'label': rules.label,
        'event_count': event_count,
        'account_totals': account_totals,
        'region_totals': region_totals,
        'kind_totals': kind_totals,
        'flag_counts': flag_counts,
        'premium_accounts': sorted(premium),
        'top_accounts': top_accounts,
        'checksum': checksum,
    }
    metrics = {
        'total_score': total_score,
        'average_score': total_score // live_count if live_count else 0,
        'top_account': top_accounts[0][0] if top_accounts else None,
        'top_account_score': top_accounts[0][1] if top_accounts else 0,
    }
    quality = {
        'unpriced_rows': unpriced_rows,
        'unregistered_rows': unregistered_rows,
        'rebooked_rows': sum(1 for row in rows if row[BOOKED] != row[WRITTEN]),
        'orphan_voids': orphan_voids,
        'orphan_revives': orphan_revives,
        'cancelled_score': cancelled_score,
        'amendments': [[row[ID], row[FINAL]] for row in rows if row[AMENDED]],
    }
    rescued = sorted(
        account for account in premium
        if per[account][2] < rules.premium_floor * per[account][0]
    )
    group_keys = (len(account_totals) + len(region_totals) + len(kind_totals)
                  + len(flag_counts))
    bottleneck = {
        'group_keys': group_keys,
        'processed_rows': processed,
        'baseline_row_scans': group_keys * processed,
    }
    return result, metrics, quality, rescued, waived_penalty, bottleneck


def aggregate(events_path, rules_path):
    """Rate one scenario workload and return its result object."""
    rules = Rules(rules_path)
    return rate(events_path, rules)[0]


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: optimize.py EVENTS_CSV RULES_JSON\n')
        return 2
    value = aggregate(argv[1], argv[2])
    sys.stdout.write(json.dumps(value, sort_keys=True) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))

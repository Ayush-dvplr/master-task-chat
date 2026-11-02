#!/usr/bin/env python3
"""Clear one revenue epoch of the transit interchange.

Usage:
    python3 clear_epoch.py <register_directory> <output_directory>

The register directory holds the machine readable registers and the
calibration material.  Everything the interchange parameterises itself with
is recovered from the calibration slice carried in that directory, so the
cleared account is a function of the registers alone: it does not depend on
the order any register states its rows in, nor on anything particular to the
epoch being cleared.

Order in which the rulebooks bear on a tap (settled by what each consumes and
produces): admission (A), identity (I), tariff (T), ledger reversals (L4),
suspension (S), exceptions (L5), capping (C), partition (P), then the netting
(N) and assurance (A-after-admission) layers on top of the cleared ledger.
"""

import csv
import json
import os
import sys

# ---------------------------------------------------------------- registers

CSV_REGISTERS = (
    'epoch_calendar', 'epoch_policy', 'operators', 'zones', 'gates',
    'gate_faults', 'tariff_tables', 'netting_policy', 'assurance_policy',
    'token_events', 'taps',
)

# Columns that are identifiers or vocabularies and must stay textual.
TEXT_COLUMNS = frozenset({
    'epoch_id', 'boundary', 'operator_id', 'zone_id', 'gate_id', 'gate_class',
    'tap_id', 'token_ref', 'rider_class', 'completion_class', 'op',
    'event_id', 'event_type', 'subject_ref', 'target_ref', 'fault_id',
    'table_id', 'effective_from', 'superseded_at', 'opened_at', 'closed_at',
    'tapped_at', 'peak_from', 'peak_to', 'opens_at', 'closes_at',
    'exception_id', 'status',
})

BOOL_COLUMNS = frozenset({'decommissioned', 'provisional'})


def _coerce(value, column):
    if column in TEXT_COLUMNS:
        return '' if value is None else str(value)
    if value is None:
        return ''
    text = str(value).strip()
    if text == '':
        return ''
    try:
        number = int(text)
    except ValueError:
        return text
    if column in BOOL_COLUMNS:
        return bool(number)
    return number


def _coerce_row(row):
    return {key: _coerce(value, key) for key, value in row.items()}


def read_csv_register(path):
    with open(path, newline='', encoding='utf-8') as handle:
        return [_coerce_row(row) for row in csv.DictReader(handle)]


def read_json_register(path):
    with open(path, encoding='utf-8') as handle:
        document = json.load(handle)
    if isinstance(document, dict):
        document = document.get('exceptions', [])
    return [_coerce_row(row) for row in document]


def load_registers(directory):
    registers = {}
    for name in CSV_REGISTERS:
        path = os.path.join(directory, name + '.csv')
        registers[name] = read_csv_register(path) if os.path.exists(path) else []
    path = os.path.join(directory, 'exceptions.json')
    registers['exceptions'] = read_json_register(path) if os.path.exists(path) else []
    return registers


def load_calibration(directory):
    path = os.path.join(directory, 'calibration_controls.json')
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


def calibration_registers(controls):
    """The calibration slice as an ordinary register set."""
    return {name: [_coerce_row(row) for row in rows]
            for name, rows in controls['slice'].items()}


def single(rows, key):
    """First row of a one row policy register, order invariantly."""
    if not rows:
        return {}
    return sorted(rows, key=lambda row: str(row.get(key, '')))[0]


# ---------------------------------------------------------------- the grid

def make_place(step, rule):
    """place(num/den): the multiple of `step` nearest to num/den."""
    step = int(step) if step else 1
    if step < 1:
        step = 1

    def place(num, den=1):
        if den < 0:
            num, den = -num, -den
        whole = den * step
        quotient, rest = divmod(num, whole)
        twice = 2 * rest
        if twice < whole:
            index = quotient
        elif twice > whole:
            index = quotient + 1
        elif rule == 'away_from_zero':
            index = quotient + 1
        elif rule == 'toward_zero':
            index = quotient
        elif rule == 'to_even_multiple':
            index = quotient if quotient % 2 == 0 else quotient + 1
        elif rule == 'to_odd_multiple':
            index = quotient if quotient % 2 == 1 else quotient + 1
        else:
            raise ValueError('unknown midpoint rule %r' % (rule,))
        return index * step

    return place


def window_covers(convention, start, end, when):
    if convention == 'closed_closed':
        return start <= when <= end
    if convention == 'closed_open':
        return start <= when < end
    if convention == 'open_closed':
        return start < when <= end
    if convention == 'open_open':
        return start < when < end
    raise ValueError('unknown window convention %r' % (convention,))


def is_inside(convention, start, end, when):
    return window_covers(convention, start, end, when)


# ---------------------------------------------------------------- identity

def resolve_identity(token_ref, when, events_by_subject):
    """The identity walk of I2 and I3, as at `when`.

    Returns (canonical_token, outcome, chain).  A walk that ends on its own
    canonicalises to the identity it ended on; a walk that closes on itself
    canonicalises to the lexicographically smallest identity of its cycle.
    """
    chain = [token_ref]
    seen = {token_ref}
    current = token_ref
    while True:
        best = None
        for event in events_by_subject.get(current, ()):
            if event['event_type'] not in ('rotate', 'merge'):
                continue
            if event['effective_at'] > when:
                continue
            if best is None or (event['effective_at'], event['event_id']) > (
                    best['effective_at'], best['event_id']):
                best = event
        if best is None:
            return current, 'walk_end', chain
        target = best['target_ref']
        chain.append(target)
        if target in seen:
            # The chain from that identity's first visit onwards is the cycle.
            start = chain.index(target)
            cycle = chain[start:]
            return min(cycle), 'cycle_broken', chain
        seen.add(target)
        current = target


def terminal_outcome(chain, when, events_by_subject):
    """I4: retire and revoke count on any member of the chain."""
    revoked = False
    retired = False
    for member in chain:
        for event in events_by_subject.get(member, ()):
            if event['effective_at'] > when:
                continue
            if event['event_type'] == 'revoke':
                revoked = True
            elif event['event_type'] == 'retire':
                retired = True
    if revoked:
        return 'revoked'
    if retired:
        return 'retired'
    return None


# ---------------------------------------------------------------- the epoch


class Epoch(object):
    """One clearance of one epoch under one reading of the seven properties."""

    def __init__(self, registers, params):
        self.registers = registers
        self.params = params
        self.place = make_place(params['grid_step_micros'],
                                params['midpoint_rule'])
        self._lay_out()
        self._admit()
        self._resolve_identities()
        self._price()
        self._apply_reversals()
        self._suspend()
        self._apply_exceptions()
        self._cap()
        self._partition()
        self._net()
        self._assure()

    # -- register layout ----------------------------------------------------

    def _lay_out(self):
        registers = self.registers
        self.calendar = single(registers['epoch_calendar'], 'epoch_id')
        self.policy = single(registers['epoch_policy'], 'epoch_id')
        self.epoch_id = self.calendar.get('epoch_id') or self.policy.get('epoch_id') or ''
        self.opens_at = self.calendar.get('opens_at', '')
        self.closes_at = self.calendar.get('closes_at', '')
        self.boundary = self.policy.get('boundary', 'closed_open')
        self.peak_from = self.policy.get('peak_from', '')
        self.peak_to = self.policy.get('peak_to', '')

        self.operators = {row['operator_id']: row
                          for row in registers['operators']}
        self.operator_ids = sorted(self.operators)
        self.zones = {row['zone_id']: row for row in registers['zones']}
        self.zone_ids = sorted(self.zones)
        self.gates = {row['gate_id']: row for row in registers['gates']}
        self.gate_ids = sorted(self.gates)
        self.tariffs = sorted(registers['tariff_tables'],
                              key=lambda row: (row['effective_from'], row['table_id']))
        self.faults = registers['gate_faults']
        self.exceptions = sorted(registers['exceptions'],
                                 key=lambda row: row['exception_id'])
        self.events = sorted(registers['token_events'],
                             key=lambda row: row['event_id'])
        self.events_by_subject = {}
        for event in self.events:
            self.events_by_subject.setdefault(event['subject_ref'], []).append(event)

        self.zone_of_gate = {}
        self.operator_of_gate = {}
        for gate_id in self.gate_ids:
            zone_id = self.gates[gate_id]['zone_id']
            self.zone_of_gate[gate_id] = zone_id
            zone = self.zones.get(zone_id, {})
            self.operator_of_gate[gate_id] = zone.get('operator_id', '')
        self.zones_of_operator = {}
        for zone_id in self.zone_ids:
            operator_id = self.zones[zone_id].get('operator_id', '')
            self.zones_of_operator.setdefault(operator_id, []).append(zone_id)
        self.gates_of_zone = {}
        for gate_id in self.gate_ids:
            self.gates_of_zone.setdefault(self.zone_of_gate[gate_id], []).append(gate_id)

        netting = single(registers['netting_policy'], 'interchange_share_bp')
        self.interchange_share_bp = netting.get('interchange_share_bp', 0)
        self.netting_multiplier = netting.get('netting_multiplier', 0)
        self.netting_modulus = netting.get('netting_modulus', 0)

        assurance = single(registers['assurance_policy'], 'assurance_sigma')
        self.assurance_sigma = assurance.get('assurance_sigma', 0)
        self.assurance_multiplier = assurance.get('assurance_multiplier', 0)
        self.assurance_modulus = assurance.get('assurance_modulus', 0)
        self.min_sample = assurance.get('min_sample', 0)

        # Taps in canonical order.  A `tap_id` can be repeated, so every
        # per tap fact is keyed by the tap's position in this list, which is a
        # property of the data and never of the order the register stated its
        # rows in.
        self.taps = sorted(registers['taps'],
                           key=lambda row: (row['tapped_at'], row['tap_id']))
        self.tap_by_id = {}
        for index, tap in enumerate(self.taps):
            tap['key'] = index
            # The first occurrence in canonical order carries the identifier.
            if tap['tap_id'] not in self.tap_by_id:
                self.tap_by_id[tap['tap_id']] = index
        self.taps_of_gate = {}
        for tap in self.taps:
            self.taps_of_gate.setdefault(tap['gate_id'], []).append(tap)

    # -- A: admission -------------------------------------------------------

    def _admit(self):
        """A1 to A4.  Every in epoch tap is admitted; A3 and A4 withdraw some
        of them at once, and an admitted tap that is not withdrawn is live."""
        self.disposition = {}
        self.reason = {}
        self.out_of_epoch_ids = []
        self.duplicate_ids = []
        seen = set()
        for tap in self.taps:
            key = tap['key']
            tap_id = tap['tap_id']
            if not is_inside(self.boundary, self.opens_at, self.closes_at,
                             tap['tapped_at']):
                self.disposition[key] = 'out_of_epoch'
                self.reason[key] = 'out_of_epoch'
                self.out_of_epoch_ids.append(tap_id)
                continue
            self.disposition[key] = 'admitted'
            self.reason[key] = ''
            if tap_id in seen:
                self.disposition[key] = 'withdrawn'
                self.reason[key] = 'duplicate_tap_id'
                if tap_id not in self.duplicate_ids:
                    self.duplicate_ids.append(tap_id)
                continue
            seen.add(tap_id)
            if self.gates.get(tap['gate_id'], {}).get('decommissioned', False):
                self.disposition[key] = 'withdrawn'
                self.reason[key] = 'decommissioned_gate'
        # Admitted taps in canonical order: identity resolves every one of
        # them, whatever happened to it later.
        self.admitted = [tap for tap in self.taps
                         if self.disposition[tap['key']] != 'out_of_epoch']
        # Live taps: admitted and not yet withdrawn.
        self.live = [tap for tap in self.admitted
                     if self.disposition[tap['key']] == 'admitted']

    # -- I: identity --------------------------------------------------------

    def _resolve_identities(self):
        self.canonical = {}
        self.outcome = {}
        self.chain = {}
        for tap in self.admitted:
            key = tap['key']
            token, outcome, chain = resolve_identity(
                tap['token_ref'], tap['tapped_at'], self.events_by_subject)
            terminal = terminal_outcome(chain, tap['tapped_at'], self.events_by_subject)
            if terminal is not None:
                outcome = terminal
            elif outcome == 'walk_end':
                outcome = 'direct' if len(chain) == 1 else 'rotated'
            self.canonical[key] = token
            self.chain[key] = chain
            self.outcome[key] = outcome

        # I6: home operator of every canonical identity.
        self.home_operator = {}
        for tap in self.admitted:                      # already canonical order
            identity = self.canonical[tap['key']]
            if identity not in self.home_operator:
                self.home_operator[identity] = self.operator_of_gate.get(tap['gate_id'], '')

        # I4: a terminal outcome withdraws the tap before anything prices it.
        for tap in self.admitted:
            key = tap['key']
            if self.disposition[key] != 'admitted':
                continue                       # A3 and A4 have already had it
            if self.outcome[key] == 'retired':
                self.disposition[key] = 'withdrawn'
                self.reason[key] = 'identity_retired'
            elif self.outcome[key] == 'revoked':
                self.disposition[key] = 'withdrawn'
                self.reason[key] = 'identity_revoked'
        self.live = [tap for tap in self.admitted
                     if self.disposition[tap['key']] == 'admitted']

    # -- T: tariff ----------------------------------------------------------

    def governing_table(self, when):
        live = None
        for row in self.tariffs:
            if row['effective_from'] <= when and (
                    not row['superseded_at'] or when < row['superseded_at']):
                if live is None or (row['effective_from'], row['table_id']) > (
                        live['effective_from'], live['table_id']):
                    live = row
        return live

    def is_peak(self, when):
        if not self.peak_from or not self.peak_to:
            return False
        return self.peak_from <= when[11:16] < self.peak_to

    def fault_abatement(self, gate_id, when):
        best = 0
        for fault in self.faults:
            if fault['gate_id'] != gate_id:
                continue
            close = fault['closed_at'] or self.closes_at
            if window_covers(self.params['fault_window_edge'],
                             fault['opened_at'], close, when):
                best = max(best, fault['abatement_micros'])
        return best

    def _price(self):
        """T1 to T7 for every live tap that identity left priceable."""
        self.table_id = {}
        self.gross = {}
        self.unit_fare = {}
        self.peak = {}
        self.cross = {}
        for tap in self.taps:
            self.peak[tap['key']] = self.is_peak(tap['tapped_at'])
        self.no_table_ids = []
        priced_outcomes = ('direct', 'rotated', 'cycle_broken')
        for tap in self.admitted:
            key = tap['key']
            self.cross[key] = False
            self.table_id[key] = ''
            self.gross[key] = 0
            self.unit_fare[key] = 0
            if self.disposition[key] != 'admitted':
                continue
            if self.outcome[key] not in priced_outcomes:
                continue
            table = self.governing_table(tap['tapped_at'])
            if table is None:
                # T1: no table governs the instant, so the tap is withdrawn.
                self.disposition[key] = 'withdrawn'
                self.reason[key] = 'no_governing_table'
                self.no_table_ids.append(tap['tap_id'])
                continue
            self.table_id[key] = table['table_id']
            gate = self.gates.get(tap['gate_id'], {})
            zone = self.zones.get(self.zone_of_gate.get(tap['gate_id'], ''), {})
            home = self.home_operator.get(self.canonical[key], '')
            cross = bool(self.operator_of_gate.get(tap['gate_id'], '')) and \
                self.operator_of_gate.get(tap['gate_id'], '') != home
            self.cross[key] = cross
            fare = self._fare(tap, table, gate, zone, cross)
            self.gross[key] = fare[0]
            self.unit_fare[key] = fare[1]

    def _fare(self, tap, table, gate, zone, cross):
        """T2 to T7: the unit fare of one tap, in micros."""
        distance = tap['distance_units']
        band = zone.get('tariff_band', 0)
        if tap['rider_class'] == 'concession':
            rate = table['rate_concession']
        elif self.peak[tap['key']]:
            rate = table['rate_peak']
        else:
            rate = table['rate_offpeak']
        column = 'mult_' + tap['completion_class']
        mult = table.get(column, 10000)
        distance_rate_product = rate * distance
        place = self.place
        gross = place(distance_rate_product * band * mult, 10000)
        value = gross
        floor = gate.get('floor_fare_micros', 0)
        abatement = self.fault_abatement(tap['gate_id'], tap['tapped_at'])
        levy_basis = self.params['levy_basis']
        for adjustment in self.params['adjustment_order']:
            if adjustment == 'fault_abatement':
                if abatement:
                    value = place(max(0, value - abatement), 1)
            elif adjustment == 'concession_relief':
                if tap['rider_class'] == 'concession':
                    value = place(value * (10000 - table['relief_bp']), 10000)
            elif adjustment == 'interchange_uplift':
                if cross:
                    value = place(value * (10000 + table['uplift_bp']), 10000)
            elif adjustment == 'shortfall_levy':
                if levy_basis == 'gross_before_adjustments':
                    basis = gross
                elif levy_basis == 'running_value':
                    basis = value
                elif levy_basis == 'floor_fare':
                    basis = floor
                elif levy_basis == 'distance_rate_product':
                    basis = distance_rate_product
                else:
                    raise ValueError('unknown levy basis %r' % (levy_basis,))
                value = place(value + place(basis * table['levy_bp'], 10000), 1)
            else:
                raise ValueError('unknown adjustment %r' % (adjustment,))
        return gross, max(value, floor)

    # -- L4: reversal records ----------------------------------------------

    def _apply_reversals(self):
        """L4, resolved before the suspension rulebook measures any burden."""
        self.reversal_keys = set()
        self.voided_ids = []
        for tap in self.admitted:
            key = tap['key']
            if tap['op'] != 'void' or self.disposition[key] != 'admitted':
                continue
            self.disposition[key] = 'withdrawn'
            if not self.reason[key]:
                self.reason[key] = 'reversal_record'
            self.reversal_keys.add(key)
        reach = self.params['void_reach']
        if reach == 'tap_only':
            return
        for tap in self.admitted:                      # canonical order
            key = tap['key']
            if key not in self.reversal_keys:
                continue
            identity = self.canonical[key]
            zone_id = self.zone_of_gate.get(tap['gate_id'], '')
            operator_id = self.operator_of_gate.get(tap['gate_id'], '')
            for other in self.admitted:
                other_key = other['key']
                if other_key == key:
                    continue
                if self.canonical[other_key] != identity:
                    continue
                if reach == 'token_zone_epoch':
                    if self.zone_of_gate.get(other['gate_id'], '') != zone_id:
                        continue
                elif reach == 'token_operator_epoch':
                    if self.operator_of_gate.get(other['gate_id'], '') != operator_id:
                        continue
                if self.disposition[other_key] != 'admitted':
                    continue
                self.disposition[other_key] = 'withdrawn'
                self.reason[other_key] = 'voided_by_reversal'
                self.voided_ids.append(other['tap_id'])

    # -- S: suspension -----------------------------------------------------

    def gate_state(self):
        """admitted taps and currently withdrawn taps per gate."""
        admitted = {}
        defects = {}
        for gate_id in self.gate_ids:
            admitted[gate_id] = 0
            defects[gate_id] = 0
        for tap in self.admitted:
            gate_id = tap['gate_id']
            admitted[gate_id] = admitted.get(gate_id, 0) + 1
            if self.disposition[tap['key']] != 'admitted':
                defects[gate_id] = defects.get(gate_id, 0) + 1
        return admitted, defects

    def _suspend(self):
        taps_at_gate = {}
        for tap in self.admitted:
            taps_at_gate.setdefault(tap['gate_id'], []).append(tap)
        priced_at_gate = {}
        for tap in self.admitted:
            if self.disposition[tap['key']] == 'admitted':
                priced_at_gate[tap['gate_id']] = priced_at_gate.get(tap['gate_id'], 0) + 1
        self.suspended = {}
        self.suspension_reason = {}
        for gate_id in self.gate_ids:
            self.suspended[gate_id] = False
            self.suspension_reason[gate_id] = ''
            if self.gates[gate_id].get('decommissioned', False):
                self.suspended[gate_id] = True
                self.suspension_reason[gate_id] = 'decommissioned'
        self.unvalidated = set()
        self.stood_down = set()
        self.burden_bp = {gate_id: 0 for gate_id in self.gate_ids}
        self.iterations = 0

        def withdraw_at(gate_id):
            changed = False
            for tap in taps_at_gate.get(gate_id, ()):
                key = tap['key']
                if self.disposition[key] == 'admitted':
                    self.disposition[key] = 'withdrawn'
                    self.reason[key] = 'gate_suspended'
                    priced_at_gate[gate_id] = priced_at_gate.get(gate_id, 0) - 1
                    changed = True
            return changed

        while True:
            self.iterations += 1
            changed = False
            # S1 measure every gate's burden.
            admitted, defects = self.gate_state()
            for gate_id in self.gate_ids:
                count = admitted.get(gate_id, 0)
                burden = (10000 * defects.get(gate_id, 0)) // count if count else 0
                self.burden_bp[gate_id] = burden
                if self.suspended[gate_id]:
                    continue
                if burden > self.gates[gate_id].get('fault_allowance_bp', 0):
                    self.suspended[gate_id] = True
                    self.suspension_reason[gate_id] = 'burden'
                    changed = True
            # S3 zone validation.
            for zone_id in self.zone_ids:
                if zone_id in self.unvalidated:
                    continue
                floor = self.zones[zone_id].get('validation_floor', 0)
                if floor <= 0:
                    continue
                carrying = 0
                for gate_id in self.gates_of_zone.get(zone_id, ()):
                    if self.suspended[gate_id]:
                        continue
                    if priced_at_gate.get(gate_id, 0) > 0:
                        carrying += 1
                if carrying < floor:
                    self.unvalidated.add(zone_id)
                    changed = True
            # S4 provisional zones.
            for zone_id in self.zone_ids:
                if zone_id in self.unvalidated:
                    continue
                if not self.zones[zone_id].get('provisional', False):
                    continue
                operator_id = self.zones[zone_id].get('operator_id', '')
                for sibling in self.zones_of_operator.get(operator_id, ()):
                    if sibling != zone_id and sibling in self.unvalidated:
                        self.unvalidated.add(zone_id)
                        changed = True
                        break
            # S5 operators standing down.
            for operator_id in self.operator_ids:
                if operator_id in self.stood_down:
                    continue
                owned = self.zones_of_operator.get(operator_id, [])
                if not owned:
                    continue
                if all(zone_id in self.unvalidated for zone_id in owned):
                    self.stood_down.add(operator_id)
                    changed = True
            # S6 what the states do to gates.
            for zone_id in sorted(self.unvalidated):
                for gate_id in self.gates_of_zone.get(zone_id, ()):
                    if not self.suspended[gate_id]:
                        self.suspended[gate_id] = True
                        self.suspension_reason[gate_id] = 'zone_unvalidated'
                        changed = True
            for operator_id in sorted(self.stood_down):
                for zone_id in self.zones_of_operator.get(operator_id, ()):
                    for gate_id in self.gates_of_zone.get(zone_id, ()):
                        if not self.suspended[gate_id]:
                            self.suspended[gate_id] = True
                            self.suspension_reason[gate_id] = 'operator_stood_down'
                            changed = True
            # S2 suspension withdraws.
            for gate_id in self.gate_ids:
                if self.suspended[gate_id] and priced_at_gate.get(gate_id, 0) > 0:
                    if withdraw_at(gate_id):
                        changed = True
            if not changed:
                break
        # Remeasure so the register reports the burdens the fixpoint settled on.
        admitted, defects = self.gate_state()
        for gate_id in self.gate_ids:
            count = admitted.get(gate_id, 0)
            self.burden_bp[gate_id] = (10000 * defects.get(gate_id, 0)) // count if count else 0

    # -- L5: exceptions ----------------------------------------------------

    def _apply_exceptions(self):
        self.exception_id = {tap['key']: '' for tap in self.taps}
        self.exceptions_on_withdrawn = []
        self.exceptions_upheld = 0
        self.exceptions_rejected = 0
        for row in self.exceptions:
            if row['status'] == 'upheld':
                self.exceptions_upheld += 1
            else:
                self.exceptions_rejected += 1
            if row['status'] != 'upheld':
                continue
            tap_id = row['tap_id']
            # A tap_id is the first occurrence in canonical order; a repeated
            # one is a withdrawn duplicate and not a tap of its own.
            index = self.tap_by_id.get(tap_id)
            if index is None:
                continue                       # names no tap in the register
            key = self.taps[index]['key']
            if self.disposition[key] != 'admitted':
                self.exceptions_on_withdrawn.append(row['exception_id'])
                continue
            self.unit_fare[key] = row['unit_fare_micros']
            self.exception_id[key] = row['exception_id']

    # -- C: capping --------------------------------------------------------

    def _cap(self):
        self.priced = [tap for tap in self.admitted
                       if self.disposition[tap['key']] == 'admitted']
        self.priced_total_before = {}
        for zone_id in self.zone_ids:
            self.priced_total_before[zone_id] = 0
        for tap in self.priced:
            zone_id = self.zone_of_gate.get(tap['gate_id'], '')
            self.priced_total_before[zone_id] = \
                self.priced_total_before.get(zone_id, 0) + self.unit_fare[tap['key']]

        headroom = {}
        for zone_id in self.zone_ids:
            cap = self.zones[zone_id].get('revenue_cap_micros', 0)
            headroom[zone_id] = cap - self.priced_total_before.get(zone_id, 0)
        order = self.params['cap_release_order']
        if order == 'ascending_zone_id':
            self.release_order = sorted(self.zone_ids)
        elif order == 'descending_headroom_then_zone':
            self.release_order = sorted(self.zone_ids,
                                        key=lambda z: (-headroom[z], z))
        elif order == 'ascending_headroom_then_zone':
            self.release_order = sorted(self.zone_ids,
                                        key=lambda z: (headroom[z], z))
        elif order == 'descending_cap_then_zone':
            self.release_order = sorted(self.zone_ids,
                                        key=lambda z: (-self.zones[z].get('revenue_cap_micros', 0), z))
        else:
            raise ValueError('unknown release order %r' % (order,))

        lent = {zone_id: 0 for zone_id in self.zone_ids}
        borrowed = {zone_id: 0 for zone_id in self.zone_ids}
        self.loans = []
        float_left = {operator_id: self.operators[operator_id].get('float_ceiling_micros', 0)
                      for operator_id in self.operator_ids}
        for zone_id in self.release_order:
            need = -headroom[zone_id]
            if need <= 0:
                continue
            operator_id = self.zones[zone_id].get('operator_id', '')
            for lender in self.release_order:
                if need <= 0:
                    break
                if lender == zone_id:
                    continue
                if self.zones[lender].get('operator_id', '') != operator_id:
                    continue
                spare = headroom[lender] - lent[lender]
                if spare <= 0:
                    continue
                ceiling = float_left.get(operator_id, 0)
                amount = min(spare, need, ceiling)
                if amount <= 0:
                    continue
                self.loans.append({'from_zone': lender, 'to_zone': zone_id,
                                   'operator_id': operator_id,
                                   'amount_micros': amount})
                lent[lender] += amount
                borrowed[zone_id] += amount
                need -= amount
                float_left[operator_id] = ceiling - amount
        self.lent = lent
        self.borrowed = borrowed
        self.effective_cap = {}
        for zone_id in self.zone_ids:
            self.effective_cap[zone_id] = \
                self.zones[zone_id].get('revenue_cap_micros', 0) + borrowed[zone_id]

        # C4 curtailment, with the C5 coverage obligation.
        self.curtailed = {zone_id: [] for zone_id in self.zone_ids}
        curtailed_keys = set()
        for zone_id in self.release_order:
            cap = self.effective_cap[zone_id]
            total = self.priced_total_before.get(zone_id, 0)
            if total <= cap:
                continue
            candidates = sorted(
                (tap for tap in self.priced
                 if self.zone_of_gate.get(tap['gate_id'], '') == zone_id),
                key=lambda tap: (-self.unit_fare[tap['key']],
                                 tap['tapped_at'], tap['tap_id']))
            for tap in candidates:
                if total <= cap:
                    break
                key = tap['key']
                if self._protected(key, curtailed_keys):
                    continue
                self.curtailed[zone_id].append(tap['tap_id'])
                curtailed_keys.add(key)
                self.disposition[key] = 'withdrawn'
                self.reason[key] = 'cap_curtailed'
                total -= self.unit_fare[key]

    def _protected(self, key, curtailed_keys):
        """C5: the only remaining priced tap at its gate, gate unsuspended."""
        gate_id = self.taps[key]['gate_id']
        if self.suspended.get(gate_id, False):
            return False
        for other in self.taps_of_gate.get(gate_id, ()):
            other_key = other['key']
            if other_key == key:
                continue
            if other_key in curtailed_keys:
                continue
            if self.disposition.get(other_key) != 'admitted':
                continue
            return False
        return True

    # -- P: partition ------------------------------------------------------

    def _partition(self):
        self.priced = [tap for tap in self.admitted
                       if self.disposition[tap['key']] == 'admitted']
        priced_zones = {self.zone_of_gate.get(tap['gate_id'], '') for tap in self.priced}
        self.zones_in_scope = [zone_id for zone_id in self.zone_ids
                               if zone_id in priced_zones]
        self.operators_in_scope = [operator_id for operator_id in self.operator_ids
                                   if any(self.zones[zone_id].get('operator_id', '') == operator_id
                                          for zone_id in self.zones_in_scope)]
        self.priced_at_gate = {}
        for tap in self.priced:
            self.priced_at_gate[tap['gate_id']] = self.priced_at_gate.get(tap['gate_id'], 0) + 1

    # -- N: netting --------------------------------------------------------

    def _net(self):
        share = self.interchange_share_bp
        place = self.place
        amounts = {}
        counts = {}
        for tap in self.priced:                        # canonical order
            key = tap['key']
            if not self.cross[key]:
                continue
            payer = self.operator_of_gate.get(tap['gate_id'], '')
            payee = self.home_operator.get(self.canonical[key], '')
            if payer == payee:
                continue
            amount = place(self.unit_fare[key] * share, 10000)
            if amount <= 0:
                continue
            key = (payer, payee)
            amounts[key] = amounts.get(key, 0) + amount
            counts[key] = counts.get(key, 0) + 1
        self.obligations = amounts
        self.obligation_counts = counts
        self.obligation_total = sum(amounts.values())

        edges = dict(amounts)
        self.cycles = []
        while True:
            cycle = self._first_cycle(edges)
            if cycle is None:
                break
            amount = min(edges[(cycle[i], cycle[(i + 1) % len(cycle)])]
                         for i in range(len(cycle)))
            for i in range(len(cycle)):
                key = (cycle[i], cycle[(i + 1) % len(cycle)])
                edges[key] -= amount
                if edges[key] <= 0:
                    del edges[key]
            self.cycles.append({'sequence': list(cycle), 'amount_micros': amount})
        self.residual_edges = edges
        self.residual_total = sum(edges.values())
        self.cancelled_total = sum(row['amount_micros'] * len(row['sequence'])
                                   for row in self.cycles)

        self.gross_out = {operator_id: 0 for operator_id in self.operator_ids}
        self.gross_in = {operator_id: 0 for operator_id in self.operator_ids}
        self.residual_out = {operator_id: 0 for operator_id in self.operator_ids}
        self.residual_in = {operator_id: 0 for operator_id in self.operator_ids}
        for (payer, payee), amount in amounts.items():
            self.gross_out[payer] = self.gross_out.get(payer, 0) + amount
            self.gross_in[payee] = self.gross_in.get(payee, 0) + amount
        for (payer, payee), amount in edges.items():
            self.residual_out[payer] = self.residual_out.get(payer, 0) + amount
            self.residual_in[payee] = self.residual_in.get(payee, 0) + amount
        self.net_position = {operator_id: self.residual_out[operator_id] - self.residual_in[operator_id]
                             for operator_id in self.operator_ids}

        # N4 funding schedule.
        def rank(operator_id):
            return self.operators[operator_id].get('clearing_rank', 0)
        rows = sorted(edges.items(),
                      key=lambda item: (rank(item[0][0]), rank(item[0][1]),
                                        -item[1], item[0][0], item[0][1]))
        funded = {operator_id: 0 for operator_id in self.operator_ids}
        self.schedule = []
        for (payer, payee), amount in rows:
            ceiling = self.operators[payer].get('funding_ceiling_micros', 0)
            if funded[payer] + amount <= ceiling:
                funded[payer] += amount
                state = 'funded'
            else:
                state = 'deferred'
            self.schedule.append({'payer': payer, 'payee': payee,
                                  'amount_micros': amount, 'state': state,
                                  'payer_funded_running_micros': funded[payer]})
        self.funded = funded
        digest = 0
        for row in self.schedule:
            digest = (digest * self.netting_multiplier + row['amount_micros']) % self.netting_modulus
        self.netting_digest = digest

    def _first_cycle(self, edges):
        """The first directed cycle in canonical cycle order, or None."""
        nodes = sorted({node for pair in edges for node in pair})
        best = None
        for start in nodes:
            best = self._search_cycle(edges, start, start, [start], best, nodes)
        return list(best) if best is not None else None

    def _search_cycle(self, edges, start, current, path, best, nodes):
        for node in sorted({payee for payer, payee in edges if payer == current}):
            if node == start:
                candidate = tuple(path)
                if best is None or (len(candidate), candidate) < (len(best), best):
                    best = candidate
                continue
            if node < start:
                continue                      # start is the cycle's smallest
            if node in path:
                continue
            limit = len(best) if best is not None else len(nodes)
            if len(path) + 1 > limit:
                continue
            best = self._search_cycle(edges, start, node, path + [node], best, nodes)
        return best

    # -- A: assurance ------------------------------------------------------

    def _median(self, values):
        if not values:
            return 0
        ordered = sorted(values)
        middle = len(ordered) // 2
        if len(ordered) % 2 == 1:
            return ordered[middle]
        return ordered[middle - 1]               # lower of the two middle values

    def _assure(self):
        self.sample = []
        self.zero_distance_priced = []
        for tap in self.priced:                        # canonical order
            key = tap['key']
            distance = tap['distance_units']
            if distance <= 0:
                self.zero_distance_priced.append(tap['tap_id'])
                continue
            floor = self.gates.get(tap['gate_id'], {}).get('floor_fare_micros', 0)
            margin = (self.unit_fare[key] - floor) // distance
            self.sample.append({'tap_id': tap['tap_id'],
                               'rider_class': tap['rider_class'],
                               'unit_fare_micros': self.unit_fare[key],
                               'floor_fare_micros': floor,
                               'distance_units': distance,
                               'margin': margin})
        self.sample_size = len(self.sample)
        self.median_margin = self._median([row['margin'] for row in self.sample])
        for row in self.sample:
            row['deviation'] = abs(row['margin'] - self.median_margin)
        self.mad = self._median([row['deviation'] for row in self.sample])
        self.threshold = self.assurance_sigma * self.mad
        hold = self.sample_size > self.min_sample
        for row in self.sample:
            row['held_back'] = bool(hold and row['deviation'] > self.threshold)
        self.retained = [row for row in self.sample if not row['held_back']]
        self.held_back = [row for row in self.sample if row['held_back']]
        self.pool = sum(row['margin'] for row in self.retained)
        self.retained_distance = sum(row['distance_units'] for row in self.retained)

        # S6 distance apportionment by largest remainders.
        classes = sorted({row['rider_class'] for row in self.retained})
        weights = {}
        for row in self.retained:
            weights[row['rider_class']] = weights.get(row['rider_class'], 0) + row['margin']
        total_weight = sum(weights.values())
        shares = {}
        if classes:
            if total_weight == 0:
                shares[classes[0]] = self.retained_distance
            else:
                assigned = 0
                remainders = []
                for rider_class in classes:
                    exact = self.retained_distance * weights[rider_class]
                    whole = exact // total_weight
                    shares[rider_class] = whole
                    assigned += whole
                    remainders.append((exact % total_weight, rider_class))
                left = self.retained_distance - assigned
                order = sorted(remainders, key=lambda item: (-item[0], item[1]))
                index = 0
                while left > 0:
                    rider_class = order[index % len(order)][1]
                    shares[rider_class] += 1
                    left -= 1
                    index += 1
        self.shares = shares
        self.share_classes = classes

        digest = 0
        self.digest_tap_ids = []
        self.digest_margins = []
        for row in sorted(self.retained, key=lambda row: (row['margin'], row['tap_id'])):
            digest = (digest * self.assurance_multiplier + row['margin']) % self.assurance_modulus
            self.digest_tap_ids.append(row['tap_id'])
            self.digest_margins.append(row['margin'])
        self.assurance_digest = digest

    # -- totals ------------------------------------------------------------

    def build(self):
        """Every artifact of the cleared epoch, as plain data."""
        priced_ids = [tap['tap_id'] for tap in self.priced]
        withdrawn_ids = [tap['tap_id'] for tap in self.taps
                         if self.disposition[tap['key']] == 'withdrawn']
        out_ids = [tap['tap_id'] for tap in self.taps
                   if self.disposition[tap['key']] == 'out_of_epoch']
        admitted_ids = [tap['tap_id'] for tap in self.admitted]
        charge = sum(self.unit_fare[tap['key']] for tap in self.priced)
        priced_distance = sum(tap['distance_units'] for tap in self.priced)
        admitted_distance = sum(tap['distance_units'] for tap in self.admitted)
        withdrawn_distance = sum(tap['distance_units'] for tap in self.taps
                                 if self.disposition[tap['key']] == 'withdrawn')

        rows = []
        running = 0
        for tap in self.taps:
            key = tap['key']
            disposition = self.disposition[key]
            fare = self.unit_fare.get(key, 0)
            if disposition == 'admitted':
                disposition = 'priced'
                running += fare
            identity = self.canonical.get(key, '')
            rows.append({
                'tap_id': tap['tap_id'],
                'canonical_token': identity,
                'identity_outcome': self.outcome.get(key, ''),
                'gate_id': tap['gate_id'],
                'zone_id': self.zone_of_gate.get(tap['gate_id'], ''),
                'operator_id': self.operator_of_gate.get(tap['gate_id'], ''),
                'home_operator_id': self.home_operator.get(identity, '')
                    if identity else '',
                'tapped_at': tap['tapped_at'],
                'distance_units': tap['distance_units'],
                'rider_class': tap['rider_class'],
                'completion_class': tap['completion_class'],
                'op': tap['op'],
                'governing_table_id': self.table_id.get(key, ''),
                'peak': self.peak.get(key, False),
                'cross_operator': self.cross.get(key, False),
                'gross_before_adjustments_micros': self.gross.get(key, 0),
                'unit_fare_micros': fare,
                'disposition': disposition,
                'withdrawal_reason': self.reason.get(key, ''),
                'exception_id': self.exception_id.get(key, ''),
                'running_charge_micros': running,
            })

        zone_charge = {zone_id: 0 for zone_id in self.zone_ids}
        zone_distance = {zone_id: 0 for zone_id in self.zone_ids}
        zone_priced = {zone_id: 0 for zone_id in self.zone_ids}
        zone_withdrawn = {zone_id: 0 for zone_id in self.zone_ids}
        operator_charge = {operator_id: 0 for operator_id in self.operator_ids}
        operator_distance = {operator_id: 0 for operator_id in self.operator_ids}
        operator_priced = {operator_id: 0 for operator_id in self.operator_ids}
        operator_withdrawn = {operator_id: 0 for operator_id in self.operator_ids}
        for tap in self.taps:
            key = tap['key']
            zone_id = self.zone_of_gate.get(tap['gate_id'], '')
            operator_id = self.operator_of_gate.get(tap['gate_id'], '')
            disposition = self.disposition[key]
            if disposition == 'admitted':
                zone_charge[zone_id] = zone_charge.get(zone_id, 0) + self.unit_fare[key]
                operator_charge[operator_id] = operator_charge.get(operator_id, 0) + self.unit_fare[key]
                zone_distance[zone_id] = zone_distance.get(zone_id, 0) + tap['distance_units']
                operator_distance[operator_id] = operator_distance.get(operator_id, 0) + tap['distance_units']
                zone_priced[zone_id] = zone_priced.get(zone_id, 0) + 1
                operator_priced[operator_id] = operator_priced.get(operator_id, 0) + 1
            elif disposition == 'withdrawn':
                zone_withdrawn[zone_id] = zone_withdrawn.get(zone_id, 0) + 1
                operator_withdrawn[operator_id] = operator_withdrawn.get(operator_id, 0) + 1

        cap_infeasible = []
        cap_zones = []
        for zone_id in self.zone_ids:
            after = zone_charge.get(zone_id, 0)
            residual = after - self.effective_cap.get(zone_id, 0)
            if residual < 0:
                residual = 0
            if residual > 0:
                cap_infeasible.append(zone_id)
            cap_zones.append({
                'zone_id': zone_id,
                'revenue_cap_micros': self.zones[zone_id].get('revenue_cap_micros', 0),
                'effective_cap_micros': self.effective_cap.get(zone_id, 0),
                'priced_total_before_micros': self.priced_total_before.get(zone_id, 0),
                'priced_total_after_micros': after,
                'lent_micros': self.lent.get(zone_id, 0),
                'borrowed_micros': self.borrowed.get(zone_id, 0),
                'curtailed_tap_ids': sorted(self.curtailed.get(zone_id, [])),
                'residual_micros': residual,
                'cap_infeasible': residual > 0,
            })

        outcomes = {}
        for tap in self.admitted:
            outcomes.setdefault(self.outcome[tap['key']], []).append(tap['tap_id'])
        identity_outcomes = [{'outcome': name, 'tap_ids': sorted(outcomes[name]),
                              'count': len(outcomes[name])}
                             for name in sorted(outcomes)]

        suspended_gates = [gate_id for gate_id in self.gate_ids if self.suspended[gate_id]]
        unvalidated_zones = sorted(self.unvalidated)
        stood_down = sorted(self.stood_down)

        summary = {
            'epoch_id': self.epoch_id,
            'epoch_opens_at': self.opens_at,
            'epoch_closes_at': self.closes_at,
            'resolved_parameters': dict(self.params),
            'taps_total': len(self.taps),
            'taps_admitted': len(admitted_ids),
            'taps_priced': len(priced_ids),
            'taps_withdrawn': len(withdrawn_ids),
            'taps_out_of_epoch': len(out_ids),
            'epoch_charge_micros': charge,
            'priced_distance_units': priced_distance,
            'admitted_distance_units': admitted_distance,
            'suspended_gates': suspended_gates,
            'unvalidated_zones': unvalidated_zones,
            'stood_down_operators': stood_down,
            'operators_in_scope': list(self.operators_in_scope),
            'zones_in_scope': list(self.zones_in_scope),
            'cap_infeasible_zones': cap_infeasible,
        }

        reconciliation = {
            'identities': [
                {'identity': 'admitted_plus_out_of_epoch_equals_total',
                 'left': len(admitted_ids) + len(out_ids), 'right': len(self.taps)},
                {'identity': 'priced_plus_withdrawn_equals_admitted',
                 'left': len(priced_ids) + len(withdrawn_ids), 'right': len(admitted_ids)},
                {'identity': 'zone_charges_sum_to_epoch_charge',
                 'left': sum(zone_charge.values()), 'right': charge},
                {'identity': 'operator_charges_sum_to_epoch_charge',
                 'left': sum(operator_charge.values()), 'right': charge},
                {'identity': 'ledger_running_total_closes_on_epoch_charge',
                 'left': rows[-1]['running_charge_micros'] if rows else 0, 'right': charge},
                {'identity': 'priced_plus_withdrawn_distance_equals_admitted_distance',
                 'left': priced_distance + withdrawn_distance, 'right': admitted_distance},
                {'identity': 'loans_granted_equal_cap_released',
                 'left': sum(row['amount_micros'] for row in self.loans),
                 'right': sum(self.effective_cap.get(zone_id, 0) -
                              self.zones[zone_id].get('revenue_cap_micros', 0)
                              for zone_id in self.zone_ids)},
                {'identity': 'net_positions_sum_to_zero',
                 'left': sum(self.net_position.values()), 'right': 0},
                {'identity': 'residual_plus_cancelled_equals_gross',
                 'left': self.residual_total + self.cancelled_total,
                 'right': self.obligation_total},
                {'identity': 'assurance_shares_sum_to_retained_distance',
                 'left': sum(self.shares.values()), 'right': self.retained_distance},
                {'identity': 'retained_margins_sum_to_pool',
                 'left': sum(row['margin'] for row in self.retained), 'right': self.pool},
            ],
        }
        for row in reconciliation['identities']:
            row['residual'] = row['left'] - row['right']
        reconciliation['residual_total'] = sum(row['residual']
                                               for row in reconciliation['identities'])

        quality = {
            'taps_out_of_epoch': sorted(set(self.out_of_epoch_ids)),
            'taps_without_governing_table': sorted(set(self.no_table_ids)),
            'taps_with_retired_identity': sorted(tap['tap_id'] for tap in self.admitted
                                                 if self.outcome[tap['key']] == 'retired'),
            'taps_with_revoked_identity': sorted(tap['tap_id'] for tap in self.admitted
                                                 if self.outcome[tap['key']] == 'revoked'),
            'identity_cycles_broken': sorted(tap['tap_id'] for tap in self.admitted
                                             if self.outcome[tap['key']] == 'cycle_broken'),
            'duplicate_tap_ids': sorted(set(self.duplicate_ids)),
            'zero_distance_taps': sorted(tap['tap_id'] for tap in self.taps
                                         if tap['distance_units'] == 0),
            'decommissioned_gates': [gate_id for gate_id in self.gate_ids
                                     if self.gates[gate_id].get('decommissioned', False)],
            'faults_open_at_close': sorted(fault['fault_id'] for fault in self.faults
                                           if not fault['closed_at']),
            'exceptions_total': len(self.exceptions),
            'exceptions_upheld': self.exceptions_upheld,
            'exceptions_rejected': self.exceptions_rejected,
            'exceptions_on_withdrawn_taps': sorted(set(self.exceptions_on_withdrawn)),
        }

        identity_register = {
            'outcomes': identity_outcomes,
            'resolutions': [
                {'tap_id': tap['tap_id'], 'token_ref': tap['token_ref'],
                 'canonical_token': self.canonical[tap['key']],
                 'outcome': self.outcome[tap['key']],
                 'chain': list(self.chain[tap['key']])}
                for tap in sorted(self.admitted, key=lambda tap: tap['tap_id'])],
        }

        suspension_register = {
            'iterations': self.iterations,
            'gates': [{'gate_id': gate_id, 'zone_id': self.zone_of_gate.get(gate_id, ''),
                       'burden_bp': self.burden_bp[gate_id],
                       'allowance_bp': self.gates[gate_id].get('fault_allowance_bp', 0),
                       'suspended': self.suspended[gate_id],
                       'reason': self.suspension_reason[gate_id]}
                      for gate_id in self.gate_ids],
            'zones': [{'zone_id': zone_id,
                       'validated_gate_count': sum(1 for gate_id in self.gates_of_zone.get(zone_id, ())
                                                   if not self.suspended[gate_id]),
                       'validation_floor': self.zones[zone_id].get('validation_floor', 0),
                       'unvalidated': zone_id in self.unvalidated}
                      for zone_id in self.zone_ids],
            'operators': [{'operator_id': operator_id,
                           'stood_down': operator_id in self.stood_down}
                          for operator_id in self.operator_ids],
        }

        cap_relief = {
            'release_order': list(self.release_order),
            'zones': cap_zones,
            'loans': self.loans,
            'loan_total_micros': sum(row['amount_micros'] for row in self.loans),
        }

        operator_reports = {}
        for operator_id in self.operators_in_scope:
            suspended = [gate_id for gate_id in self.gate_ids
                         if self.suspended[gate_id]
                         and self.operator_of_gate.get(gate_id, '') == operator_id]
            operator_reports[operator_id] = {
                'partition_kind': 'operator',
                'partition_id': operator_id,
                'epoch_id': self.epoch_id,
                'taps_priced': operator_priced.get(operator_id, 0),
                'taps_withdrawn': operator_withdrawn.get(operator_id, 0),
                'charge_micros': operator_charge.get(operator_id, 0),
                'priced_distance_units': operator_distance.get(operator_id, 0),
                'zones_in_scope': [zone_id for zone_id in self.zones_in_scope
                                   if self.zones[zone_id].get('operator_id', '') == operator_id],
                'gates_suspended': suspended,
                'net_position_micros': self.net_position.get(operator_id, 0),
            }

        zone_reports = {}
        for zone_id in self.zones_in_scope:
            gates_in_scope = [gate_id for gate_id in self.gate_ids
                              if self.zone_of_gate.get(gate_id, '') == zone_id
                              and self.priced_at_gate.get(gate_id, 0) > 0]
            zone_reports[zone_id] = {
                'partition_kind': 'zone',
                'partition_id': zone_id,
                'epoch_id': self.epoch_id,
                'operator_id': self.zones[zone_id].get('operator_id', ''),
                'taps_priced': zone_priced.get(zone_id, 0),
                'taps_withdrawn': zone_withdrawn.get(zone_id, 0),
                'charge_micros': zone_charge.get(zone_id, 0),
                'priced_distance_units': zone_distance.get(zone_id, 0),
                'revenue_cap_micros': self.zones[zone_id].get('revenue_cap_micros', 0),
                'effective_cap_micros': self.effective_cap.get(zone_id, 0),
                'gates_in_scope': gates_in_scope,
                'cap_infeasible': zone_id in cap_infeasible,
            }

        netting = {
            'summary': {
                'epoch_id': self.epoch_id,
                'interchange_share_bp': self.interchange_share_bp,
                'obligation_total_micros': self.obligation_total,
                'residual_total_micros': self.residual_total,
                'cancelled_cycle_count': len(self.cycles),
                'cancelled_total_micros': self.cancelled_total,
                'net_position_total_micros': sum(self.net_position.values()),
                'netting_digest': self.netting_digest,
                'funded_edge_count': sum(1 for row in self.schedule if row['state'] == 'funded'),
                'deferred_edge_count': sum(1 for row in self.schedule if row['state'] == 'deferred'),
                'funded_total_micros': sum(row['amount_micros'] for row in self.schedule
                                           if row['state'] == 'funded'),
                'deferred_total_micros': sum(row['amount_micros'] for row in self.schedule
                                             if row['state'] == 'deferred'),
            },
            'obligations': {
                'edges': [{'payer': payer, 'payee': payee,
                           'amount_micros': self.obligations[(payer, payee)],
                           'tap_count': self.obligation_counts[(payer, payee)]}
                          for payer, payee in sorted(self.obligations)],
                'total_micros': self.obligation_total,
            },
            'residual': {
                'edges': [{'payer': payer, 'payee': payee, 'amount_micros': amount}
                          for (payer, payee), amount in sorted(self.residual_edges.items())],
                'cycles': [{'sequence': list(row['sequence']),
                            'amount_micros': row['amount_micros']}
                           for row in self.cycles],
                'total_micros': self.residual_total,
            },
            'positions': {
                'positions': [{'operator_id': operator_id,
                                'gross_out_micros': self.gross_out[operator_id],
                                'gross_in_micros': self.gross_in[operator_id],
                                'residual_out_micros': self.residual_out[operator_id],
                                'residual_in_micros': self.residual_in[operator_id],
                                'net_position_micros': self.net_position[operator_id]}
                               for operator_id in self.operator_ids],
                'net_total_micros': sum(self.net_position.values()),
            },
            'schedule': {
                'rows': self.schedule,
                'funding_ceilings': [{'operator_id': operator_id,
                                      'funding_ceiling_micros':
                                          self.operators[operator_id].get('funding_ceiling_micros', 0),
                                      'funded_micros': self.funded[operator_id]}
                                     for operator_id in self.operator_ids],
            },
        }

        margins = sorted((dict(row, held_back=row['held_back']) for row in self.sample),
                         key=lambda row: row['tap_id'])
        assurance = {
            'summary': {
                'epoch_id': self.epoch_id,
                'assurance_sigma': self.assurance_sigma,
                'assurance_modulus': self.assurance_modulus,
                'min_sample': self.min_sample,
                'sample_size': self.sample_size,
                'median_margin': self.median_margin,
                'mad': self.mad,
                'threshold': self.threshold,
                'retained_count': len(self.retained),
                'held_back_count': len(self.held_back),
                'pool_micros': self.pool,
                'assurance_digest': self.assurance_digest,
                'priced_distance_units': priced_distance,
                'zero_distance_taps': sorted(self.zero_distance_priced),
            },
            'margins': {'rows': margins, 'row_count': len(margins)},
            'holdbacks': {
                'rows': [{'tap_id': row['tap_id'], 'margin': row['margin'],
                          'median_margin': self.median_margin,
                          'deviation': row['deviation'], 'threshold': self.threshold}
                         for row in sorted(self.held_back, key=lambda row: row['tap_id'])],
                'row_count': len(self.held_back),
            },
            'order': {'tap_ids': self.digest_tap_ids, 'margins': self.digest_margins,
                      'digest': self.assurance_digest},
            'apportionment': {
                'retained_distance_units': self.retained_distance,
                'shares': [{'rider_class': rider_class,
                            'retained_margin_micros': sum(row['margin'] for row in self.retained
                                                          if row['rider_class'] == rider_class),
                            'share_units': self.shares.get(rider_class, 0)}
                           for rider_class in self.share_classes],
                'share_total_units': sum(self.shares.values()),
            },
        }

        ladder = []
        for rider_class in sorted({row['rider_class'] for row in self.sample}):
            retained = [row for row in self.retained if row['rider_class'] == rider_class]
            held = [row for row in self.held_back if row['rider_class'] == rider_class]
            ladder.append({'rider_class': rider_class,
                          'retained_count': len(retained),
                          'held_back_count': len(held),
                          'margin_total': sum(row['margin'] for row in retained),
                          'share_units': self.shares.get(rider_class, 0)})

        return {
            'summary': summary,
            'reconciliation': reconciliation,
            'ledger': {'rows': rows, 'row_count': len(rows), 'charge_micros': charge},
            'quality': quality,
            'identity': identity_register,
            'suspension': suspension_register,
            'cap_relief': cap_relief,
            'operator_reports': operator_reports,
            'zone_reports': zone_reports,
            'netting': netting,
            'assurance': assurance,
            'ladder': ladder,
            'cycles': self.cycles,
        }


# ------------------------------------------------------- parameter recovery

PROPERTY_ORDER = ('adjustment_order', 'levy_basis', 'grid_step_micros',
                  'midpoint_rule', 'void_reach', 'cap_release_order',
                  'fault_window_edge')


def published_figures(result):
    """The figures the calibration slice publishes, taken from a clearance."""
    summary = result['summary']
    fares = {row['tap_id']: row['unit_fare_micros'] for row in result['ledger']['rows']
             if row['disposition'] == 'priced'}
    curtailed = sorted(tap_id for zone in result['cap_relief']['zones']
                       for tap_id in zone['curtailed_tap_ids'])
    return {
        'epoch_charge_micros': summary['epoch_charge_micros'],
        'taps_priced': summary['taps_priced'],
        'taps_withdrawn': summary['taps_withdrawn'],
        'priced_distance_units': summary['priced_distance_units'],
        'unit_fare_checks': fares,
        'suspended_gates': summary['suspended_gates'],
        'curtailed_tap_ids': curtailed,
        'loan_total_micros': result['cap_relief']['loan_total_micros'],
        'loans': [[row['from_zone'], row['to_zone'], row['amount_micros']]
                  for row in result['cap_relief']['loans']],
        'netting_digest': result['netting']['summary']['netting_digest'],
        'assurance_pool_micros': result['assurance']['summary']['pool_micros'],
        'assurance_digest': result['assurance']['summary']['assurance_digest'],
    }


def _pricing_signature(registers, params, identity_cache):
    """Fares of the slice's taps under a candidate reading of the tariff."""
    epoch = Epoch.__new__(Epoch)
    epoch.registers = registers
    epoch.params = params
    epoch._lay_out()
    epoch.peak = {tap['key']: epoch.is_peak(tap['tapped_at']) for tap in epoch.taps}
    epoch.place = make_place(params['grid_step_micros'], params['midpoint_rule'])
    fares = {}
    for tap in identity_cache['admitted']:
        key = tap['key']
        if identity_cache['outcome'][key] not in ('direct', 'rotated', 'cycle_broken'):
            continue
        table = epoch.governing_table(tap['tapped_at'])
        if table is None:
            continue
        gate = epoch.gates.get(tap['gate_id'], {})
        zone = epoch.zones.get(epoch.zone_of_gate.get(tap['gate_id'], ''), {})
        cross = (epoch.operator_of_gate.get(tap['gate_id'], '') !=
                 identity_cache['home'][key])
        fares[tap['tap_id']] = epoch._fare(tap, table, gate, zone, cross)[1]
    return fares


def recover_parameters(directory):
    """Recover the seven properties from the calibration slice."""
    controls = load_calibration(directory)
    if controls is None:
        raise SystemExit('no calibration material in %s' % directory)
    legal = controls['legal_values']
    names = list(controls.get('property_names') or PROPERTY_ORDER)
    for name in PROPERTY_ORDER:
        if name not in legal:
            raise SystemExit('calibration material lacks %s' % name)
    published = controls['published']
    slice_registers = calibration_registers(controls)

    # Identity is independent of every recovered property: resolve it once.
    probe = {'adjustment_order': ['fault_abatement'], 'levy_basis': 'running_value',
             'grid_step_micros': 1, 'midpoint_rule': 'away_from_zero',
             'void_reach': 'tap_only', 'cap_release_order': 'ascending_zone_id',
             'fault_window_edge': 'closed_open'}
    base = Epoch(slice_registers, probe)
    identity_cache = {
        'admitted': base.admitted,
        'outcome': base.outcome,
        'home': {tap['key']: base.home_operator.get(base.canonical[tap['key']], '')
                 for tap in base.admitted},
    }
    upheld = {row['tap_id'] for row in slice_registers['exceptions']
              if row['status'] == 'upheld'}
    checks = {tap_id: fare for tap_id, fare in published['unit_fare_checks'].items()
              if tap_id not in upheld}

    # Stage one: the published fares pin down the tariff reading.  Identity
    # depends on none of the seven properties, and neither does the fare of a
    # tap, so any reading that reproduces every published figure must first
    # reproduce the published unit fares.  An upheld exception replaces the
    # fare of the tap it names, so those taps say nothing about the tariff.
    pricing = []
    for step in legal['grid_step_micros']:
        for rule in legal['midpoint_rule']:
            for order in legal['adjustment_order']:
                for basis in legal['levy_basis']:
                    for edge in legal['fault_window_edge']:
                        candidate = dict(probe)
                        candidate['adjustment_order'] = list(order)
                        candidate['levy_basis'] = basis
                        candidate['grid_step_micros'] = step
                        candidate['midpoint_rule'] = rule
                        candidate['fault_window_edge'] = edge
                        fares = _pricing_signature(slice_registers, candidate, identity_cache)
                        if all(fares.get(tap_id) == fare for tap_id, fare in checks.items()):
                            pricing.append(candidate)
    if not pricing:
        raise SystemExit('no tariff reading reproduces the calibration fares')

    # Stage two: the reversal reach and the cap release order follow from the
    # rest of the published figures.
    survivors = []
    for candidate in pricing:
        for reach in legal['void_reach']:
            for release in legal['cap_release_order']:
                full = dict(candidate)
                full['void_reach'] = reach
                full['cap_release_order'] = release
                result = Epoch(slice_registers, full).build()
                figures = published_figures(result)
                if all(figures.get(key) == value for key, value in published.items()):
                    survivors.append(full)
    if len(survivors) != 1:
        raise SystemExit('%d readings of the seven properties reproduce the slice'
                         % len(survivors))
    best = survivors[0]
    return {name: best[name] for name in names}


# ---------------------------------------------------------------- output

def write_json(path, document):
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(json.dumps(document, indent=2, sort_keys=True))
        handle.write('\n')


def write_csv(path, header, rows):
    with open(path, 'w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle, lineterminator='\n')
        writer.writerow(header)
        for row in rows:
            writer.writerow(row)


def clear(register_directory, output_directory):
    params = recover_parameters(register_directory)
    registers = load_registers(register_directory)
    result = Epoch(registers, params).build()

    if not os.path.isdir(output_directory):
        os.makedirs(output_directory)
    write_json(os.path.join(output_directory, 'summary.json'), result['summary'])
    write_json(os.path.join(output_directory, 'reconciliation.json'), result['reconciliation'])
    write_json(os.path.join(output_directory, 'tap_ledger.json'), result['ledger'])
    write_json(os.path.join(output_directory, 'data_quality.json'), result['quality'])
    write_json(os.path.join(output_directory, 'identity_register.json'), result['identity'])
    write_json(os.path.join(output_directory, 'suspension_register.json'), result['suspension'])
    write_json(os.path.join(output_directory, 'cap_relief.json'), result['cap_relief'])

    for operator_id, report in sorted(result['operator_reports'].items()):
        write_json(os.path.join(output_directory, 'operator_%s.json' % operator_id), report)
    for zone_id, report in sorted(result['zone_reports'].items()):
        write_json(os.path.join(output_directory, 'zone_%s.json' % zone_id), report)

    write_json(os.path.join(output_directory, 'netting_summary.json'), result['netting']['summary'])
    write_json(os.path.join(output_directory, 'netting_obligations.json'), result['netting']['obligations'])
    write_json(os.path.join(output_directory, 'netting_residual.json'), result['netting']['residual'])
    write_json(os.path.join(output_directory, 'netting_positions.json'), result['netting']['positions'])
    write_json(os.path.join(output_directory, 'netting_schedule.json'), result['netting']['schedule'])
    write_csv(os.path.join(output_directory, 'netting_cycles.csv'),
              ['cycle_index', 'sequence', 'amount_micros'],
              [[index + 1, '>'.join(row['sequence']), row['amount_micros']]
               for index, row in enumerate(result['cycles'])])

    write_json(os.path.join(output_directory, 'assurance_summary.json'), result['assurance']['summary'])
    write_json(os.path.join(output_directory, 'assurance_margins.json'), result['assurance']['margins'])
    write_json(os.path.join(output_directory, 'assurance_holdbacks.json'), result['assurance']['holdbacks'])
    write_json(os.path.join(output_directory, 'assurance_order.json'), result['assurance']['order'])
    write_json(os.path.join(output_directory, 'assurance_apportionment.json'),
               result['assurance']['apportionment'])
    write_csv(os.path.join(output_directory, 'assurance_ladder.csv'),
              ['rider_class', 'retained_count', 'held_back_count', 'margin_total', 'share_units'],
              [[row['rider_class'], row['retained_count'], row['held_back_count'],
                row['margin_total'], row['share_units']] for row in result['ladder']])
    return result


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: clear_epoch.py <register_directory> <output_directory>\n')
        return 2
    clear(argv[1], argv[2])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))

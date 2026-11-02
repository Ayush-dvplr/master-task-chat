#!/usr/bin/env python3
"""Standalone replay of the reminder scope surface.

Rebuilds the surface the change ledger describes, under the ordering key the
scope authority policy defines, from the evidence in the directory named by
--input, and writes reproduced_state.json into the directory named by --out.

Only the standard library is imported and only files inside --input are read.
"""

import argparse
import csv
import hashlib
import io
import itertools
import json
import os
import re
import sqlite3
import zipfile
from urllib.request import pathname2url

INT_FIELDS = ('seq', 'value', 'authority_rank', 'effective_generation')
FOLD_LABELS = {'breaking': 'major', 'additive': 'minor', 'internal': 'patch'}


# ---------------------------------------------------------------- text helpers

def read_text(path):
    with open(path, 'rb') as handle:
        data = handle.read()
    if data.startswith(b'\xef\xbb\xbf'):
        data = data[3:]
    return data.decode('utf-8')


def strip_tags(xml):
    return re.sub(r'<[^>]+>', '', xml)


def docx_text(path):
    with zipfile.ZipFile(path) as archive:
        return strip_tags(archive.read('word/document.xml').decode('utf-8'))


# --------------------------------------------------------------- evidence load

def load_ledger(evidence_dir):
    """Every record of every shard directly inside ledger/, keyed by record sequence.

    A record sequence re-exported in more than one shard is read from the shard
    whose file name sorts last; the earlier copies are ignored.
    """
    ledger_dir = os.path.join(evidence_dir, 'ledger')
    records = {}
    names = sorted(name for name in os.listdir(ledger_dir)
                   if name.startswith('shard_')
                   and os.path.isfile(os.path.join(ledger_dir, name)))
    for name in names:
        path = os.path.join(ledger_dir, name)
        text = read_text(path)
        if name.endswith('.ndjson'):
            rows = [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            delimiter = ',' if name.endswith('.csv') else '|'
            rows = [{key.strip(): value for key, value in row.items()}
                    for row in csv.DictReader(io.StringIO(text), delimiter=delimiter)]
        for row in rows:
            record = dict(row)
            for field in INT_FIELDS:
                record[field] = int(record[field])
            records[record['seq']] = record
    return records


def load_journal(evidence_dir):
    path = os.path.abspath(os.path.join(evidence_dir, 'release_ops.sqlite'))
    uri = 'file:' + pathname2url(path) + '?mode=ro'
    connection = sqlite3.connect(uri, uri=True)
    try:
        cursor = connection.execute(
            'SELECT line_no, op, scope, record_seq, retired_anchor, surviving_anchor, status '
            'FROM journal ORDER BY line_no')
        names = [column[0] for column in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]
    finally:
        connection.close()


def load_restricted_map(evidence_dir):
    path = os.path.join(evidence_dir, 'restricted_scope_map.xlsx')
    with zipfile.ZipFile(path) as archive:
        workbook = archive.read('xl/workbook.xml').decode('utf-8')
        rels = archive.read('xl/_rels/workbook.xml.rels').decode('utf-8')
        targets = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels))
        sheet = None
        for name, rel_id in re.findall(r'<sheet name="([^"]+)"[^>]*r:id="([^"]+)"', workbook):
            if name.startswith('active_'):
                sheet = targets[rel_id]
        if sheet is None:
            raise SystemExit('restricted scope map holds no active_ sheet')
        shared = [strip_tags(item) for item in
                  re.findall(r'<si>(.*?)</si>',
                             archive.read('xl/sharedStrings.xml').decode('utf-8'), re.S)]
        xml = archive.read('xl/' + sheet).decode('utf-8')
    rows = []
    for row_match in re.finditer(r'<row[^>]*>(.*?)</row>', xml, re.S):
        cells = []
        for cell in re.finditer(r'<c ([^>]*)>(.*?)</c>', row_match.group(1), re.S):
            attrs, body = cell.group(1), cell.group(2)
            kind = re.search(r't="([^"]*)"', attrs)
            value_match = re.search(r'<v>(.*?)</v>', body, re.S)
            value = value_match.group(1) if value_match else ''
            if kind and kind.group(1) == 's':
                value = shared[int(value)]
            cells.append(value)
        rows.append(cells)
    header = rows[0]
    table = []
    for cells in rows[1:]:
        row = dict(zip(header, cells))
        row['alt_key'] = int(row['alt_key'])
        row['canonical_value'] = int(row['canonical_value'])
        table.append(row)
    return table


def load_catalogue(evidence_dir):
    return json.loads(read_text(os.path.join(evidence_dir, 'urgency_class_catalogue.json')))


def load_addenda(evidence_dir):
    addenda = []
    for name in sorted(os.listdir(evidence_dir)):
        match = re.fullmatch(r'policy_addendum_A(\d+)\.docx', name)
        if match and os.path.isfile(os.path.join(evidence_dir, name)):
            addenda.append((int(match.group(1)), docx_text(os.path.join(evidence_dir, name))))
    addenda.sort(key=lambda item: item[0])
    return addenda


def published_parameters(addenda):
    """Read the deprecation window and the urgency weights an addendum publishes.

    The highest numbered addendum that addresses a parameter governs it. A
    parameter that no addendum publishes, or that the highest addendum declares
    recovered, is recovered from the calibration controls.
    """
    window = None
    weights = None
    for _, text in addenda:
        lowered = text.lower()
        recovered = ('recovered from the calibration' in lowered
                     or 'is recovered' in lowered
                     or 'are recovered' in lowered
                     or 'published nowhere' in lowered)
        if 'deprecation window' in lowered:
            if recovered:
                window = None
            else:
                match = re.search(r'deprecation window is (\d+) generations', lowered)
                if match:
                    window = int(match.group(1))
        if 'urgency weight' in lowered:
            if recovered:
                weights = None
            else:
                match = re.search(r'breaking[^\d]{0,40}(\d+)[^\d]{0,40}additive[^\d]{0,40}(\d+)'
                                  r'[^\d]{0,40}internal[^\d]{0,40}(\d+)', lowered)
                if match:
                    weights = {'breaking': int(match.group(1)),
                               'additive': int(match.group(2)),
                               'internal': int(match.group(3))}
    return window, weights


# -------------------------------------------------------------- journal folding

def journal_view(journal):
    return [row for row in journal if row['status'] != 'rejected']


def admission(journal):
    """Inert journal reasons, keyed by record sequence.

    A record is rolled back by any non rejected rollback_change naming it, and
    is inert with apply_change_rejected when every apply_change naming it,
    rejected or not, was refused.
    """
    rolled_back = set()
    apply_ops = {}
    for row in journal:
        if row['op'] == 'rollback_change':
            if row['status'] != 'rejected':
                rolled_back.add(row['record_seq'])
        elif row['op'] == 'apply_change':
            apply_ops.setdefault(row['record_seq'], []).append(row)
    inert = {}
    for seq in sorted(rolled_back):
        inert[seq] = 'rolled_back'
    for seq in sorted(apply_ops):
        if seq in inert:
            continue
        if all(op['status'] == 'rejected' for op in apply_ops[seq]):
            inert[seq] = 'apply_change_rejected'
    return inert


def settle_anchors(journal):
    """Per scope: the anchor a pending record resolves to, and superseded anchors.

    Only journal operations the release desk has not refused take part, and the
    surviving anchor of the last of them in journal line order settles the
    scope. A refused supersede settles nothing, wherever it sits.
    """
    surviving = {}
    superseded = {}
    for row in journal_view(journal):
        if row['op'] != 'supersede_anchor':
            continue
        scope = row['scope']
        superseded.setdefault(scope, set()).add(row['retired_anchor'])
        surviving[scope] = row['surviving_anchor']
    return surviving, superseded


def resolve_anchor(record, surviving, superseded):
    anchor = record['lineage_anchor']
    scope = record['scope']
    if anchor == 'pending' or anchor in superseded.get(scope, set()):
        return surviving.get(scope)
    return anchor


# ------------------------------------------------------------------ the replay

def resolve_value(record, anchor, restricted_map):
    if record['reference_domain'] != 'restricted_scope_index':
        return record['value']
    for row in restricted_map:
        if row['alt_key'] == record['value'] and row['lineage_anchor'] == anchor:
            return row['canonical_value']
    raise SystemExit('restricted reference %s of %s does not resolve under anchor %s'
                     % (record['value'], record['scope'], anchor))


def fold(version, class_name):
    label = FOLD_LABELS.get(class_name)
    if label == 'major':
        return [version[0] + 1, 0, 0]
    if label == 'minor':
        return [version[0], version[1] + 1, 0]
    if label == 'patch':
        return [version[0], version[1], version[2] + 1]
    raise SystemExit('unknown urgency class ' + repr(class_name))


def ordered(records, ordering_key):
    if ordering_key == 'effective_generation,seq':
        return sorted(records, key=lambda record: (record['effective_generation'], record['seq']))
    return sorted(records, key=lambda record: record['seq'])


def replay(records, journal, restricted_map, window, ordering_key):
    """Apply the whole ledger under one ordering key. Returns a state bundle."""
    admitted_inert = admission(journal)
    surviving, superseded = settle_anchors(journal)
    active = {}
    retired = []
    deprecations = {}
    effective = []
    inert = []
    revisited = []
    version = [0, 0, 0]
    for record in ordered(records, ordering_key):
        seq = record['seq']
        scope = record['scope']
        anchor = resolve_anchor(record, surviving, superseded)
        value = resolve_value(record, anchor, restricted_map)
        reason = admitted_inert.get(seq)
        if reason is None:
            operation = record['op']
            open_deprecations = deprecations.get(scope, [])
            if operation == 'publish':
                if scope in active or scope in retired:
                    reason = 'publish_names_known_scope'
                else:
                    active[scope] = value
            elif operation == 'revise':
                if scope not in active:
                    reason = 'revise_names_inactive_scope'
                elif active[scope] == value:
                    reason = 'revise_keeps_value'
                else:
                    active[scope] = value
            elif operation == 'deprecate':
                if scope not in active:
                    reason = 'deprecate_names_inactive_scope'
                else:
                    open_deprecations.append((record['effective_generation'], record['authority_rank']))
                    deprecations[scope] = open_deprecations
            elif operation == 'restore':
                if scope not in active or not open_deprecations:
                    reason = 'restore_without_open_deprecation'
                elif record['authority_rank'] < open_deprecations[-1][1]:
                    reason = 'restore_rank_below_deprecation'
                else:
                    open_deprecations.pop()
            elif operation == 'withdraw':
                if scope not in active:
                    reason = 'withdraw_names_inactive_scope'
                else:
                    del active[scope]
                    retired.append(scope)
                    deprecations.pop(scope, None)
            else:
                raise SystemExit('unknown ledger operation ' + operation)
        if reason is None:
            effective.append(record)
            version = fold(version, record['urgency_class'])
            if record['reference_domain'] == 'restricted_scope_index':
                revisited.append({'seq': seq, 'scope': scope,
                                  'lineage_anchor': anchor, 'canonical_value': value})
        else:
            inert.append({'seq': seq, 'reason': reason})
    generation = max(record['effective_generation'] for record in records)
    overdue = sorted(((stack[-1][0], scope) for scope, stack in deprecations.items()
                      if stack and scope in active and generation - stack[-1][0] >= window),
                     key=lambda item: (item[0], item[1]))
    for _, scope in overdue:
        del active[scope]
        retired.append(scope)
    return {
        'generation': generation,
        'active': active,
        'retired': retired,
        'effective': effective,
        'inert': sorted(inert, key=lambda item: item['seq']),
        'revisited': revisited,
        'version': version,
        'window_retired': [scope for _, scope in overdue],
        'surviving': surviving,
        'superseded': superseded,
    }


def surface_digest(surface):
    payload = json.dumps(surface, sort_keys=True, separators=(',', ':'))
    return hashlib.blake2b(payload.encode('utf-8'), digest_size=8).hexdigest()


def version_string(version):
    return '%d.%d.%d' % tuple(version)


# ------------------------------------------------------- parameter recovery

def control_retired(records, window):
    """A control replayed with no journal, under the authority ordering."""
    active = {}
    retired = []
    deprecations = {}
    for record in ordered(records, 'effective_generation,seq'):
        scope = record['scope']
        operation = record['op']
        stack = deprecations.get(scope, [])
        if operation == 'publish':
            if scope not in active and scope not in retired:
                active[scope] = record['value']
        elif operation == 'revise':
            if scope in active and active[scope] != record['value']:
                active[scope] = record['value']
        elif operation == 'deprecate':
            if scope in active:
                stack.append((record['effective_generation'], record['authority_rank']))
                deprecations[scope] = stack
        elif operation == 'restore':
            if scope in active and stack and record['authority_rank'] >= stack[-1][1]:
                stack.pop()
        elif operation == 'withdraw':
            if scope in active:
                del active[scope]
                retired.append(scope)
                deprecations.pop(scope, None)
    generation = max(record['effective_generation'] for record in records)
    overdue = sorted(((stack[-1][0], scope) for scope, stack in deprecations.items()
                      if stack and scope in active and generation - stack[-1][0] >= window),
                     key=lambda item: (item[0], item[1]))
    for _, scope in overdue:
        del active[scope]
        retired.append(scope)
    return retired


def tie_break_order(class_names):
    order = [name for name in ('breaking', 'additive', 'internal') if name in class_names]
    return order + [name for name in class_names if name not in order]


def recover_parameters(evidence_dir, classes):
    """Recover the deprecation window and the urgency weights from calibration."""
    text = read_text(os.path.join(evidence_dir, 'calibration', 'published_controls.psv'))
    controls = []
    for row in csv.DictReader(io.StringIO(text), delimiter='|'):
        row['retired'] = [name for name in row['retired_scopes'].split(';') if name != '-']
        row['total'] = int(row['urgency_grand_total'])
        path = os.path.join(evidence_dir, 'calibration', row['control'] + '.ndjson')
        row['records'] = [json.loads(line) for line in read_text(path).splitlines() if line.strip()]
        controls.append(row)
    fitting = []
    for window in range(2, 31):
        if not all(control_retired(row['records'], window) == row['retired'] for row in controls):
            continue
        counts = []
        for row in controls:
            counts.append([sum(1 for record in row['records']
                                if record['urgency_class'] == name) for name in classes])
        for values in _weight_candidates(counts, [row['total'] for row in controls]):
            weights = dict(zip(classes, values))
            fitting.append((window, weights))
    if not fitting:
        raise SystemExit('no deprecation window and urgency weights fit the calibration controls')
    order = tie_break_order(classes)
    return max(fitting, key=lambda item: (item[0],) + tuple(item[1][name] for name in order))


def _weight_candidates(counts, totals):
    """Yield integer weight vectors, 1..99, that satisfy every control total."""
    if not counts:
        return
    size = len(counts[0])
    for values in itertools.product(range(1, 100), repeat=size):
        if all(sum(a * b for a, b in zip(values, row)) == total
               for row, total in zip(counts, totals)):
            yield values


# --------------------------------------------------------------------- driver

def build_state(evidence_dir):
    records = load_ledger(evidence_dir)
    journal = load_journal(evidence_dir)
    restricted_map = load_restricted_map(evidence_dir)
    catalogue = load_catalogue(evidence_dir)
    addenda = load_addenda(evidence_dir)
    classes = [entry['name'] for entry in catalogue['classes']]
    window, weights = published_parameters(addenda)
    if window is None or weights is None:
        recovered_window, recovered_weights = recover_parameters(evidence_dir, classes)
        if window is None:
            window = recovered_window
        if weights is None:
            weights = recovered_weights
    ledger = list(records.values())
    authority = replay(ledger, journal, restricted_map, window, 'effective_generation,seq')
    control = replay(ledger, journal, restricted_map, window, 'seq')
    totals = {}
    for name in classes:
        totals[name] = sum(weights[record['urgency_class']]
                           for record in ledger if record['urgency_class'] == name)
    return {
        'authority': authority,
        'control': control,
        'window': window,
        'weights': weights,
        'classes': classes,
        'catalogue': catalogue,
        'records': records,
        'totals': totals,
    }


def first_divergent_seq(records):
    """Record sequence the authority ordering places at the first differing position."""
    authority = ordered(records, 'effective_generation,seq')
    control = ordered(records, 'seq')
    for left, right in zip(authority, control):
        if left['seq'] != right['seq']:
            return left['seq']
    return None


def main():
    parser = argparse.ArgumentParser(description='replay the scope surface from evidence')
    parser.add_argument('--input', required=True, help='directory holding the evidence')
    parser.add_argument('--out', required=True, help='directory to write reproduced_state.json into')
    args = parser.parse_args()
    evidence_dir = os.path.abspath(args.input)
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)
    state = build_state(evidence_dir)
    authority = state['authority']
    control = state['control']
    payload = {
        'surface_digest': surface_digest(authority['active']),
        'generation': authority['generation'],
        'release_version': version_string(authority['version']),
        'control_digest': surface_digest(control['active']),
        'active_scopes': authority['active'],
        'retired_scopes': authority['retired'],
        'deprecation_window': state['window'],
        'urgency_weights': state['weights'],
    }
    text = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + '\n'
    with open(os.path.join(out_dir, 'reproduced_state.json'), 'wb') as handle:
        handle.write(text.replace('\r\n', '\n').encode('utf-8'))


if __name__ == '__main__':
    main()

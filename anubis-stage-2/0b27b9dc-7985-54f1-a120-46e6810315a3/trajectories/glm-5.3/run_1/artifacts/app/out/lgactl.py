#!/usr/bin/env python3
"""lgactl: least grant admission control solver.

Usage: lgactl.py CORPUS_DIR OUT_DIR

Reads the corpus of record files under CORPUS_DIR, replays the recorded
population of runs against the shipped four layer policy, settles the least
grant plan, and writes the twenty four data artifacts plus this program into
OUT_DIR. Standard library only; no network access.
"""

import csv
import hashlib
import json
import os
import re
import sys
import unicodedata

PHASES = ('auth', 'account', 'session')
PAM_CODES = ('success', 'ignore', 'auth_err', 'user_unknown', 'perm_denied',
             'maxtries', 'cred_insufficient', 'abort', 'service_err')
ARCHES = ('x86_64', 'i386', 'aarch64')
ACTION_RANK = {'KILL_PROCESS': 1, 'KILL_THREAD': 2, 'TRAP': 3, 'ERRNO': 4,
               'USER_NOTIF': 5, 'TRACE': 6, 'LOG': 7, 'ALLOW': 8}
REFUSING_ACTIONS = ('KILL_PROCESS', 'KILL_THREAD', 'TRAP', 'USER_NOTIF', 'TRACE')
LAYER_RANK = {'pam': 1, 'selinux': 2, 'capability': 3, 'seccomp': 4, 'NONE': 9}
CAPABILITY_TABLE = (
    'CAP_CHOWN', 'CAP_DAC_OVERRIDE', 'CAP_DAC_READ_SEARCH', 'CAP_FOWNER',
    'CAP_FSETID', 'CAP_KILL', 'CAP_SETGID', 'CAP_SETUID', 'CAP_SETPCAP',
    'CAP_LINUX_IMMUTABLE', 'CAP_NET_BIND_SERVICE', 'CAP_NET_BROADCAST',
    'CAP_NET_ADMIN', 'CAP_NET_RAW', 'CAP_IPC_LOCK', 'CAP_IPC_OWNER',
    'CAP_SYS_MODULE', 'CAP_SYS_RAWIO', 'CAP_SYS_CHROOT', 'CAP_SYS_PTRACE',
    'CAP_SYS_PACCT', 'CAP_SYS_ADMIN', 'CAP_SYS_BOOT', 'CAP_SYS_NICE',
    'CAP_SYS_RESOURCE', 'CAP_SYS_TIME', 'CAP_SYS_TTY_CONFIG', 'CAP_MKNOD',
    'CAP_LEASE', 'CAP_AUDIT_WRITE', 'CAP_AUDIT_CONTROL', 'CAP_SETFCAP',
    'CAP_MAC_OVERRIDE', 'CAP_MAC_ADMIN', 'CAP_SYSLOG', 'CAP_WAKE_ALARM',
    'CAP_BLOCK_SUSPEND', 'CAP_AUDIT_READ', 'CAP_PERFMON', 'CAP_BPF',
    'CAP_CHECKPOINT_RESTORE')
CAP_BIT = {name: bit for bit, name in enumerate(CAPABILITY_TABLE)}
ADVISORY_CAPABILITY = 'CAP_AUDIT_WRITE'
ROUND_CAP = 8

ARTIFACT_ORDER = (
    'principal_registry.jsonl', 'syscall_index.tsv', 'pam_stack_resolved.csv',
    'selinux_type_graph.json', 'seccomp_program.jsonl', 'pam_verdicts.csv',
    'capability_ledger.csv', 'domain_transitions.tsv',
    'seccomp_decisions.jsonl', 'arch_dispatch.tsv', 'admission_ledger.csv',
    'denial_attribution.jsonl', 'blocked_syscalls.tsv',
    'capability_gaps.csv', 'audit_continuity.jsonl',
    'relaxation_atoms.csv', 'forbidden_atoms.tsv', 'grant_plan.csv',
    'iteration_trace.jsonl', 'minimality_witness.csv',
    'residual_denials.tsv', 'conservation.json', 'summary.json')

REQUIRED_GROUPS = ('runs-trace', 'selinux-allow', 'cap-units', 'grant-atoms')


# ---------------------------------------------------------------------------
# canonical forms
# ---------------------------------------------------------------------------

def canon_id(value):
    """Canonical identifier form: upper case, underscores and full stops as hyphens."""
    return unicodedata.normalize('NFC', value).upper().replace('_', '-').replace('.', '-')


def canon_type(value):
    """Canonical SELinux type name: lower case, hyphens and full stops as underscores."""
    return unicodedata.normalize('NFC', value).lower().replace('-', '_').replace('.', '_')


def canon_cap(value):
    """Canonical capability name from a name or a decimal bit index, or None."""
    text = unicodedata.normalize('NFC', value).strip()
    if not text:
        return None
    upper = text.upper()
    if upper in CAP_BIT:
        return upper
    lower = 'cap_' + upper[4:] if upper.startswith('CAP') else None
    if lower and lower in CAP_BIT:
        return lower
    if text.isdigit():
        bit = int(text)
        if 0 <= bit < len(CAPABILITY_TABLE):
            return CAPABILITY_TABLE[bit]
    return None


def read_cap_set(value):
    """Read a plus (or comma) separated capability set into a frozenset of names."""
    text = unicodedata.normalize('NFC', value).strip()
    if not text or text.lower() == 'none':
        return frozenset()
    members = []
    for part in re.split(r'[+,]', text):
        part = part.strip()
        if not part:
            continue
        name = canon_cap(part)
        if name is not None:
            members.append(name)
    return frozenset(members)


def write_cap_set(capset):
    if not capset:
        return 'NONE'
    return '+'.join(sorted(capset, key=lambda name: CAP_BIT[name]))


# ---------------------------------------------------------------------------
# corpus reading
# ---------------------------------------------------------------------------

def _split_lines(text):
    """Return the logical lines of a corpus file, BOM and line endings stripped."""
    if text.startswith('\ufeff'):
        text = text[1:]
    lines = text.split('\n')
    out = []
    for line in lines:
        if line.endswith('\r'):
            line = line[:-1]
        out.append(line)
    return out


def _is_blank(line):
    return not line.strip()


def _parse_delimited(line, sep):
    """Parse one delimited record, honouring the quoting rule of the encodings."""
    fields = []
    index = 0
    length = len(line)
    while True:
        if index < length and line[index] == '"':
            value = []
            index += 1
            while index < length:
                char = line[index]
                if char == '"':
                    if index + 1 < length and line[index + 1] == '"':
                        value.append('"')
                        index += 2
                    else:
                        index += 1
                        break
                else:
                    value.append(char)
                    index += 1
            fields.append(''.join(value))
        else:
            end = line.find(sep, index)
            if end < 0:
                end = length
            fields.append(line[index:end])
            index = end
        if index < length:
            index += 1
        else:
            break
    return fields


def _parse_fixed_header(line):
    widths = []
    for element in line.split(';'):
        name, _, width = element.partition(':')
        widths.append((name, int(width)))
    return widths


def _read_delimited(path, sep):
    lines = _split_lines(open_bytes(path))
    header = None
    records = []
    for line in lines:
        if _is_blank(line):
            continue
        fields = _parse_delimited(line, sep)
        if header is None:
            header = fields
            continue
        row = {}
        for position, name in enumerate(header):
            row[name] = fields[position] if position < len(fields) else ''
        records.append(row)
    return records


def _read_fixed(path):
    lines = _split_lines(open_bytes(path))
    widths = None
    records = []
    for line in lines:
        if _is_blank(line):
            continue
        if widths is None:
            widths = _parse_fixed_header(line)
            continue
        row = {}
        position = 0
        for name, width in widths:
            row[name] = line[position:position + width].rstrip()
            position += width
        records.append(row)
    return records


def _read_json(path):
    data = json.loads(open_bytes(path))
    return [dict(record) for record in data.get('records', [])]


def _read_jsonl(path):
    records = []
    for line in _split_lines(open_bytes(path)):
        if _is_blank(line):
            continue
        records.append(json.loads(line))
    return records


def _read_toml(path):
    records = []
    current = None
    for line in _split_lines(open_bytes(path)):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        if stripped == '[[record]]':
            if current is not None:
                records.append(current)
            current = {}
            continue
        if current is not None and '=' in stripped:
            name, _, value = stripped.partition('=')
            value = value.strip()
            if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
                value = value[1:-1].replace('\\\\', '\\').replace('\\"', '"')
            current[name.strip()] = value
    if current is not None:
        records.append(current)
    return records


def _read_ini(path):
    records = []
    current = None
    for line in _split_lines(open_bytes(path)):
        stripped = line.strip()
        if not stripped:
            continue
        match = re.match(r'^\[record_(\d+)\]$', stripped)
        if match:
            if current is not None:
                records.append(current)
            current = {}
            continue
        if current is not None and '=' in stripped:
            name, _, value = stripped.partition('=')
            current[name.strip()] = value.strip()
    if current is not None:
        records.append(current)
    return records


def _read_properties(path):
    records = []
    for line in _split_lines(open_bytes(path)):
        stripped = line.strip()
        if not stripped:
            continue
        match = re.match(r'^record\.(\d+)\.(\w+)\s*=(.*)$', stripped)
        if not match:
            continue
        number = int(match.group(1))
        name = match.group(2)
        value = match.group(3).strip()
        value = value.replace('\\:', ':').replace('\\=', '=')
        while len(records) < number:
            records.append({})
        records[number - 1][name] = value
    return [record for record in records if record]


def _read_logfmt(path):
    records = []
    for line in _split_lines(open_bytes(path)):
        if _is_blank(line):
            continue
        row = {}
        for pair in line.split(' '):
            if not pair:
                continue
            name, _, value = pair.partition('=')
            if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
                inner = value[1:-1]
                inner = inner.replace('\\\\', '\\').replace('\\"', '"')
                inner = inner.replace('\\n', '\n').replace('\\t', '\t')
                value = inner
            row[name] = value
        records.append(row)
    return records


def _read_sexp(path):
    records = []
    for line in _split_lines(open_bytes(path)):
        stripped = line.strip()
        if not stripped:
            continue
        row = {}
        for match in re.finditer(r'\((\w+)\s+"((?:[^"\\]|\\.)*)"\)', stripped):
            value = match.group(2).replace('\\"', '"').replace('\\\\', '\\')
            row[match.group(1)] = value
        records.append(row)
    return records


def _read_rfc5424(path):
    records = []
    for line in _split_lines(open_bytes(path)):
        if '[lga@1 ' not in line:
            continue
        segment = line.split('[lga@1 ', 1)[1]
        quoted = False
        escaped = False
        end = None
        for position, char in enumerate(segment):
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = not quoted
            elif char == ']' and not quoted:
                end = position
                break
        if end is None:
            continue
        segment = segment[:end]
        row = {}
        for match in re.finditer(r'(\w+)="((?:[^"\\]|\\.)*)"', segment):
            row[match.group(1)] = match.group(2).replace('\\"', '"').replace('\\\\', '\\')
        records.append(row)
    return records


def open_bytes(path):
    with open(path, 'rb') as handle:
        return handle.read().decode('utf-8')


READERS = {
    '.csv': lambda path: _read_delimited(path, ','),
    '.psv': lambda path: _read_delimited(path, '|'),
    '.ssv': lambda path: _read_delimited(path, ' '),
    '.tsv': lambda path: _read_delimited(path, '\t'),
    '.fixed': _read_fixed,
    '.json': _read_json,
    '.jsonl': _read_jsonl,
    '.toml': _read_toml,
    '.ini': _read_ini,
    '.properties': _read_properties,
    '.logfmt': _read_logfmt,
    '.sexp': _read_sexp,
    '.rfc5424': _read_rfc5424,
}


def read_group(corpus_dir, group):
    """Read every shard of one group in canonical shard order."""
    shards = []
    for name in sorted(os.listdir(corpus_dir)):
        path = os.path.join(corpus_dir, name)
        if not os.path.isfile(path):
            continue
        stem, ext = os.path.splitext(name)
        if not stem.startswith(group + '-'):
            continue
        reader = READERS.get(ext)
        if reader is None:
            continue
        shards.append((name, reader(path)))
    return shards


def first_wins(shards, key):
    """Collapse shards keeping the first record per identity key."""
    seen = set()
    records = []
    for _, shard_records in shards:
        for record in shard_records:
            identity = key(record)
            if identity in seen:
                continue
            seen.add(identity)
            records.append(record)
    return records


def last_wins(shards, key):
    """Collapse shards keeping the last record per identity key."""
    latest = {}
    order = []
    for _, shard_records in shards:
        for record in shard_records:
            identity = key(record)
            if identity not in latest:
                order.append(identity)
            latest[identity] = record
    return [latest[identity] for identity in order]


# ---------------------------------------------------------------------------
# the corpus
# ---------------------------------------------------------------------------

def parse_target(text):
    """Split an atom target string into its elements; note= runs to the end."""
    elements = {}
    head = text
    note = None
    position = text.find('note=')
    if position >= 0:
        note = text[position + len('note='):]
        head = text[:position]
    for element in head.split(';'):
        if not element:
            continue
        name, _, value = element.partition('=')
        elements[name] = value
    if note is not None:
        elements['note'] = note
    return elements


class Corpus(object):
    def __init__(self, corpus_dir):
        self.repairs = {'arch': 0, 'capability': 0, 'number': 0, 'perm': 0, 'type': 0}
        self._load(corpus_dir)

    def _load(self, corpus_dir):
        # principals
        records = first_wins(read_group(corpus_dir, 'principals'),
                             lambda r: canon_id(r.get('principal_id', '')))
        self.principals = {}
        for record in records:
            principal_id = canon_id(record['principal_id'])
            self.principals[principal_id] = {
                'principal_id': principal_id,
                'uid': int(record['uid']) if record['uid'].strip() else 0,
                'login': unicodedata.normalize('NFC', record['login']),
                'display': unicodedata.normalize('NFC', record['display']),
                'groups': sorted(unicodedata.normalize('NFC', part)
                                 for part in record['groups'].split('|') if part),
                'inh_thread': read_cap_set(record['inh_thread']),
                'perm_thread': read_cap_set(record['perm_thread']),
            }

        # pam stack
        records = read_group(corpus_dir, 'pam-stack')
        self.pam_lines = []
        for _, shard in records:
            for record in shard:
                flags = unicodedata.normalize('NFC', record['flags'])
                gate = None
                for word in flags.split(','):
                    word = word.strip()
                    if word.startswith('skip_if_uid_below='):
                        gate = int(word.split('=', 1)[1])
                self.pam_lines.append({
                    'rule_id': canon_id(record['rule_id']),
                    'service': unicodedata.normalize('NFC', record['service']),
                    'phase': unicodedata.normalize('NFC', record['phase']),
                    'rank': int(record['rank']),
                    'control': unicodedata.normalize('NFC', record['control']),
                    'module': unicodedata.normalize('NFC', record['module']),
                    'flags': flags,
                    'gate': gate,
                })
        self.pam_lines.sort(key=lambda line: (line['service'], PHASES.index(line['phase']),
                                             line['rank'], line['module'], line['rule_id']))

        # pam returns
        records = first_wins(read_group(corpus_dir, 'pam-returns'),
                             lambda r: (canon_id(r.get('run_id', '')),
                                        unicodedata.normalize('NFC', r.get('phase', '')),
                                        unicodedata.normalize('NFC', r.get('module', ''))))
        self.pam_returns = {}
        for record in records:
            key = (canon_id(record['run_id']),
                   unicodedata.normalize('NFC', record['phase']),
                   unicodedata.normalize('NFC', record['module']))
            self.pam_returns[key] = unicodedata.normalize('NFC', record['code'])

        # selinux types
        records = read_group(corpus_dir, 'selinux-types')
        flat = []
        for _, shard in records:
            flat.extend(shard)
        self.types = {}
        for record in flat:
            name = canon_type(record['type_name'])
            attrs = set()
            for part in record['attributes'].split('|'):
                part = unicodedata.normalize('NFC', part).strip()
                if part:
                    attrs.add(part)
            self.types[name] = attrs
        self.attribute_types = {}
        for name, attrs in self.types.items():
            for attr in attrs:
                self.attribute_types.setdefault(attr, set()).add(name)

        # selinux allow
        records = read_group(corpus_dir, 'selinux-allow')
        flat = []
        for _, shard in records:
            flat.extend(shard)
        self.allow_records = []
        for record in flat:
            self.allow_records.append({
                'rule_id': canon_id(record['rule_id']),
                'source': canon_type(record['source']),
                'target': canon_type(record['target']),
                'tclass': unicodedata.normalize('NFC', record['tclass']),
                'perms': set(unicodedata.normalize('NFC', part).strip()
                             for part in record['perms'].split(',') if part.strip()),
            })

        # selinux transitions
        records = read_group(corpus_dir, 'selinux-transition')
        flat = []
        for _, shard in records:
            flat.extend(shard)
        self.transitions = []
        for record in flat:
            self.transitions.append({
                'rule_id': canon_id(record['rule_id']),
                'source': canon_type(record['source']),
                'exec_type': canon_type(record['exec_type']),
                'new_domain': canon_type(record['new_domain']),
                'rank': int(record['rank']),
            })
        self.transitions.sort(key=lambda rec: (rec['source'], rec['exec_type'],
                                               rec['rank'], rec['rule_id']))

        # cap units
        records = first_wins(read_group(corpus_dir, 'cap-units'),
                             lambda r: canon_id(r.get('unit_id', '')))
        self.units = {}
        for record in records:
            unit_id = canon_id(record['unit_id'])
            self.units[unit_id] = {
                'unit_id': unit_id,
                'unit_name': unicodedata.normalize('NFC', record['unit_name']),
                'bounding': read_cap_set(record['bounding']),
                'ambient': read_cap_set(record['ambient']),
                'no_new_privs': record['no_new_privs'].strip() == 'true',
                'filters': [canon_id(part) for part in record['filters'].split('|') if part],
            }

        # cap filecaps
        records = first_wins(read_group(corpus_dir, 'cap-filecaps'),
                             lambda r: canon_id(r.get('binary_id', '')))
        self.binaries = {}
        for record in records:
            binary_id = canon_id(record['binary_id'])
            self.binaries[binary_id] = {
                'binary_id': binary_id,
                'path': unicodedata.normalize('NFC', record['path']),
                'permitted_file': read_cap_set(record['permitted_file']),
                'inheritable_file': read_cap_set(record['inheritable_file']),
                'effective_bit': record['effective_bit'].strip() == '1',
            }

        # cap required
        records = read_group(corpus_dir, 'cap-required')
        flat = []
        for _, shard in records:
            flat.extend(shard)
        self.advisory = set()
        self.operations = []
        for record in flat:
            capability = canon_cap(record['capability'])
            advisory = unicodedata.normalize('NFC', record['advisory']).strip() == 'yes'
            if advisory and capability:
                self.advisory.add(capability)

        # seccomp filters
        records = read_group(corpus_dir, 'seccomp-filters')
        flat = []
        for _, shard in records:
            flat.extend(shard)
        self.filter_rules = []
        for record in flat:
            arg_index = record['arg_index'].strip()
            self.filter_rules.append({
                'rule_id': canon_id(record['rule_id']),
                'filter_id': canon_id(record['filter_id']),
                'idx': int(record['idx']),
                'arch': unicodedata.normalize('NFC', record['arch']),
                'syscall': unicodedata.normalize('NFC', record['syscall']),
                'arg_index': int(arg_index) if arg_index else None,
                'op': unicodedata.normalize('NFC', record['op']),
                'value': int(record['value']) if record['value'].strip() else 0,
                'mask': int(record['mask']) if record['mask'].strip() else 0,
                'action': unicodedata.normalize('NFC', record['action']),
            })
        self.filter_rules.sort(key=lambda rule: (rule['filter_id'], rule['idx'], rule['rule_id']))
        self.rules_by_filter = {}
        for rule in self.filter_rules:
            self.rules_by_filter.setdefault(rule['filter_id'], []).append(rule)

        # seccomp defaults
        records = first_wins(read_group(corpus_dir, 'seccomp-defaults'),
                             lambda r: canon_id(r.get('filter_id', '')))
        self.filter_defaults = {}
        self.filter_priority = {}
        for record in records:
            filter_id = canon_id(record['filter_id'])
            self.filter_defaults[filter_id] = unicodedata.normalize('NFC', record['default_action'])
            self.filter_priority[filter_id] = int(record['priority'])

        # arch syscalls
        records = first_wins(read_group(corpus_dir, 'arch-syscalls'),
                             lambda r: (unicodedata.normalize('NFC', r.get('arch', '')),
                                        r.get('nr', '').strip()))
        self.syscall_name = {}
        self.syscall_numbers = {}
        for record in records:
            arch = unicodedata.normalize('NFC', record['arch'])
            nr = int(record['nr'])
            name = unicodedata.normalize('NFC', record['syscall'])
            self.syscall_name[(arch, nr)] = name
            current = self.syscall_numbers.setdefault((arch, name), nr)
            if nr < current:
                self.syscall_numbers[(arch, name)] = nr

        # runs labels
        records = last_wins(read_group(corpus_dir, 'runs-labels'),
                            lambda r: canon_id(r.get('run_id', '')))
        self.labels = {}
        for record in records:
            label = unicodedata.normalize('NFC', record['label']).strip()
            self.labels[canon_id(record['run_id'])] = label

        # grant atoms
        records = first_wins(read_group(corpus_dir, 'grant-atoms'),
                            lambda r: canon_id(r.get('atom_id', '')))
        self.atoms = {}
        self.atom_order = []
        for record in records:
            atom_id = canon_id(record['atom_id'])
            target_text = unicodedata.normalize('NFC', record['target'])
            self.atoms[atom_id] = {
                'atom_id': atom_id,
                'layer': unicodedata.normalize('NFC', record['layer']),
                'kind': unicodedata.normalize('NFC', record['kind']),
                'cost': int(record['cost']),
                'target': target_text,
                'elements': parse_target(target_text),
            }
            self.atom_order.append(atom_id)
        self.atom_order.sort()

        # cost controls
        records = first_wins(read_group(corpus_dir, 'cost-controls'),
                             lambda r: canon_id(r.get('control_id', '')))
        self.controls = []
        for record in records:
            atoms = set(canon_id(part) for part in record['atoms'].split('|') if part)
            self.controls.append({
                'control_id': canon_id(record['control_id']),
                'atoms': atoms,
                'total': int(record['total']),
            })

        # audit events: recorded, not acted on
        records = read_group(corpus_dir, 'audit-events')
        self.audit_events = []
        for _, shard in records:
            for record in shard:
                self.audit_events.append({
                    'event_id': canon_id(record['event_id']),
                    'run_id': canon_id(record['run_id']),
                    'ts': unicodedata.normalize('NFC', record['ts']),
                    'action': unicodedata.normalize('NFC', record['action']),
                    'principal': canon_id(record['principal']),
                })

        # runs trace
        shards = read_group(corpus_dir, 'runs-trace')
        raw_events = []
        for _, shard in shards:
            for record in shard:
                raw_events.append(record)
        self._load_runs(raw_events)

    def _load_runs(self, raw_events):
        by_run = {}
        for record in raw_events:
            run_id = canon_id(record['run_id'])
            by_run.setdefault(run_id, []).append(record)
        runs = {}
        for run_id, records in by_run.items():
            records.sort(key=lambda r: int(r['seq']))
            dispatch = None
            exec_event = None
            for record in records:
                if record['kind'] == 'exec':
                    exec_event = record
                    arch = unicodedata.normalize('NFC', record['arch']).strip()
                    if arch:
                        dispatch = arch
                    break
            if dispatch is None:
                for record in records:
                    arch = unicodedata.normalize('NFC', record['arch']).strip()
                    if arch:
                        dispatch = arch
                        break
            if dispatch is None:
                dispatch = 'x86_64'
            base = records[0]
            events = []
            for record in records:
                kind = unicodedata.normalize('NFC', record['kind'])
                event = {
                    'seq': int(record['seq']),
                    'kind': kind,
                    'principal': canon_id(record['principal']),
                    'service': unicodedata.normalize('NFC', record['service']),
                    'unit': canon_id(record['unit']),
                    'binary': canon_id(record['binary']),
                    'source_domain': canon_type(record['source_domain']),
                    'exec_type': canon_type(record['exec_type']),
                    'phase': unicodedata.normalize('NFC', record['phase']),
                    'arg0': int(record['arg0']) if record['arg0'].strip() else 0,
                    'tclass': unicodedata.normalize('NFC', record['tclass']),
                    'required': unicodedata.normalize('NFC', record['required']),
                }
                # arch repair
                arch = unicodedata.normalize('NFC', record['arch']).strip()
                arch_repaired = False
                if kind != 'exec':
                    if not arch:
                        arch = dispatch
                        arch_repaired = True
                        self.repairs['arch'] += 1
                event['arch'] = arch
                event['arch_repaired'] = arch_repaired
                # capability repair
                capability = unicodedata.normalize('NFC', record['capability']).strip()
                if capability:
                    repaired = canon_cap(capability)
                    if repaired is None:
                        repaired = capability.upper()
                    if repaired != capability:
                        self.repairs['capability'] += 1
                    capability = repaired
                event['capability'] = capability
                # perm repair
                perm_text = unicodedata.normalize('NFC', record['perm']).strip()
                if ',' in perm_text:
                    self.repairs['perm'] += 1
                    perms = tuple(part.strip() for part in perm_text.split(',') if part.strip())
                else:
                    perms = (perm_text,) if perm_text else ()
                event['perms'] = perms
                # syscall number repair
                number_text = unicodedata.normalize('NFC', record['syscall_nr']).strip()
                if number_text:
                    if number_text.lower().startswith('0x'):
                        self.repairs['number'] += 1
                        number = int(number_text, 16)
                    elif number_text.startswith('0') and len(number_text) > 1:
                        self.repairs['number'] += 1
                        number = int(number_text)
                    else:
                        number = int(number_text)
                    event['nr'] = number
                else:
                    event['nr'] = None
                # target type repair
                target_type = unicodedata.normalize('NFC', record['target_type']).strip()
                if target_type:
                    canonical = canon_type(target_type)
                    if canonical != target_type:
                        self.repairs['type'] += 1
                    target_type = canonical
                event['target_type'] = target_type
                events.append(event)
            run = {
                'run_id': run_id,
                'label': self.labels.get(run_id, 'unlabelled'),
                'dispatch_arch': dispatch,
                'principal': canon_id(base['principal']),
                'service': unicodedata.normalize('NFC', base['service']),
                'unit': canon_id(base['unit']),
                'binary': canon_id(base['binary']),
                'source_domain': canon_type(base['source_domain']),
                'exec_type': canon_type(base['exec_type']),
                'events': events,
            }
            runs[run_id] = run
        self.runs = runs
        self.run_ids = sorted(runs)


# ---------------------------------------------------------------------------
# the policy
# ---------------------------------------------------------------------------

class Policy(object):
    """The shipped policy plus the relaxation carried by a set of atoms."""

    def __init__(self, corpus):
        self.corpus = corpus
        self.grants = {}
        for record in corpus.allow_records:
            for source in self._expand(record['source']):
                for target in self._expand(record['target']):
                    key = (source, target, record['tclass'])
                    self.grants.setdefault(key, set()).update(record['perms'])
        self.transition_index = {}
        for record in corpus.transitions:
            self.transition_index.setdefault((record['source'], record['exec_type']), []).append(record)
        self.stack_index = {}
        for line in corpus.pam_lines:
            self.stack_index.setdefault((line['service'], line['phase']), []).append(line)
        for key in self.stack_index:
            self.stack_index[key].sort(key=lambda line: (line['rank'], line['module'], line['rule_id']))

    def _expand(self, name):
        if name in self.corpus.attribute_types:
            return sorted(self.corpus.attribute_types[name])
        return [name]

    # -- grant set ---------------------------------------------------------

    def allowed(self, grants_extra, source, target, tclass, perm):
        if perm in self.grants.get((source, target, tclass), ()):
            return True
        return perm in grants_extra.get((source, target, tclass), ())

    def atom_grants(self, atoms):
        """Expand the te_allow_add atoms of a set into extra grants."""
        grants = {}
        for atom_id in atoms:
            atom = self.corpus.atoms[atom_id]
            if atom['kind'] != 'te_allow_add':
                continue
            elements = atom['elements']
            source = canon_type(elements.get('source', ''))
            target = canon_type(elements.get('target', ''))
            tclass = unicodedata.normalize('NFC', elements.get('class', ''))
            perm = unicodedata.normalize('NFC', elements.get('perm', ''))
            for source_name in self._expand(source):
                for target_name in self._expand(target):
                    grants.setdefault((source_name, target_name, tclass), set()).add(perm)
        return grants

    # -- capabilities -----------------------------------------------------

    def cap_sets(self, run, cap_atoms):
        """Return the effective and permitted sets of a run under cap atoms."""
        corpus = self.corpus
        unit = corpus.units.get(run['unit'], {'bounding': frozenset(),
                                              'ambient': frozenset(),
                                              'no_new_privs': False})
        bounding = set(unit['bounding'])
        ambient = set(unit['ambient'])
        for atom_id in cap_atoms:
            elements = corpus.atoms[atom_id]['elements']
            if canon_id(elements.get('unit', '')) != run['unit']:
                continue
            capability = canon_cap(elements.get('cap', ''))
            if capability is None:
                continue
            kind = corpus.atoms[atom_id]['kind']
            if kind == 'cap_bounding_add':
                bounding.add(capability)
            elif kind == 'cap_ambient_add':
                bounding.add(capability)
                ambient.add(capability)
        binary = corpus.binaries.get(run['binary'], {'permitted_file': frozenset(),
                                                    'inheritable_file': frozenset(),
                                                    'effective_bit': False})
        principal = corpus.principals.get(run['principal'], {'inh_thread': frozenset(),
                                                             'perm_thread': frozenset()})
        file_permitted = set(binary['permitted_file'])
        file_inheritable = set(binary['inheritable_file'])
        thread_inheritable = set(principal['inh_thread'])
        thread_permitted = set(principal['perm_thread'])
        if unit['no_new_privs']:
            from_file = file_permitted & bounding & thread_permitted
        else:
            from_file = file_permitted & bounding
        permitted = (thread_inheritable & file_inheritable) | from_file | ambient
        if binary['effective_bit']:
            effective = permitted
        else:
            effective = set(ambient)
        return frozenset(permitted), frozenset(effective)

    # -- pam ---------------------------------------------------------------

    def pam_phase(self, run, phase, relaxed_rules, returns=None):
        """Walk one phase; returns (code, deciding_rule, deciding_module)."""
        corpus = self.corpus
        principal = corpus.principals.get(run['principal'])
        uid = principal['uid'] if principal else 0
        returns = returns if returns is not None else corpus.pam_returns
        lines = self.stack_index.get((run['service'], phase), ())
        first_failure = None
        first_optional = None
        flag = False
        for line in lines:
            code = returns.get((run['run_id'], phase, line['module']), 'ignore')
            if code != 'ignore' and code not in PAM_CODES:
                code = 'ignore'
            control = line['control']
            if relaxed_rules and line['rule_id'] in relaxed_rules:
                control = 'sufficient'
            if line['gate'] is not None and uid < line['gate']:
                continue
            if code == 'ignore':
                continue
            if control == 'optional':
                if code != 'success' and first_optional is None:
                    first_optional = (line, code)
                continue
            flag = True
            if control in ('requisite', 'binding'):
                if code != 'success':
                    return code, line['rule_id'], line['module']
                if control == 'binding':
                    return 'success', 'NONE', line['module']
                continue
            if control == 'sufficient':
                if code == 'success':
                    if first_failure is None:
                        return 'success', 'NONE', line['module']
                    continue
                continue
            if control == 'required':
                if code != 'success' and first_failure is None:
                    first_failure = (line, code)
                continue
        if first_failure is not None:
            return first_failure[1], first_failure[0]['rule_id'], first_failure[0]['module']
        if flag:
            return 'success', 'NONE', 'NONE'
        if first_optional is not None:
            return first_optional[1], first_optional[0]['rule_id'], first_optional[0]['module']
        return 'service_err', 'NONE', 'NONE'

    # -- selinux -----------------------------------------------------------

    def transition_choice(self, run):
        """Return the chosen transition record for the run's exec event, or None."""
        records = self.transition_index.get((run['source_domain'], run['exec_type']))
        if not records:
            return None
        return records[0]

    def exec_decision(self, run, grants_extra):
        """Return (ok, chosen, domain_in_force, missing, flags).

        flags are ordered execute_ok, entrypoint_ok, transition_ok.
        """
        chosen = self.transition_choice(run)
        if chosen is None:
            return True, None, run['source_domain'], [], ('yes', 'yes', 'yes')
        landing = chosen['new_domain']
        exec_type = run['exec_type']
        checks = (
            ('execute', run['source_domain'], exec_type, 'file', 'execute'),
            ('entrypoint', landing, exec_type, 'file', 'entrypoint'),
            ('transition', run['source_domain'], landing, 'process', 'transition'),
        )
        flags = []
        missing = []
        for name, source, target, tclass, perm in checks:
            ok = self.allowed(grants_extra, source, target, tclass, perm)
            flags.append('yes' if ok else 'no')
            if not ok:
                missing.append((name, source, target, tclass, perm))
        if missing:
            return False, chosen, run['source_domain'], missing, tuple(flags)
        return True, chosen, landing, [], tuple(flags)

    # -- seccomp -----------------------------------------------------------

    def seccomp_decision(self, run, event, filter_default_override,
                         filter_unloaded, rule_allow):
        """Return (action, rule_id, matched_count, deciding_filter)."""
        corpus = self.corpus
        loaded = [f for f in self.corpus.units.get(run['unit'], {}).get('filters', [])
                  if f not in filter_unloaded]
        matched = 0
        best_action = None
        best_rule = None
        best_filter = None
        if not loaded:
            return 'ALLOW', 'NONE', 0, None
        for filter_id in loaded:
            answer = None
            answer_rule = None
            for rule in self.corpus.rules_by_filter.get(filter_id, ()):
                if rule['arch'] != event['arch']:
                    continue
                if rule['syscall'] != event['syscall']:
                    continue
                if rule['arg_index'] is not None:
                    if rule['arg_index'] != 0:
                        continue
                    if not _compare(rule['op'], event['arg0'], rule['value'], rule['mask']):
                        continue
                matched += 1
                if answer is None or ACTION_RANK[rule['action']] < ACTION_RANK[answer]:
                    answer = rule['action']
                    answer_rule = rule
                elif (ACTION_RANK[rule['action']] == ACTION_RANK[answer]
                      and (rule['idx'], rule['rule_id']) < (answer_rule['idx'], answer_rule['rule_id'])):
                    answer_rule = rule
            if answer is None:
                if (filter_id, event['arch'], event['syscall']) in rule_allow:
                    answer = 'ALLOW'
                    answer_rule = None
                else:
                    answer = filter_default_override.get(filter_id,
                                                         corpus.filter_defaults.get(filter_id, 'ALLOW'))
                    answer_rule = None
            elif (filter_id, event['arch'], event['syscall']) in rule_allow:
                answer = 'ALLOW'
                answer_rule = None
            if best_action is None or ACTION_RANK[answer] < ACTION_RANK[best_action]:
                best_action = answer
                best_rule = answer_rule
                best_filter = filter_id
            elif ACTION_RANK[answer] == ACTION_RANK[best_action]:
                # tie across filters: a default sorts before every rule identifier
                candidate = '' if answer_rule is None else answer_rule['rule_id']
                incumbent = '' if best_rule is None else best_rule['rule_id']
                if candidate < incumbent:
                    best_action = answer
                    best_rule = answer_rule
                    best_filter = filter_id
        return best_action, (best_rule['rule_id'] if best_rule is not None else 'NONE'), matched, best_filter


def _compare(op, arg, value, mask):
    if op == 'EQ':
        return arg == value
    if op == 'NE':
        return arg != value
    if op == 'LT':
        return arg < value
    if op == 'LE':
        return arg <= value
    if op == 'GT':
        return arg > value
    if op == 'GE':
        return arg >= value
    if op == 'MASKED_EQ':
        return (arg & mask) == value
    return False


# ---------------------------------------------------------------------------
# replay
# ---------------------------------------------------------------------------

class Applied(object):
    """The relaxation of one set of atoms over the shipped policy."""

    def __init__(self, policy, atom_ids):
        self.policy = policy
        self.corpus = policy.corpus
        self.atom_ids = frozenset(atom_ids)
        self.grants_extra = policy.atom_grants(self.atom_ids)
        self.relaxed_rules = set()
        self.cap_atoms = []
        self.filter_default_override = {}
        self.filter_unloaded = set()
        self.rule_allow = set()
        for atom_id in self.atom_ids:
            atom = self.corpus.atoms[atom_id]
            elements = atom['elements']
            if atom['kind'] == 'pam_control_relax':
                self.relaxed_rules.add(canon_id(elements.get('rule', '')))
            elif atom['kind'] in ('cap_bounding_add', 'cap_ambient_add'):
                self.cap_atoms.append(atom_id)
            elif atom['kind'] == 'seccomp_default_relax':
                self.filter_default_override[canon_id(elements.get('filter', ''))] = 'ALLOW'
            elif atom['kind'] == 'filter_unload':
                self.filter_unloaded.add(canon_id(elements.get('filter', '')))
            elif atom['kind'] == 'seccomp_rule_add':
                self.rule_allow.add((canon_id(elements.get('filter', '')),
                                     unicodedata.normalize('NFC', elements.get('arch', '')),
                                     unicodedata.normalize('NFC', elements.get('syscall', ''))))

    def replay(self, run):
        """Replay a run; returns a verdict record."""
        corpus = self.corpus
        policy = self.policy
        events = run['events']
        permitted, effective = policy.cap_sets(run, self.cap_atoms)
        exec_event = None
        for event in events:
            if event['kind'] == 'exec':
                exec_event = event
                break
        ok, chosen, domain_in_force, missing, flags = policy.exec_decision(run, self.grants_extra)
        landing = chosen['new_domain'] if chosen is not None else None
        refusal = None
        domain_after = domain_in_force
        for event in events:
            kind = event['kind']
            if kind == 'pam':
                if refusal is None:
                    code, rule, module = policy.pam_phase(run, event['phase'], self.relaxed_rules)
                    if code != 'success':
                        refusal = ('pam', event['seq'], rule, 'pam_' + code, None)
                continue
            if kind == 'exec':
                if refusal is None:
                    if not ok:
                        name = min(m[0] for m in missing)
                        refusal = ('selinux', event['seq'],
                                   chosen['rule_id'] if chosen else 'NONE',
                                   'te_missing_' + name, None)
                continue
            if kind == 'access':
                if refusal is None:
                    absent = [perm for perm in event['perms']
                              if not policy.allowed(self.grants_extra, domain_after,
                                                    event['target_type'], event['tclass'], perm)]
                    if absent:
                        refusal = ('selinux', event['seq'], 'NONE',
                                   'te_denied_' + min(absent), None)
                continue
            if kind == 'capuse':
                if refusal is None:
                    capability = event['capability']
                    if capability and capability not in effective and capability not in corpus.advisory:
                        refusal = ('capability', event['seq'], capability, 'cap_absent', None)
                continue
            if kind == 'syscall':
                if refusal is None:
                    if event['nr'] is None:
                        continue
                    name = corpus.syscall_name.get((event['arch'], event['nr']))
                    if name is None:
                        refusal = ('seccomp', event['seq'], 'NONE', 'seccomp_kill_process',
                                   None)
                    else:
                        action, rule_id, _, deciding_filter = policy.seccomp_decision(
                            run, {'arch': event['arch'], 'syscall': name, 'arg0': event['arg0']},
                            self.filter_default_override,
                            self.filter_unloaded, self.rule_allow)
                        if action in REFUSING_ACTIONS or (action == 'ERRNO' and event['required'] == 'yes'):
                            refusal = ('seccomp', event['seq'], rule_id, 'seccomp_' + action.lower(),
                                       deciding_filter)
        if refusal is None:
            return {'verdict': 'admitted', 'layer': 'NONE', 'seq': 0, 'rule': 'NONE',
                    'reason': 'admitted', 'permitted': permitted, 'effective': effective,
                    'domain_in_force': domain_in_force, 'landing': landing,
                    'transition_rule': (chosen['rule_id'] if chosen else 'NONE'),
                    'flags': flags, 'missing': missing, 'deciding_filter': None}
        return {'verdict': 'denied', 'layer': refusal[0], 'seq': refusal[1],
                'rule': refusal[2], 'reason': refusal[3], 'permitted': permitted,
                'effective': effective, 'domain_in_force': domain_in_force,
                'landing': landing, 'transition_rule': (chosen['rule_id'] if chosen else 'NONE'),
                'flags': flags, 'missing': missing, 'deciding_filter': refusal[4]}


# ---------------------------------------------------------------------------
# per event reporting under the shipped policy
# ---------------------------------------------------------------------------

def per_event_reports(policy, corpus):
    shipped = Applied(policy, ())
    decisions = []
    gaps = []
    blocked = {}
    arch_counts = {arch: {'events': 0, 'runs': 0, 'unknown': 0, 'repaired': 0}
                   for arch in ARCHES}
    for run_id in corpus.run_ids:
        run = corpus.runs[run_id]
        permitted, effective = policy.cap_sets(run, shipped.cap_atoms)
        arch_counts[run['dispatch_arch']]['runs'] += 1
        ok, chosen, domain_in_force, missing, flags = policy.exec_decision(run, shipped.grants_extra)
        for event in run['events']:
            if event['kind'] == 'capuse':
                capability = event['capability']
                if capability and capability not in effective:
                    unit = corpus.units.get(run['unit'], {})
                    binary = corpus.binaries.get(run['binary'], {})
                    gaps.append({
                        'run_id': run_id,
                        'capability': capability,
                        'unit': run['unit'],
                        'in_bounding': 'yes' if capability in unit.get('bounding', frozenset()) else 'no',
                        'in_permitted': 'yes' if capability in permitted else 'no',
                        'delta': -1 if capability in binary.get('permitted_file', frozenset()) else 1,
                    })
            elif event['kind'] == 'syscall':
                arch_counts[event['arch']]['events'] += 1
                if event['nr'] is None:
                    continue
                name = corpus.syscall_name.get((event['arch'], event['nr']))
                unknown = name is None
                if unknown:
                    name = 'NONE'
                    arch_counts[event['arch']]['unknown'] += 1
                if unknown:
                    action, rule_id, matched = 'KILL_PROCESS', 'NONE', 0
                else:
                    action, rule_id, matched, _ = policy.seccomp_decision(
                        run, {'arch': event['arch'], 'syscall': name, 'arg0': event['arg0']},
                        shipped.filter_default_override,
                        shipped.filter_unloaded, shipped.rule_allow)
                denies = (action in REFUSING_ACTIONS
                          or (action == 'ERRNO' and event['required'] == 'yes'))
                decisions.append({
                    'run_id': run_id, 'seq': event['seq'], 'arch': event['arch'],
                    'nr': event['nr'], 'syscall': name, 'action': action,
                    'rule_id': rule_id, 'matched_count': matched, 'denies': denies,
                })
                if denies:
                    key = (event['arch'], name)
                    entry = blocked.setdefault(key, {'count': 0, 'action': None})
                    entry['count'] += 1
                    if entry['action'] is None or ACTION_RANK[action] < ACTION_RANK[entry['action']]:
                        entry['action'] = action
    for run_id in corpus.run_ids:
        run = corpus.runs[run_id]
        for event in run['events']:
            if event.get('arch_repaired'):
                arch_counts[event['arch']]['repaired'] += 1
    return decisions, gaps, blocked, arch_counts


# ---------------------------------------------------------------------------
# forbidden atoms and repair counts
# ---------------------------------------------------------------------------

def refusal_touching_atoms(policy, corpus, run, verdict):
    """Atoms that can change the decision at the run's first refusing event."""
    layer = verdict['layer']
    event = None
    for candidate in run['events']:
        if candidate['seq'] == verdict['seq']:
            event = candidate
            break
    if event is None:
        return []
    if layer == 'pam':
        rule = verdict['rule']
        return [atom_id for atom_id in corpus.atom_order
                if corpus.atoms[atom_id]['kind'] == 'pam_control_relax'
                and canon_id(corpus.atoms[atom_id]['elements'].get('rule', '')) == rule]
    if layer == 'capability':
        capability = verdict['rule']
        result = []
        for atom_id in corpus.atom_order:
            atom = corpus.atoms[atom_id]
            if atom['kind'] not in ('cap_bounding_add', 'cap_ambient_add'):
                continue
            elements = atom['elements']
            if canon_id(elements.get('unit', '')) == run['unit'] and \
                    canon_cap(elements.get('cap', '')) == capability:
                result.append(atom_id)
        return result
    if layer == 'seccomp':
        name = corpus.syscall_name.get((event['arch'], event['nr'])) if event['nr'] is not None else None
        if name is None:
            # a number that resolves to no name is refused outright; no atom
            # changes that event's decision
            return []
        loaded = corpus.units.get(run['unit'], {}).get('filters', [])
        result = []
        for atom_id in corpus.atom_order:
            atom = corpus.atoms[atom_id]
            elements = atom['elements']
            if atom['kind'] == 'filter_unload':
                if canon_id(elements.get('filter', '')) in loaded:
                    result.append(atom_id)
            elif atom['kind'] == 'seccomp_default_relax':
                if canon_id(elements.get('filter', '')) in loaded:
                    result.append(atom_id)
            elif atom['kind'] == 'seccomp_rule_add':
                if canon_id(elements.get('filter', '')) in loaded and \
                        elements.get('arch') == event['arch'] and \
                        elements.get('syscall') == name:
                    result.append(atom_id)
        return result
    if layer == 'selinux':
        return selinux_touching_atoms(policy, corpus, run, verdict, event)
    return []


def selinux_touching_atoms(policy, corpus, run, verdict, event):
    """te_allow_add atoms whose triple is one of the missing ones at the event."""
    if verdict['reason'].startswith('te_missing_'):
        missing_triples = verdict['missing']
    else:
        domain = verdict['domain_in_force']
        absent = [(perm, domain, event['target_type'], event['tclass'], perm)
                  for perm in event['perms']
                  if not policy.allowed({}, domain, event['target_type'], event['tclass'], perm)]
        missing_triples = absent
    wanted = set()
    for _, source, target, tclass, perm in missing_triples:
        wanted.add((source, target, tclass, perm))
        for attr in corpus.types.get(source, ()):
            wanted.add((attr, target, tclass, perm))
        for attr in corpus.types.get(target, ()):
            wanted.add((source, attr, tclass, perm))
    result = []
    for atom_id in corpus.atom_order:
        atom = corpus.atoms[atom_id]
        if atom['kind'] != 'te_allow_add':
            continue
        elements = atom['elements']
        source = canon_type(elements.get('source', ''))
        target = canon_type(elements.get('target', ''))
        tclass = unicodedata.normalize('NFC', elements.get('class', ''))
        perm = unicodedata.normalize('NFC', elements.get('perm', ''))
        if (source, target, tclass, perm) in wanted:
            result.append(atom_id)
    return result


def candidate_atoms(policy, corpus, run, verdict, chosen, event):
    """Candidate atoms for a refused run under section 9."""
    layer = verdict['layer']
    corpus_atoms = corpus.atoms
    if layer == 'pam':
        rule = verdict['rule']
        keys = [atom_id for atom_id in corpus.atom_order
                if corpus_atoms[atom_id]['kind'] == 'pam_control_relax'
                and canon_id(corpus_atoms[atom_id]['elements'].get('rule', '')) == rule]
    elif layer == 'capability':
        capability = verdict['rule']
        keys = [atom_id for atom_id in corpus.atom_order
                if corpus_atoms[atom_id]['kind'] in ('cap_bounding_add', 'cap_ambient_add')
                and canon_id(corpus_atoms[atom_id]['elements'].get('unit', '')) == run['unit']
                and canon_cap(corpus_atoms[atom_id]['elements'].get('cap', '')) == capability]
    elif layer == 'seccomp':
        name = corpus.syscall_name.get((event['arch'], event['nr'])) if event['nr'] is not None else None
        loaded = corpus.units.get(run['unit'], {}).get('filters', [])
        keys = []
        for atom_id in corpus.atom_order:
            atom = corpus_atoms[atom_id]
            elements = atom['elements']
            if atom['kind'] == 'seccomp_default_relax' or atom['kind'] == 'filter_unload':
                if canon_id(elements.get('filter', '')) in loaded:
                    keys.append(atom_id)
            elif atom['kind'] == 'seccomp_rule_add':
                if name is not None and canon_id(elements.get('filter', '')) in loaded and \
                        elements.get('arch') == event['arch'] and \
                        elements.get('syscall') == name:
                    keys.append(atom_id)
    elif layer == 'selinux':
        keys = selinux_candidates(policy, corpus, run, verdict, event)
    else:
        keys = []
    return [atom_id for atom_id in keys if atom_id not in chosen]


def selinux_candidates(policy, corpus, run, verdict, event):
    source_ok = {run['source_domain']}
    if verdict['landing']:
        source_ok.add(verdict['landing'])
    targets = {event_target_type(event, verdict)}
    target = event_target_type(event, verdict)
    for attr in corpus.types.get(target, ()):
        targets.add(attr)
    keys = []
    for atom_id in corpus.atom_order:
        atom = corpus.atoms[atom_id]
        if atom['kind'] != 'te_allow_add':
            continue
        elements = atom['elements']
        if canon_type(elements.get('source', '')) not in source_ok:
            continue
        if canon_type(elements.get('target', '')) not in targets:
            continue
        keys.append(atom_id)
    return keys


def event_target_type(event, verdict):
    """The refused target of the event under section 9."""
    if verdict['reason'].startswith('te_missing_'):
        name = verdict['reason'][len('te_missing_'):]
        if name == 'transition':
            return verdict['landing']
        return event['exec_type']
    return event['target_type']


# ---------------------------------------------------------------------------
# plan building
# ---------------------------------------------------------------------------

def settle_plan(policy, corpus, multipliers, forbidden):
    """Build the plan in rounds and shrink it, under one multiplier pair."""
    effective_cost = {}
    for atom_id in corpus.atom_order:
        atom = corpus.atoms[atom_id]
        multiplier = multipliers.get(atom['kind'], 1)
        effective_cost[atom_id] = atom['cost'] * multiplier
    chosen = set()
    chosen_round = {}
    rounds = []
    round_number = 0
    while round_number < ROUND_CAP:
        round_number += 1
        applied = Applied(policy, chosen)
        denied = []
        baseline = {}
        for run_id in corpus.run_ids:
            run = corpus.runs[run_id]
            if run['label'] != 'must_admit':
                continue
            verdict = applied.replay(run)
            if verdict['verdict'] == 'denied':
                denied.append(run_id)
                baseline[run_id] = verdict
        if not denied:
            break
        denied_before = len(denied)
        added = []
        for run_id in denied:
            run = corpus.runs[run_id]
            verdict = baseline[run_id]
            event = None
            for candidate in run['events']:
                if candidate['seq'] == verdict['seq']:
                    event = candidate
                    break
            keys = candidate_atoms(policy, corpus, run, verdict, chosen, event)
            effective = []
            for atom_id in keys:
                if atom_id in forbidden:
                    continue
                trial = Applied(policy, chosen | {atom_id})
                outcome = trial.replay(run)
                if outcome['verdict'] == 'admitted':
                    effective.append(atom_id)
                elif outcome['verdict'] == 'denied' and outcome['seq'] > verdict['seq']:
                    effective.append(atom_id)
            if not effective:
                continue
            effective.sort(key=lambda atom_id: (effective_cost[atom_id], atom_id))
            pick = effective[0]
            chosen.add(pick)
            chosen_round[pick] = round_number
            added.append(pick)
        applied = Applied(policy, chosen)
        still = 0
        for run_id in corpus.run_ids:
            run = corpus.runs[run_id]
            if run['label'] != 'must_admit':
                continue
            if applied.replay(run)['verdict'] == 'denied':
                still += 1
        rounds.append({'round': round_number, 'denied_before': denied_before,
                       'denied_after': still, 'atoms_added': sorted(added),
                       'cost_added': sum(effective_cost[a] for a in added)})
        if not added:
            break
        if still == 0:
            break
    # shrink
    applied = Applied(policy, chosen)
    target_runs = []
    for run_id in corpus.run_ids:
        run = corpus.runs[run_id]
        if run['label'] != 'must_admit':
            continue
        if applied.replay(run)['verdict'] == 'admitted':
            target_runs.append(run_id)
    plan = set(chosen)
    for atom_id in sorted(chosen, reverse=True):
        trial_set = plan - {atom_id}
        trial = Applied(policy, trial_set)
        if all(trial.replay(corpus.runs[r])['verdict'] == 'admitted' for r in target_runs):
            plan = trial_set
    ordering = sorted(plan, key=lambda atom_id: (chosen_round[atom_id],
                                                 effective_cost[atom_id], atom_id))
    total_cost = sum(effective_cost[a] for a in plan)
    return {'plan': plan, 'rounds': rounds, 'chosen_round': chosen_round,
            'ordering': ordering, 'total_cost': total_cost,
            'effective_cost': effective_cost, 'rounds_used': len(rounds)}


def consistent_multipliers(corpus):
    """Determine the cap_bounding_add and seccomp_rule_add multipliers."""
    controls = []
    for control in corpus.controls:
        if all(atom in corpus.atoms for atom in control['atoms']):
            controls.append(control)
    if not controls:
        return [(1, 1)]
    pairs = []
    for cap_multiplier in range(1, 5):
        for seccomp_multiplier in range(1, 5):
            ok = True
            for control in controls:
                total = 0
                for atom_id in control['atoms']:
                    atom = corpus.atoms[atom_id]
                    if atom['kind'] == 'cap_bounding_add':
                        total += atom['cost'] * cap_multiplier
                    elif atom['kind'] == 'seccomp_rule_add':
                        total += atom['cost'] * seccomp_multiplier
                    else:
                        total += atom['cost']
                if total != control['total']:
                    ok = False
                    break
            if ok:
                pairs.append((cap_multiplier, seccomp_multiplier))
    return pairs


# ---------------------------------------------------------------------------
# artifact writers
# ---------------------------------------------------------------------------

def json_compact(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))


def csv_field(value):
    text = str(value)
    if any(ch in text for ch in (',', '"', '\n')):
        return '"' + text.replace('"', '""') + '"'
    return text


def tsv_field(value):
    text = str(value)
    return text.replace('\\', '\\\\').replace('\t', '\\t').replace('\n', '\\n')


def write_csv(path, header, rows):
    parts = []
    if header is not None:
        parts.append(','.join(csv_field(name) for name in header))
    for row in rows:
        parts.append(','.join(csv_field(value) for value in row))
    write_text(path, '\n'.join(parts) + '\n' if parts else '')


def write_tsv(path, header, rows):
    parts = []
    if header is not None:
        parts.append('\t'.join(tsv_field(name) for name in header))
    for row in rows:
        parts.append('\t'.join(tsv_field(value) for value in row))
    write_text(path, '\n'.join(parts) + '\n' if parts else '')


def write_jsonl(path, objects):
    text = ''.join(json_compact(obj) + '\n' for obj in objects)
    write_text(path, text)


def write_json(path, obj):
    write_text(path, json_compact(obj) + '\n')


def write_text(path, text):
    with open(path, 'wb') as handle:
        handle.write(text.encode('utf-8'))


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: lgactl.py CORPUS_DIR OUT_DIR\n')
        return 2
    corpus_dir, out_dir = argv[1], argv[2]
    if not os.path.isdir(corpus_dir):
        sys.stderr.write('corpus directory is absent: %s\n' % corpus_dir)
        return 2
    for group in REQUIRED_GROUPS:
        shards = read_group(corpus_dir, group)
        if not shards or not any(shard for _, shard in shards):
            sys.stderr.write('corpus group is empty: %s\n' % group)
            return 3
    corpus = Corpus(corpus_dir)
    policy = Policy(corpus)

    # shipped verdicts and per event reporting
    shipped = Applied(policy, ())
    verdicts = {}
    for run_id in corpus.run_ids:
        verdicts[run_id] = shipped.replay(corpus.runs[run_id])

    # forbidden atoms and repair counts
    repairs_count = {atom_id: 0 for atom_id in corpus.atom_order}
    forbidden = {}
    for run_id in corpus.run_ids:
        run = corpus.runs[run_id]
        verdict = verdicts[run_id]
        if verdict['verdict'] != 'denied':
            continue
        layer = verdict['layer']
        event = None
        for candidate in run['events']:
            if candidate['seq'] == verdict['seq']:
                event = candidate
                break
        touching = refusal_touching_atoms(policy, corpus, run, verdict)
        for atom_id in touching:
            atom = corpus.atoms[atom_id]
            if atom['layer'] != layer:
                continue
            trial = Applied(policy, {atom_id})
            if trial.replay(run)['verdict'] == 'admitted':
                if run['label'] == 'must_admit':
                    repairs_count[atom_id] += 1
                elif run['label'] == 'must_deny' and atom_id not in forbidden:
                    forbidden[atom_id] = run_id

    # multipliers and plan
    pairs = consistent_multipliers(corpus)
    if not pairs:
        pairs = [(1, 1)]
    settled = []
    for cap_multiplier, seccomp_multiplier in pairs:
        multipliers = {'cap_bounding_add': cap_multiplier,
                       'seccomp_rule_add': seccomp_multiplier}
        result = settle_plan(policy, corpus, multipliers, forbidden)
        settled.append(((cap_multiplier, seccomp_multiplier), result))
    settled.sort(key=lambda item: (item[1]['total_cost'], item[0][0], item[0][1]))
    chosen_pair, plan_result = settled[0]
    multipliers = {'cap_bounding_add': chosen_pair[0], 'seccomp_rule_add': chosen_pair[1]}
    effective_cost = plan_result['effective_cost']
    plan = plan_result['plan']

    plan_applied = Applied(policy, plan)
    final_verdicts = {}
    for run_id in corpus.run_ids:
        final_verdicts[run_id] = plan_applied.replay(corpus.runs[run_id])

    write_artifacts(corpus, policy, verdicts, repairs_count, forbidden,
                    plan_result, multipliers, effective_cost, final_verdicts,
                    out_dir)
    return 0


def write_artifacts(corpus, policy, verdicts, repairs_count, forbidden,
                    plan_result, multipliers, effective_cost, final_verdicts,
                    out_dir):
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    paths = {name: os.path.join(out_dir, name) for name in ARTIFACT_ORDER}
    paths['manifest.json'] = os.path.join(out_dir, 'manifest.json')

    # principal registry
    runs_by_principal = {}
    for run_id in corpus.run_ids:
        runs_by_principal.setdefault(corpus.runs[run_id]['principal'], []).append(run_id)
    principal_ids = sorted(runs_by_principal)
    objects = []
    for principal_id in principal_ids:
        record = corpus.principals.get(principal_id)
        run_ids = runs_by_principal[principal_id]
        residual = any(corpus.runs[r]['label'] == 'must_admit'
                       and final_verdicts[r]['verdict'] == 'denied' for r in run_ids)
        if residual:
            disposition = 'residual'
        elif any(verdicts[r]['verdict'] == 'denied'
                 and final_verdicts[r]['verdict'] == 'admitted' for r in run_ids):
            disposition = 'granted'
        elif all(verdicts[r]['verdict'] == 'admitted' for r in run_ids):
            disposition = 'admitted'
        else:
            disposition = 'denied'
        objects.append({
            'principal_id': principal_id,
            'uid': record['uid'] if record else 0,
            'login': record['login'] if record else '',
            'display': record['display'] if record else '',
            'groups': record['groups'] if record else [],
            'inheritable': sorted(record['inh_thread'], key=lambda name: CAP_BIT[name]) if record else [],
            'permitted': sorted(record['perm_thread'], key=lambda name: CAP_BIT[name]) if record else [],
            'run_count': len(run_ids),
            'final_disposition': disposition,
        })
    write_jsonl(paths['principal_registry.jsonl'], objects)

    # syscall index
    rows = []
    for (arch, nr) in sorted(corpus.syscall_name, key=lambda key: (key[0], key[1])):
        name = corpus.syscall_name[(arch, nr)]
        rows.append((arch, nr, name, '%04d' % nr))
    write_tsv(paths['syscall_index.tsv'], ('arch', 'nr', 'syscall', 'nr_padded'), rows)

    # pam stack resolved
    rows = []
    position_index = {}
    for line in corpus.pam_lines:
        key = (line['service'], line['phase'])
        position_index[key] = position_index.get(key, 0) + 1
        rows.append((line['service'], line['phase'], position_index[key],
                     line['rank'], line['control'], line['module'], line['rule_id'],
                     '' if line['gate'] is None else line['gate']))
    write_csv(paths['pam_stack_resolved.csv'],
              ('service', 'phase', 'position', 'rank', 'control', 'module',
               'rule_id', 'gated_uid'), rows)

    # selinux type graph
    types = {}
    for name in sorted(corpus.types):
        types[name] = sorted(corpus.types[name])
    attributes = {}
    for attr in sorted(corpus.attribute_types):
        attributes[attr] = sorted(corpus.attribute_types[attr])
    domains = sorted(name for name, attrs in corpus.types.items() if 'domain' in attrs)
    file_types = sorted(name for name, attrs in corpus.types.items() if 'domain' not in attrs)
    write_json(paths['selinux_type_graph.json'],
               {'types': types, 'attributes': attributes, 'domains': domains,
                'file_types': file_types})

    # seccomp program
    objects = []
    for rule in corpus.filter_rules:
        nr = corpus.syscall_numbers.get((rule['arch'], rule['syscall']))
        objects.append({
            'rule_id': rule['rule_id'], 'filter_id': rule['filter_id'],
            'idx': rule['idx'], 'arch': rule['arch'], 'syscall': rule['syscall'],
            'nr': nr, 'arg_index': rule['arg_index'], 'op': rule['op'],
            'value': rule['value'], 'mask': rule['mask'], 'action': rule['action'],
            'action_rank': ACTION_RANK[rule['action']],
        })
    write_jsonl(paths['seccomp_program.jsonl'], objects)

    # pam verdicts
    rows = []
    for run_id in corpus.run_ids:
        run = corpus.runs[run_id]
        for phase in PHASES:
            code, rule, module = policy.pam_phase(run, phase, set())
            rows.append((run_id, phase, code, rule if code != 'success' else 'NONE', module))
    write_csv(paths['pam_verdicts.csv'],
              ('run_id', 'phase', 'result', 'deciding_rule', 'deciding_module'), rows)

    # capability ledger
    rows = []
    for run_id in corpus.run_ids:
        run = corpus.runs[run_id]
        permitted, effective = policy.cap_sets(run, [])
        unit = corpus.units.get(run['unit'], {})
        rows.append((run_id, run['unit'], run['binary'],
                     'yes' if unit.get('no_new_privs') else 'no',
                     len(unit.get('bounding', frozenset())),
                     len(unit.get('ambient', frozenset())),
                     write_cap_set(permitted), write_cap_set(effective)))
    write_csv(paths['capability_ledger.csv'],
              ('run_id', 'unit', 'binary', 'nnp', 'bounding_count', 'ambient_count',
               'permitted', 'effective'), rows)

    # domain transitions
    rows = []
    for run_id in corpus.run_ids:
        run = corpus.runs[run_id]
        ok, chosen, domain_in_force, missing, flags = policy.exec_decision(run, {})
        rows.append((run_id, run['source_domain'], run['exec_type'],
                     chosen['rule_id'] if chosen else 'NONE', domain_in_force,
                     flags[0], flags[1], flags[2]))
    write_tsv(paths['domain_transitions.tsv'], None, rows)

    # seccomp decisions
    decisions, gaps, blocked, arch_counts = per_event_reports(policy, corpus)
    write_jsonl(paths['seccomp_decisions.jsonl'], decisions)

    # arch dispatch
    rows = []
    for arch in ARCHES:
        counts = arch_counts[arch]
        rows.append((arch, counts['events'], counts['runs'], counts['unknown'],
                     counts['repaired']))
    write_tsv(paths['arch_dispatch.tsv'],
              ('arch', 'event_count', 'run_count', 'unknown_count', 'repaired_count'), rows)

    # admission ledger
    rows = []
    for run_id in corpus.run_ids:
        verdict = verdicts[run_id]
        rows.append((run_id, corpus.runs[run_id]['label'], verdict['verdict'],
                     verdict['layer'], verdict['seq'], verdict['rule'], verdict['reason']))
    rows.sort(key=lambda row: (LAYER_RANK[row[3]], row[4]))
    write_csv(paths['admission_ledger.csv'],
              ('run_id', 'label', 'verdict', 'layer', 'seq', 'rule_id', 'reason'), rows)

    # denial attribution
    objects = []
    for run_id in corpus.run_ids:
        verdict = verdicts[run_id]
        if verdict['verdict'] != 'denied':
            continue
        run = corpus.runs[run_id]
        layer = verdict['layer']
        event = None
        for candidate in run['events']:
            if candidate['seq'] == verdict['seq']:
                event = candidate
                break
        if layer == 'pam':
            detail = 'pam %s phase %s rule %s' % (run['service'], event['phase'], verdict['rule'])
        elif layer == 'selinux':
            if verdict['reason'].startswith('te_missing_'):
                name = verdict['reason'][len('te_missing_'):]
                if name == 'transition':
                    target, tclass = verdict['landing'], 'process'
                else:
                    target, tclass = event['exec_type'], 'file'
                perms = (name,)
            else:
                target = event['target_type']
                tclass = event['tclass']
                perms = event['perms']
            detail = 'allow %s %s : %s { %s }' % (run['source_domain'], target,
                                                   tclass, ','.join(perms))
        elif layer == 'capability':
            detail = 'capability %s absent from the effective set' % verdict['rule']
        else:
            detail = 'seccomp %s on %s nr %d' % (verdict['reason'], event['arch'], event['nr'])
        objects.append({'run_id': run_id, 'layer': layer, 'seq': verdict['seq'],
                        'rule_id': verdict['rule'], 'reason': verdict['reason'],
                        'detail': detail})
    write_jsonl(paths['denial_attribution.jsonl'], objects)

    # blocked syscalls
    plan_by_pair = {}
    for atom_id in plan_result['ordering']:
        atom = corpus.atoms[atom_id]
        if atom['kind'] != 'seccomp_rule_add':
            continue
        elements = atom['elements']
        key = (unicodedata.normalize('NFC', elements.get('arch', '')),
               unicodedata.normalize('NFC', elements.get('syscall', '')))
        round_number = plan_result['chosen_round'][atom_id]
        if key not in plan_by_pair or round_number < plan_by_pair[key]:
            plan_by_pair[key] = round_number
    rows = []
    for (arch, name), entry in blocked.items():
        rows.append((arch, name, entry['count'],
                     plan_by_pair.get((arch, name), 0), entry['action']))
    rows.sort(key=lambda row: (row[3], row[0], row[1]))
    write_tsv(paths['blocked_syscalls.tsv'],
              ('arch', 'syscall', 'block_count', 'first_round', 'worst_action'), rows)

    # capability gaps
    rows = []
    for gap in gaps:
        rows.append((gap['run_id'], gap['capability'], gap['unit'],
                     gap['in_bounding'], gap['in_permitted'], gap['delta']))
    rows.sort(key=lambda row: (row[0], row[1]))
    write_csv(paths['capability_gaps.csv'],
              ('run_id', 'capability', 'unit', 'in_bounding', 'in_permitted', 'delta'), rows)

    # audit continuity
    objects = []
    for run_id in corpus.run_ids:
        run = corpus.runs[run_id]
        permitted, effective = policy.cap_sets(run, [])
        has_capability = ADVISORY_CAPABILITY in effective
        audit_event = None
        for event in run['events']:
            if event['kind'] == 'audit':
                audit_event = event
                break
        ok, chosen, domain_in_force, missing, flags = policy.exec_decision(run, {})
        access_ok = True
        if audit_event is not None:
            for perm in audit_event['perms']:
                if not policy.allowed({}, domain_in_force, audit_event['target_type'],
                                      audit_event['tclass'], perm):
                    access_ok = False
                    break
        if has_capability and access_ok:
            continuity, reason = 'intact', ''
        elif not has_capability:
            continuity, reason = 'broken', 'capability'
        else:
            continuity, reason = 'broken', 'access'
        objects.append({'run_id': run_id, 'audit_capability': has_capability,
                        'audit_access': access_ok, 'continuity': continuity,
                        'break_reason': reason})
    write_jsonl(paths['audit_continuity.jsonl'], objects)

    # relaxation atoms
    rows = []
    for atom_id in corpus.atom_order:
        atom = corpus.atoms[atom_id]
        rows.append((atom_id, atom['layer'], atom['kind'], atom['cost'], atom['target'],
                     repairs_count[atom_id], 'yes' if atom_id in forbidden else 'no',
                     forbidden.get(atom_id, '')))
    write_csv(paths['relaxation_atoms.csv'],
              ('atom_id', 'layer', 'kind', 'cost', 'target', 'repairs_count',
               'forbidden', 'witness_run'), rows)

    # forbidden atoms
    rows = []
    for atom_id in corpus.atom_order:
        if atom_id in forbidden:
            atom = corpus.atoms[atom_id]
            rows.append((atom_id, atom['layer'], atom['kind'], atom['cost'],
                         forbidden[atom_id]))
    write_tsv(paths['forbidden_atoms.tsv'], None, rows)

    # grant plan
    rows = []
    for atom_id in plan_result['ordering']:
        atom = corpus.atoms[atom_id]
        rows.append((atom_id, atom['layer'], atom['kind'], atom['cost'],
                     plan_result['chosen_round'][atom_id], atom['target']))
    write_csv(paths['grant_plan.csv'],
              ('atom_id', 'layer', 'kind', 'cost', 'round', 'target'), rows)

    # iteration trace
    write_jsonl(paths['iteration_trace.jsonl'], plan_result['rounds'])

    # minimality witness
    witness_rows = []
    for atom_id in sorted(plan_result['plan']):
        reduced = plan_result['plan'] - {atom_id}
        reduced_applied = Applied(policy, reduced)
        witness = None
        for run_id in corpus.run_ids:
            run = corpus.runs[run_id]
            if run['label'] != 'must_admit':
                continue
            if final_verdicts[run_id]['verdict'] != 'admitted':
                continue
            if reduced_applied.replay(run)['verdict'] == 'denied':
                witness = run_id
                break
        if witness is None:
            witness_rows.append((atom_id, 'NONE', 'NONE', 0))
        else:
            outcome = reduced_applied.replay(corpus.runs[witness])
            witness_rows.append((atom_id, witness, outcome['layer'], outcome['seq']))
    write_csv(paths['minimality_witness.csv'],
              ('atom_id', 'witness_run', 'witness_layer', 'witness_seq'), witness_rows)

    # residual denials
    rows = []
    for run_id in corpus.run_ids:
        run = corpus.runs[run_id]
        if run['label'] != 'must_admit':
            continue
        if final_verdicts[run_id]['verdict'] == 'admitted':
            continue
        status = 'nonconvergent' if plan_result['rounds_used'] >= ROUND_CAP else 'unrepairable'
        rows.append((run_id, run['label'], status, plan_result['rounds_used'],
                     final_verdicts[run_id]['layer']))
    write_tsv(paths['residual_denials.tsv'],
              ('run_id', 'label', 'status', 'rounds_used', 'last_layer'), rows)

    # conservation
    admitted_initial = sum(1 for r in corpus.run_ids if verdicts[r]['verdict'] == 'admitted')
    denied_initial = len(corpus.run_ids) - admitted_initial
    admitted_final = sum(1 for r in corpus.run_ids if final_verdicts[r]['verdict'] == 'admitted')
    must_admit_total = sum(1 for r in corpus.run_ids if corpus.runs[r]['label'] == 'must_admit')
    must_admit_satisfied = sum(1 for r in corpus.run_ids
                               if corpus.runs[r]['label'] == 'must_admit'
                               and final_verdicts[r]['verdict'] == 'admitted')
    must_deny_total = sum(1 for r in corpus.run_ids if corpus.runs[r]['label'] == 'must_deny')
    must_deny_held = sum(1 for r in corpus.run_ids
                         if corpus.runs[r]['label'] == 'must_deny'
                         and final_verdicts[r]['verdict'] == 'denied')
    residual_count = sum(1 for r in corpus.run_ids
                         if corpus.runs[r]['label'] == 'must_admit'
                         and final_verdicts[r]['verdict'] == 'denied')
    write_json(paths['conservation.json'], {
        'total_runs': len(corpus.run_ids),
        'admitted_initial': admitted_initial,
        'denied_initial': denied_initial,
        'admitted_final': admitted_final,
        'must_admit_total': must_admit_total,
        'must_admit_satisfied': must_admit_satisfied,
        'must_deny_total': must_deny_total,
        'must_deny_held': must_deny_held,
        'residual_count': residual_count,
        'plan_cost': plan_result['total_cost'],
        'plan_size': len(plan_result['plan']),
        'rounds_used': plan_result['rounds_used'],
    })

    # summary
    layer_counts = {}
    for run_id in corpus.run_ids:
        layer = verdicts[run_id]['layer']
        layer_counts[layer] = layer_counts.get(layer, 0) + 1
    label_counts = {}
    for run_id in corpus.run_ids:
        label = corpus.runs[run_id]['label']
        label_counts[label] = label_counts.get(label, 0) + 1
    arch_runs = {}
    for arch in ARCHES:
        arch_runs[arch] = sum(1 for r in corpus.run_ids
                              if corpus.runs[r]['dispatch_arch'] == arch)
    atom_kind_counts = {}
    for atom_id in plan_result['plan']:
        kind = corpus.atoms[atom_id]['kind']
        atom_kind_counts[kind] = atom_kind_counts.get(kind, 0) + 1
    audit_broken = sum(1 for obj in objects if obj['continuity'] == 'broken')
    write_json(paths['summary.json'], {
        'layer_counts': {key: layer_counts[key] for key in sorted(layer_counts)},
        'label_counts': {key: label_counts[key] for key in sorted(label_counts)},
        'arch_runs': {arch: arch_runs[arch] for arch in ARCHES},
        'repair_counts': {name: corpus.repairs[name] for name in sorted(corpus.repairs)},
        'atom_kind_counts': {key: atom_kind_counts[key] for key in sorted(atom_kind_counts)},
        'blocked_syscall_rows': len(blocked),
        'capability_gap_rows': len(gaps),
        'audit_broken_runs': audit_broken,
        'forbidden_atom_rows': len(forbidden),
    })

    # manifest
    manifest = {}
    for name in ARTIFACT_ORDER:
        data = open(paths[name], 'rb').read()
        manifest[name] = {'bytes': len(data), 'lines': data.count(b'\n'),
                          'sha256': hashlib.sha256(data).hexdigest()}
    write_json(paths['manifest.json'], manifest)


if __name__ == '__main__':
    sys.exit(main(sys.argv))

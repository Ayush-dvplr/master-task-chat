#!/usr/bin/env python3
"""Workspace dependency lock resolver.

Reads the five intake files from an input folder, settles the workspace under
the mode word found in that folder's manifest.json, and writes lock.json,
issues.jsonl and summary.json into the output folder.

Usage: python3 lockres.py IN_DIR OUT_DIR
"""

import csv
import hashlib
import json
import os
import re
import sys
from collections import deque

NAME_RE = re.compile(r'^[a-z][a-z0-9-]{0,39}$')
VER_RE = re.compile(
    r'^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-rc\.(0|[1-9][0-9]*))?$')
SHA_RE = re.compile(r'^[0-9a-f]{40}$')
PUBLISH_KEYS = {'seq', 'pkg', 'ver', 'deps', 'sha'}
YANK_KEYS = {'seq', 'pkg', 'ver', 'yank'}

MODE_BITS = (2, 4, 8, 16, 32, 64, 128)


# --------------------------------------------------------------------------- #
# versions and ranges
# --------------------------------------------------------------------------- #

def version_tuple(text):
    """Return a sort key for a version string, or None if it is not a version."""
    m = VER_RE.match(text) if isinstance(text, str) else None
    if not m:
        return None
    rc = m.group(4)
    if rc is None:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)), 1, 0)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), 0, int(rc))


def is_version(text):
    return version_tuple(text) is not None


def is_release(text):
    return is_version(text) and '-rc.' not in text


def parse_range(text):
    """Return a list of groups, each a list of (op, version_string) clauses."""
    if not isinstance(text, str):
        raise ValueError('range must be a string')
    groups = []
    for group_text in text.split('|'):
        clauses = []
        for clause_text in group_text.split(','):
            clause_text = clause_text.strip()
            if clause_text == '*':
                clauses.append((None, None))
                continue
            m = re.match(r'^(=|>=|<|\^|~)(.+)$', clause_text)
            if not m or not is_version(m.group(2)):
                raise ValueError('bad clause %r' % clause_text)
            clauses.append((m.group(1), m.group(2)))
        groups.append(clauses)
    return groups


def is_range(text):
    try:
        parse_range(text)
    except ValueError:
        return False
    return True


def clause_holds(version, op, target):
    if op is None:
        return True
    other = version_tuple(target)
    if op == '=':
        return version == other
    if op == '>=':
        return version >= other
    if op == '<':
        return version < other
    if op == '^':
        if other[0] > 0:
            ceiling = (other[0] + 1, 0, 0, 1, 0)
        elif other[1] > 0:
            ceiling = (0, other[1] + 1, 0, 1, 0)
        else:
            ceiling = (0, 0, other[2] + 1, 1, 0)
        return other <= version < ceiling
    if op == '~':
        return other <= version < (other[0], other[1] + 1, 0, 1, 0)
    raise ValueError('unknown operator %r' % op)


def range_holds(version, groups, rc_open):
    """Does a version meet a parsed range?

    A release candidate only meets a group that names a release candidate of
    its own, unless rc_open is set.
    """
    for clauses in groups:
        if not rc_open and version_is_candidate(version):
            if not any(op is not None and '-rc.' in target
                       for op, target in clauses):
                continue
        if not all(clause_holds(version, op, target) for op, target in clauses):
            continue
        return True
    return False


def version_is_candidate(version):
    return isinstance(version, tuple) and version[3] == 0


def make_matcher(rc_open):
    cache = {}

    def matches(version, range_text):
        groups = cache.get(range_text)
        if groups is None:
            groups = parse_range(range_text)
            cache[range_text] = groups
        return range_holds(version_tuple(version), groups, rc_open)

    return matches


# --------------------------------------------------------------------------- #
# intake files
# --------------------------------------------------------------------------- #

def read_lines(path):
    with open(path, 'rb') as handle:
        raw = handle.read()
    lines = raw.split(b'\n')
    if lines and lines[-1] == b'':
        lines.pop()
    return lines


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def valid_publish(record):
    if not is_int(record['seq']) or record['seq'] < 1:
        return False
    if not isinstance(record.get('pkg'), str) or not NAME_RE.match(record['pkg']):
        return False
    if not is_version(record.get('ver')):
        return False
    if not isinstance(record.get('sha'), str) or not SHA_RE.match(record['sha']):
        return False
    deps = record.get('deps')
    if not isinstance(deps, dict):
        return False
    for dep_pkg, dep_range in deps.items():
        if not isinstance(dep_pkg, str) or not NAME_RE.match(dep_pkg):
            return False
        if dep_pkg == record['pkg']:
            return False
        if not is_range(dep_range):
            return False
    return True


def valid_yank(record):
    if record['yank'] is not True:
        return False
    if not is_int(record['seq']) or record['seq'] < 1:
        return False
    if not isinstance(record.get('pkg'), str) or not NAME_RE.match(record['pkg']):
        return False
    return is_version(record.get('ver'))


def read_index(path):
    """Screen the feed. Return (malformed, retransmitted, publishes, yanks)."""
    malformed = 0
    retransmitted = 0
    publishes = []
    yanks = []
    seen = set()
    for line in read_lines(path):
        if line.strip() == b'':
            continue
        try:
            record = json.loads(line.decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            malformed += 1
            continue
        if not isinstance(record, dict):
            malformed += 1
            continue
        keys = set(record)
        if keys == PUBLISH_KEYS:
            if not valid_publish(record):
                malformed += 1
                continue
        elif keys == YANK_KEYS:
            if not valid_yank(record):
                malformed += 1
                continue
        else:
            malformed += 1
            continue
        digest = json.dumps(record, sort_keys=True)
        if digest in seen:
            retransmitted += 1
            continue
        seen.add(digest)
        (yanks if 'yank' in record else publishes).append(record)
    return malformed, retransmitted, publishes, yanks


def read_pins(path, last_wins):
    """Return the pins in force and the number of valid pins."""
    pins = {}
    with open(path, newline='', encoding='utf-8') as handle:
        for row in csv.reader(handle):
            if not row:
                continue
            if row[0].strip().lower() == 'pkg' and row[1].strip().lower() == 'range':
                continue
            if len(row) < 3:
                continue
            pkg = row[0]
            pin_range = row[1]
            if not NAME_RE.match(pkg) or not is_range(pin_range):
                continue
            if last_wins or pkg not in pins:
                pins[pkg] = pin_range
    return pins


def read_json(path):
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


# --------------------------------------------------------------------------- #
# screening rules
# --------------------------------------------------------------------------- #

def choose_copies(publishes, keep_highest):
    """Pick the kept copy of every package version; count republished extras."""
    kept = {}
    republished = 0
    for record in publishes:
        key = (record['pkg'], record['ver'])
        current = kept.get(key)
        if current is None:
            kept[key] = record
            continue
        if current['sha'] == record['sha']:
            continue
        republished += 1
        if keep_highest:
            if record['seq'] > current['seq']:
                kept[key] = record
        elif record['seq'] < current['seq']:
            kept[key] = record
    return kept, republished


def settle_yanks(kept, yanks, force_apply):
    """Split accepted yank lines into applied and ignored."""
    yanked = set()
    applied = 0
    ignored = 0
    for record in yanks:
        key = (record['pkg'], record['ver'])
        published = kept.get(key)
        if published is None:
            ignored += 1
            continue
        if force_apply or record['seq'] > published['seq']:
            yanked.add(key)
            applied += 1
        else:
            ignored += 1
    return yanked, applied, ignored


# --------------------------------------------------------------------------- #
# resolution
# --------------------------------------------------------------------------- #

def order_requirements(deps, descending):
    items = list(deps.items())
    items.sort(key=lambda item: item[0], reverse=descending)
    return items


def resolve(feed, workspace, previous, pins, options):
    """Walk the requirement queue and return the lock, issues and counts."""
    matches = make_matcher(options['rc_open'])
    kept = feed['kept']
    yanked = feed['yanked']
    by_package = {}
    for (pkg, ver), record in kept.items():
        by_package.setdefault(pkg, []).append((version_tuple(ver), ver, record))
    for versions in by_package.values():
        versions.sort(key=lambda item: item[0])

    queue = deque()
    for member in workspace['members']:
        requester = 'member:' + member['name']
        for pkg, dep_range in order_requirements(member['deps'],
                                                 options['member_descending']):
            queue.append((pkg, dep_range, requester))

    lock = {}
    via = {}
    issues = []
    sticky = 0

    while queue:
        pkg, dep_range, requester = queue.popleft()
        if pkg in lock:
            if not matches(lock[pkg], dep_range):
                issues.append({'kind': 'conflict', 'pkg': pkg, 'range': dep_range,
                                'by': requester, 'picked': lock[pkg]})
            continue
        pin = pins.get(pkg)
        candidates = [entry for entry in by_package.get(pkg, [])
                      if (pkg, entry[1]) not in yanked
                      and matches(entry[1], dep_range)
                      and (pin is None or matches(entry[1], pin))]
        if not candidates:
            issues.append({'kind': 'unresolved', 'pkg': pkg, 'range': dep_range,
                           'by': requester})
            continue
        chosen = None
        if options['sticky_all'] or requester.startswith('member:'):
            held = previous.get(pkg)
            if held is not None and is_version(held.get('version')):
                for entry in candidates:
                    if entry[1] == held['version']:
                        chosen = entry
                        sticky += 1
                        break
        if chosen is None:
            chosen = candidates[-1] if options['pick_highest'] else candidates[0]
        lock[pkg] = chosen[1]
        via[pkg] = requester
        if options['walk_deps']:
            requester = '%s@%s' % (pkg, chosen[1])
            for dep_pkg, dep_range in order_requirements(chosen[2]['deps'],
                                                         options['dep_descending']):
                queue.append((dep_pkg, dep_range, requester))
    return lock, via, issues, sticky


# --------------------------------------------------------------------------- #
# reports
# --------------------------------------------------------------------------- #

def lock_lines(lock, kept):
    return ''.join('%s@%s:%s\n' % (pkg, ver, kept[(pkg, ver)]['sha'])
                  for pkg, ver in sorted(lock.items()))


def chain_owner(pkg, via):
    """Follow a pick's via chain back to the member that asked for it."""
    owner = via.get(pkg)
    seen = {pkg}
    while owner is not None and not owner.startswith('member:'):
        parent = owner.split('@', 1)[0]
        if parent in seen:
            return None
        seen.add(parent)
        owner = via.get(parent)
    return owner


def member_lines(lock, via, kept, member):
    """Lines of one member's share of the lock, in package name order."""
    lines = []
    for pkg, ver in sorted(lock.items()):
        if chain_owner(pkg, via) == 'member:' + member:
            lines.append('%s@%s:%s\n' % (pkg, ver, kept[(pkg, ver)]['sha']))
    return ''.join(lines)


def render(lock, via, issues, kept, counts):
    packages = {}
    for pkg, ver in lock.items():
        packages[pkg] = {'sha': kept[(pkg, ver)]['sha'],
                         'version': ver, 'via': via[pkg]}
    lock_bytes = (json.dumps({'packages': packages}, sort_keys=True,
                             indent=2) + '\n').encode('utf-8')
    issues_text = ''.join(
        json.dumps(issue, sort_keys=True, separators=(',', ':')) + '\n'
        for issue in issues)
    summary = dict(counts)
    summary['picked'] = len(lock)
    summary['conflicts'] = sum(1 for i in issues if i['kind'] == 'conflict')
    summary['unresolved'] = sum(1 for i in issues if i['kind'] == 'unresolved')
    summary['lock_digest'] = hashlib.sha256(
        lock_lines(lock, kept).encode('utf-8')).hexdigest()
    summary_bytes = (json.dumps(summary, sort_keys=True, indent=2)
                     + '\n').encode('utf-8')
    return lock_bytes, issues_text.encode('utf-8'), summary_bytes


def write_reports(out_dir, lock_bytes, issues_bytes, summary_bytes):
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    for name, data in (('lock.json', lock_bytes), ('issues.jsonl', issues_bytes),
                       ('summary.json', summary_bytes)):
        with open(os.path.join(out_dir, name), 'wb') as handle:
            handle.write(data)


# --------------------------------------------------------------------------- #
# mode word
# --------------------------------------------------------------------------- #

def options_for_mode(mode):
    """Turn the mode word into resolver options.

    Mode zero follows the written conventions and the worked examples. Each of
    the seven mode bits switches one further step to its other reading. The
    reserved value 1 is always clear and is masked off if it ever appears.
    """
    options = {
        'rc_open': False,
        'keep_highest': False,
        'force_yank': False,
        'sticky_all': False,
        'member_descending': True,
        'dep_descending': True,
        'pin_last_wins': False,
        'pick_highest': True,
        'walk_deps': True,
    }
    bits = set()
    value = mode if isinstance(mode, int) and not isinstance(mode, bool) else 0
    value &= ~1
    shift = 0
    while value:
        if value & 1:
            bits.add(1 << shift)
        value >>= 1
        shift += 1
    for bit, key in zip(MODE_BITS, ('rc_open', 'keep_highest', 'force_yank',
                                    'sticky_all', 'member_descending',
                                    'dep_descending', 'pin_last_wins')):
        if bit in bits:
            options[key] = not options[key]
    return options


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #

def run(in_dir, out_dir):
    manifest = read_json(os.path.join(in_dir, 'manifest.json'))
    mode = manifest.get('mode', 0)
    options = options_for_mode(mode)

    malformed, retransmitted, publishes, yanks = read_index(
        os.path.join(in_dir, 'index.jsonl'))
    workspace = read_json(os.path.join(in_dir, 'workspace.json'))
    previous = read_json(os.path.join(in_dir, 'lock.prev.json')).get('packages', {})
    pins = read_pins(os.path.join(in_dir, 'pins.csv'), options['pin_last_wins'])

    kept, republished = choose_copies(publishes, options['keep_highest'])
    yanked, yanks_applied, yanks_ignored = settle_yanks(
        kept, yanks, options['force_yank'])
    feed = {'kept': kept, 'yanked': yanked}

    lock, via, issues, sticky = resolve(feed, workspace, previous, pins, options)

    counts = {
        'malformed': malformed,
        'retransmitted': retransmitted,
        'republished': republished,
        'yanks_applied': yanks_applied,
        'yanks_ignored': yanks_ignored,
        'sticky': sticky,
        'pins': len(pins),
    }
    lock_bytes, issues_bytes, summary_bytes = render(lock, via, issues, kept, counts)
    write_reports(out_dir, lock_bytes, issues_bytes, summary_bytes)
    return lock, via, issues, summary_bytes, kept


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: lockres.py IN_DIR OUT_DIR\n')
        return 2
    run(argv[1], argv[2])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))

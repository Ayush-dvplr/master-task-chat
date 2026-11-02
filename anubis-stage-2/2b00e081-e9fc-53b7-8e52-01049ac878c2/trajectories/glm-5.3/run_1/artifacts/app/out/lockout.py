#!/usr/bin/env python3
"""Replay a sign-in attempt journal into a lockout table.

Usage: python3 lockout.py IN_DIR OUT_DIR

Reads attempts.jsonl, policy.json, overrides.csv, locks.prev.json and manifest.json
from IN_DIR, replays the accepted records and writes locks.json, decisions.jsonl
and summary.json into OUT_DIR.

The replay follows the written conventions plus six rules the notes never
recorded, which were recovered from the worked examples (see AGENTS.md):

  1. A user is NOT locked at the very second its lock ends (the end is exclusive).
  2. A failure exactly `window` seconds old still counts.
  3. The FIRST valid overrides.csv row for a user stands.
  4. A pass from a locked user gets deny (and does not clear anything).
  5. A repeat lock lasts lock * 2^(strikes-1) seconds.
  6. Records sharing one second are replayed reset, pass, fail, probe, then by seq.

The mode word in manifest.json uses the bits 2, 4, 8, 16, 32, 64 and 128. Each set
bit changes exactly one step of the replay. The readings implemented here are
listed with BIT_READINGS below; bit 1 is reserved and always clear.
"""

import hashlib
import json
import os
import re
import sys

USER_RE = re.compile(r'^[a-z][a-z0-9._-]{0,30}$')
AGENT_RE = re.compile(r'^[A-Za-z0-9/._-]{1,40}$')
KINDS = ('reset', 'pass', 'fail', 'probe')
KIND_ORDER = {'reset': 0, 'pass': 1, 'fail': 2, 'probe': 3}

RESULTS = ('allow', 'fail', 'lock', 'deny', 'unlock', 'ban', 'ignore')

# What each mode bit is taken to do. The evidence for each reading is noted in
# AGENTS.md. Bit 1 is reserved and always clear.
BIT_SCREEN = 2      # retransmission compares content without seq
BIT_SEED = 4        # the previous table seeds the lock end but not the strikes
BIT_LIMIT = 8       # OPEN: mode 0 rule kept (the first valid row stands)
BIT_COUNT = 16      # probes are counted as attempts (they feed the failure list
                    # and the source counter, but only a fail locks)
BIT_SOURCE = 32     # per-source attempt counter; ban_after and ban become live
BIT_LOCK = 64       # a pass from a locked user is denied but clears the lock
BIT_BAN = 128       # a ban also locks the user whose record triggered it


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def valid_user(value):
    return isinstance(value, str) and USER_RE.match(value) is not None


def valid_src(value):
    if not isinstance(value, str):
        return False
    parts = value.split('.')
    if len(parts) != 4:
        return False
    for part in parts:
        if not part.isdigit() or not part.isascii():
            return False
        if len(part) > 1 and part[0] == '0':
            return False
        if int(part) > 255:
            return False
    return True


def valid_agent(value):
    if value is None:
        return True
    return isinstance(value, str) and AGENT_RE.match(value) is not None


def valid_record(obj):
    if not isinstance(obj, dict):
        return False
    if set(obj.keys()) != {'seq', 'kind', 'user', 'src', 'at', 'agent'}:
        return False
    if not is_int(obj['seq']) or obj['seq'] < 1:
        return False
    if obj['kind'] not in KINDS:
        return False
    if not valid_user(obj['user']):
        return False
    if not valid_src(obj['src']):
        return False
    if not is_int(obj['at']) or obj['at'] < 0:
        return False
    return valid_agent(obj['agent'])


def screen_journal(path, dedup_without_seq):
    """Read the journal, returning (accepted, malformed, retransmitted, conflicting)."""
    accepted = []
    malformed = 0
    retransmitted = 0
    conflicting = 0
    seen = set()
    used_seq = set()
    with open(path, 'rb') as handle:
        raw = handle.read()
    for raw_line in raw.split(b'\n'):
        try:
            text = raw_line.decode('utf-8')
        except UnicodeDecodeError:
            malformed += 1
            continue
        if text.strip() == '':
            continue
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if not valid_record(obj):
            malformed += 1
            continue
        if dedup_without_seq:
            content = json.dumps({k: v for k, v in obj.items() if k != 'seq'},
                                 sort_keys=True, separators=(',', ':'))
        else:
            content = json.dumps(obj, sort_keys=True, separators=(',', ':'))
        if content in seen:
            retransmitted += 1
            continue
        seen.add(content)
        if obj['seq'] in used_seq:
            conflicting += 1
            continue
        used_seq.add(obj['seq'])
        accepted.append(obj)
    return accepted, malformed, retransmitted, conflicting


def read_overrides(path):
    """Return the valid (user, limit) rows of overrides.csv in file order."""
    rows = []
    with open(path, encoding='utf-8') as handle:
        lines = handle.read().split('\n')
    if not lines or lines[0].strip() != 'user,limit,note':
        return rows
    for line in lines[1:]:
        if line == '':
            continue
        fields = line.split(',')
        if len(fields) != 3:
            continue
        user, limit, _note = fields
        if not valid_user(user):
            continue
        if len(limit) != 1 or limit not in '123456789':
            continue
        rows.append((user, int(limit)))
    return rows


def override_limits(rows, last_wins):
    limits = {}
    for user, limit in rows:
        if last_wins or user not in limits:
            limits[user] = limit
    return limits


def read_previous(path):
    """Return the seeded rows of locks.prev.json in file order."""
    with open(path, encoding='utf-8') as handle:
        doc = json.load(handle)
    seeded = []
    seen = set()
    for row in doc.get('locks', []):
        if not isinstance(row, dict):
            continue
        user = row.get('user')
        until = row.get('until')
        strikes = row.get('strikes')
        if not valid_user(user) or not is_int(until) or not is_int(strikes) or strikes < 1:
            continue
        if user in seen:
            continue
        seen.add(user)
        seeded.append((user, until, strikes))
    return seeded


def read_manifest(path):
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


def replay(accepted, policy, limits, seeded, mode):
    """Replay accepted records and return the tables and the decision lines."""
    window = policy['window']
    threshold = policy['threshold']
    lock_len = policy['lock']
    ban_after = policy.get('ban_after')
    ban_len = policy.get('ban')

    probes_count = mode & BIT_COUNT != 0
    source_bans = mode & BIT_SOURCE != 0
    pass_clears = mode & BIT_LOCK != 0
    ban_locks_user = mode & BIT_BAN != 0
    seed_strikes = mode & BIT_SEED == 0  # bit 4: the seed carries the lock end only

    users = {}
    for user, until, strikes in seeded:
        users[user] = {
            'until': until,
            'strikes': strikes if seed_strikes else 0,
            'fails': [],
            'ban_lock': False,
        }

    records = sorted(accepted, key=lambda r: (r['at'], KIND_ORDER[r['kind']], r['seq']))
    decisions = []
    counts = {name: 0 for name in RESULTS}
    bans = {}
    src_attempts = {}

    for rec in records:
        user = rec['user']
        src = rec['src']
        at = rec['at']
        kind = rec['kind']
        state = users.setdefault(user, {'until': None, 'strikes': 0, 'fails': [], 'ban_lock': False})

        if source_bans and (kind == 'fail' or (kind == 'probe' and probes_count)):
            attempts = src_attempts.setdefault(src, [])
            attempts[:] = [x for x in attempts if at - x <= window]
            attempts.append(at)

        locked = state['until'] is not None and at < state['until']
        is_attempt = kind == 'fail' or (kind == 'probe' and probes_count)

        if is_attempt:
            if locked:
                result = 'deny'
            else:
                fails = state['fails']
                fails[:] = [x for x in fails if at - x <= window]
                fails.append(at)
                limit = limits.get(user, threshold)
                if kind == 'fail' and len(fails) >= limit:
                    state['strikes'] += 1
                    state['until'] = at + lock_len * (1 << (state['strikes'] - 1))
                    state['fails'] = []
                    result = 'lock'
                else:
                    result = 'fail'
        elif kind == 'pass':
            if locked:
                result = 'deny'
                if pass_clears and not state['ban_lock']:
                    state['until'] = None
                    state['strikes'] = 0
                    state['fails'] = []
            else:
                result = 'allow'
        elif kind == 'reset':
            was_locked = locked
            state['fails'] = []
            state['until'] = None
            result = 'unlock' if was_locked else 'ignore'
        else:
            result = 'ignore'

        if source_bans and ban_after is not None and is_attempt:
            attempts = src_attempts.get(src, [])
            if len(attempts) >= ban_after and src not in bans:
                bans[src] = at + ban_len
                result = 'ban'
                if ban_locks_user:
                    state['strikes'] += 1
                    state['until'] = at + lock_len * (1 << (state['strikes'] - 1))
                    state['fails'] = []
                    state['ban_lock'] = True

        counts[result] += 1
        decisions.append({'at': at, 'kind': kind, 'result': result,
                          'seq': rec['seq'], 'src': src, 'user': user})

    last_at = max(r['at'] for r in records) if records else 0
    active = {}
    for user, state in users.items():
        if state['until'] is not None and last_at < state['until']:
            active[user] = {'strikes': state['strikes'], 'until': state['until']}
    return active, bans, decisions, counts


def table_lines(mapping):
    return sorted('%s %d\n' % (key, until) for key, until in mapping.items())


def digest(lines):
    return hashlib.sha256(''.join(lines).encode('utf-8')).hexdigest()


def build_reports(active, bans, decisions, counts, screening, overrides):
    locks_doc = {
        'bans': {src: {'until': until} for src, until in sorted(bans.items())},
        'locks': {user: {'strikes': data['strikes'], 'until': data['until']}
                  for user, data in sorted(active.items())},
    }
    locks_json = json.dumps(locks_doc, sort_keys=True, indent=2) + '\n'
    decisions_jsonl = ''.join(
        json.dumps(rec, sort_keys=True, separators=(',', ':')) + '\n' for rec in decisions)
    active_digest = digest(table_lines({u: v['until'] for u, v in active.items()}))
    summary = {
        'malformed': screening['malformed'],
        'retransmitted': screening['retransmitted'],
        'conflicting': screening['conflicting'],
        'events': screening['events'],
        'allows': counts['allow'],
        'fails': counts['fail'],
        'locks': counts['lock'],
        'denies': counts['deny'],
        'unlocks': counts['unlock'],
        'bans': counts['ban'],
        'ignored': counts['ignore'],
        'active': len(active),
        'banned': len(bans),
        'overrides': overrides,
        'table_digest': active_digest,
    }
    summary_json = json.dumps(summary, sort_keys=True, indent=2) + '\n'
    return locks_json, decisions_jsonl, summary_json


def run(in_dir, out_dir):
    manifest = read_manifest(os.path.join(in_dir, 'manifest.json'))
    mode = manifest.get('mode', 0)
    if not is_int(mode) or mode < 0:
        mode = 0
    with open(os.path.join(in_dir, 'policy.json'), encoding='utf-8') as handle:
        policy = json.load(handle)

    accepted, malformed, retransmitted, conflicting = screen_journal(
        os.path.join(in_dir, 'attempts.jsonl'), mode & BIT_SCREEN != 0)
    rows = read_overrides(os.path.join(in_dir, 'overrides.csv'))
    limits = override_limits(rows, False)  # bit 8 is open; mode 0 rule applies
    seeded = read_previous(os.path.join(in_dir, 'locks.prev.json'))

    active, bans, decisions, counts = replay(accepted, policy, limits, seeded, mode)

    screening = {'malformed': malformed, 'retransmitted': retransmitted,
                 'conflicting': conflicting, 'events': len(accepted)}
    locks_json, decisions_jsonl, summary_json = build_reports(
        active, bans, decisions, counts, screening, len(set(u for u, _ in rows)))

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'locks.json'), 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(locks_json)
    with open(os.path.join(out_dir, 'decisions.jsonl'), 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(decisions_jsonl)
    with open(os.path.join(out_dir, 'summary.json'), 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(summary_json)
    return 0


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: lockout.py IN_DIR OUT_DIR\n')
        return 2
    return run(argv[1], argv[2])


if __name__ == '__main__':
    sys.exit(main(sys.argv))

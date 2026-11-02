"""Replay an arena slot request journal into a session table.

Usage: python3 arena.py IN_DIR OUT_DIR
Reads requests.jsonl, servers.json, owned.csv, sessions.prev.json and manifest.json
from IN_DIR and writes sessions.json, decisions.jsonl and summary.json to OUT_DIR.
"""


import hashlib
import json
import re
import sys
from collections import Counter

PLAYER_RE = re.compile(r'^[a-z][a-z0-9._-]{0,30}$')
SERVER_RE = re.compile(r'^[a-z][a-z0-9-]{0,20}$')
CLAN_RE = re.compile(r'^[a-z][a-z0-9-]{0,15}$')
RECORD_KEYS = ('seq', 'kind', 'player', 'at', 'party', 'span', 'server', 'clan')
KINDS = ('claim', 'extend', 'release', 'ping')
KIND_ORDER = {'release': 0, 'extend': 1, 'claim': 2, 'ping': 3}
BIT_HINT, BIT_SEED, BIT_COOL, BIT_OWNED = 2, 4, 8, 16
BIT_RETRANS, BIT_EXTEND, BIT_CLAN = 32, 64, 128


def is_integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def valid_player(value):
    return isinstance(value, str) and bool(PLAYER_RE.match(value))


def valid_server_name(value):
    return isinstance(value, str) and bool(SERVER_RE.match(value))


def valid_clan(value):
    return value is None or (isinstance(value, str) and bool(CLAN_RE.match(value)))


def valid_record(record):
    if not isinstance(record, dict) or set(record.keys()) != set(RECORD_KEYS):
        return False
    if not is_integer(record['seq']) or record['seq'] < 1:
        return False
    if record['kind'] not in KINDS:
        return False
    if not valid_player(record['player']):
        return False
    if not is_integer(record['at']) or record['at'] < 0:
        return False
    if not is_integer(record['party']) or not 1 <= record['party'] <= 40:
        return False
    if not is_integer(record['span']) or record['span'] < 60 or record['span'] % 60:
        return False
    if record['server'] is not None and not valid_server_name(record['server']):
        return False
    if not valid_clan(record['clan']):
        return False
    return True


def read_text_lines(path):
    with open(path, 'rb') as handle:
        raw = handle.read()
    lines = raw.split(b'\n')
    if lines and lines[-1] == b'':
        lines.pop()
    return lines


def screen_journal(path, compare_with_seq):
    """Apply screening steps 1-4 and return counts plus accepted records."""
    counts = Counter()
    seen_contents = set()
    seen_seqs = set()
    accepted = []
    for blob in read_text_lines(path):
        text = blob.decode('utf-8', 'replace')
        if text.strip() == '':
            continue
        try:
            record = json.loads(text)
        except ValueError:
            counts['malformed'] += 1
            continue
        if not valid_record(record):
            counts['malformed'] += 1
            continue
        fields = [key for key in RECORD_KEYS if compare_with_seq or key != 'seq']
        content = json.dumps({key: record[key] for key in fields}, sort_keys=True)
        if content in seen_contents:
            counts['retransmitted'] += 1
            continue
        if record['seq'] in seen_seqs:
            counts['conflicting'] += 1
            continue
        seen_contents.add(content)
        seen_seqs.add(record['seq'])
        accepted.append(record)
    return counts, accepted


def load_servers(path):
    with open(path, 'rb') as handle:
        doc = json.loads(handle.read().decode('utf-8'))
    rows = doc.get('servers', []) if isinstance(doc, dict) else []
    servers = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = row.get('name')
        slots = row.get('slots')
        if not valid_server_name(name):
            continue
        if not is_integer(slots) or slots < 1:
            continue
        if name in seen:
            continue
        seen.add(name)
        servers.append((name, slots))
    return servers


def load_owned(path, servers):
    """Return the owned server per player; the first counted row for a player stands."""
    names = {name for name, _ in servers}
    owned = {}
    for index, blob in enumerate(read_text_lines(path)):
        text = blob.decode('utf-8', 'replace')
        if index == 0:
            continue
        if text.strip() == '':
            continue
        fields = text.split(',')
        if len(fields) != 3:
            continue
        player, server = fields[0], fields[1]
        if not valid_player(player) or server not in names:
            continue
        if player not in owned:
            owned[player] = server
    return owned


def load_previous(path, servers, seed_per_player):
    """Seed the session table from the previous replay."""
    names = {name for name, _ in servers}
    with open(path, 'rb') as handle:
        doc = json.loads(handle.read().decode('utf-8'))
    rows = doc.get('sessions', []) if isinstance(doc, dict) else []
    seeded = []
    used_servers = set()
    used_players = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        server = row.get('server')
        player = row.get('player')
        until = row.get('until')
        clan = row.get('clan')
        if server not in names:
            continue
        if not valid_player(player):
            continue
        if not is_integer(until):
            continue
        if not valid_clan(clan):
            continue
        if seed_per_player:
            if player in used_players:
                continue
        elif server in used_servers:
            continue
        used_servers.add(server)
        used_players.add(player)
        seeded.append((server, player, until, clan))
    return seeded


def cooldown_end(mode_word, release_at, release_span, session_until):
    """Return the second at which a released server stops cooling down."""
    if release_span is None:
        return release_at + 1
    if mode_word & BIT_COOL:
        return release_at + release_span // 4
    return release_at + release_span


class Replay:
    def __init__(self, servers, owned, seeded, mode_word):
        self.slots = dict(servers)
        self.order = [name for name, _ in servers]
        self.owned = owned
        self.owners = {}
        for player, server in owned.items():
            self.owners.setdefault(server, set()).add(player)
        self.mode = mode_word
        self.sessions = {}
        for server, player, until, clan in seeded:
            self.sessions[server] = {'player': player, 'until': until, 'clan': clan}
        self.cooldowns = {}
        self.last_clan = {}

    def occupied(self, server, at):
        session = self.sessions.get(server)
        return session is not None and session['until'] >= at

    def holder_live(self, player, at):
        for session in self.sessions.values():
            if session['player'] == player and session['until'] > at:
                return True
        return False

    def holder_server(self, player, at):
        for server, session in self.sessions.items():
            if session['player'] == player and session['until'] > at:
                return server
        return None

    def cooling(self, server, at):
        return server in self.cooldowns and self.cooldowns[server] >= at

    def usable(self, server, player, party, at, ignore_ownership):
        if server not in self.slots:
            return False
        if ignore_ownership:
            if self.slots[server] <= party:
                return False
        elif self.slots[server] < party:
            return False
        if self.occupied(server, at):
            return False
        if self.cooling(server, at):
            return False
        if not ignore_ownership and server in self.owners:
            return False
        return True

    def pick_server(self, record, at):
        player = record['player']
        party = record['party']
        owned = self.owned.get(player)
        if owned is not None and self.usable(owned, player, party, at, True):
            return owned
        if self.mode & BIT_OWNED and owned is not None and not self.usable(owned, player, party, at, True):
            return None
        hint = record['server']
        hint_usable = hint is not None and self.usable(hint, player, party, at, False)
        if not (self.mode & BIT_HINT) and hint_usable:
            return hint
        for name in self.order:
            if self.usable(name, player, party, at, False):
                return name
        if self.mode & BIT_HINT and hint_usable:
            return hint
        return None

    def session_clan(self, record):
        if self.mode & BIT_CLAN:
            player = record['player']
            if record['clan'] is None and player in self.last_clan:
                return self.last_clan[player]
        return record['clan']

    def place(self, record, at):
        server = self.pick_server(record, at)
        if server is None:
            return 'refuse'
        self.sessions[server] = {
            'player': record['player'],
            'until': at + record['span'],
            'clan': self.session_clan(record),
        }
        return 'claim'

    def apply(self, record):
        at = record['at']
        player = record['player']
        kind = record['kind']
        if kind == 'ping':
            return 'ignore'
        if kind == 'claim':
            if self.holder_live(player, at):
                return 'refuse'
            return self.place(record, at)
        if kind == 'extend':
            server = self.holder_server(player, at)
            if server is not None:
                self.sessions[server]['until'] += record['span']
                return 'extend'
            if self.mode & BIT_EXTEND:
                return self.place(record, at)
            return 'ignore'
        if kind == 'release':
            server = self.holder_server(player, at)
            if server is None:
                return 'ignore'
            session = self.sessions.pop(server)
            owned = self.owned.get(player)
            release_span = None if server == owned else record['span']
            end = cooldown_end(self.mode, at, release_span, session['until'])
            if end is not None:
                self.cooldowns[server] = max(self.cooldowns.get(server, end), end)
            return 'release'
        return 'ignore'


def replay(in_dir, mode_word):
    counts, records = screen_journal(in_dir + '/requests.jsonl', not (mode_word & BIT_RETRANS))
    servers = load_servers(in_dir + '/servers.json')
    owned = load_owned(in_dir + '/owned.csv', servers)
    seeded = load_previous(in_dir + '/sessions.prev.json', servers, bool(mode_word & BIT_SEED))
    records.sort(key=lambda rec: (rec['at'], KIND_ORDER[rec['kind']], rec['seq']))
    engine = Replay(servers, owned, seeded, mode_word)
    decisions = []
    results = Counter()
    for record in records:
        result = engine.apply(record)
        if record['clan'] is not None:
            engine.last_clan[record['player']] = record['clan']
        results[result] += 1
        decisions.append({
            'at': record['at'],
            'kind': record['kind'],
            'player': record['player'],
            'result': result,
            'seq': record['seq'],
        })
    last = records[-1]['at'] if records else 0
    sessions = {
        server: {'clan': entry['clan'], 'player': entry['player'], 'until': entry['until']}
        for server, entry in engine.sessions.items() if entry['until'] > last
    }
    cooldowns = {server: end for server, end in engine.cooldowns.items() if end > last}
    summary = {
        'malformed': counts['malformed'],
        'retransmitted': counts['retransmitted'],
        'conflicting': counts['conflicting'],
        'events': len(decisions),
        'claims': results['claim'],
        'extends': results['extend'],
        'releases': results['release'],
        'refusals': results['refuse'],
        'ignored': results['ignore'],
        'active': len(sessions),
        'cooling': len(cooldowns),
        'owned': len(owned),
        'table_digest': table_digest(sessions),
    }
    return decisions, {'sessions': sessions, 'cooldowns': cooldowns}, summary


def table_digest(sessions):
    lines = sorted('%s %s\n' % (server, entry['player']) for server, entry in sessions.items())
    return hashlib.sha256(''.join(lines).encode('utf-8')).hexdigest()


def load_mode(in_dir):
    with open(in_dir + '/manifest.json', 'rb') as handle:
        doc = json.loads(handle.read().decode('utf-8'))
    mode = doc.get('mode', 0)
    if not is_integer(mode):
        mode = 0
    return mode


def write_reports(out_dir, decisions, doc, summary):
    lines = [json.dumps(row, sort_keys=True, separators=(',', ':')) for row in decisions]
    body = '\n'.join(lines) + '\n' if lines else ''
    with open(out_dir + '/decisions.jsonl', 'w', encoding='utf-8') as handle:
        handle.write(body)
    with open(out_dir + '/sessions.json', 'w', encoding='utf-8') as handle:
        handle.write(json.dumps(doc, sort_keys=True, indent=2) + '\n')
    with open(out_dir + '/summary.json', 'w', encoding='utf-8') as handle:
        handle.write(json.dumps(summary, sort_keys=True, indent=2) + '\n')


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: arena.py IN_DIR OUT_DIR\n')
        return 2
    in_dir, out_dir = argv[1], argv[2]
    mode_word = load_mode(in_dir)
    decisions, doc, summary = replay(in_dir, mode_word)
    write_reports(out_dir, decisions, doc, summary)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))

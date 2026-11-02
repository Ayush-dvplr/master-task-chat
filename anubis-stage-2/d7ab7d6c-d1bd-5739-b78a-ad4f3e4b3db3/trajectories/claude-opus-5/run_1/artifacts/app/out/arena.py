import csv
import hashlib
import json
import os
import re
import sys

PLAYER_RE = re.compile(r"[a-z][a-z0-9._-]{0,30}")
SERVER_RE = re.compile(r"[a-z][a-z0-9-]{0,20}")
CLAN_RE = re.compile(r"[a-z][a-z0-9-]{0,15}")
RECORD_KEYS = {"seq", "kind", "player", "at", "party", "span", "server", "clan"}
KIND_RANK = {"release": 0, "extend": 1, "claim": 2, "ping": 3}

BIT_HINT_FIRST = 2
BIT_SEED_ONCE = 4
BIT_SHORT_COOL = 8
BIT_OWNED_STRICT = 16
BIT_RETX_NO_SEQ = 32
BIT_EXTEND_CLAIMS = 64
BIT_CLAN_SINGLE = 128
SHORT_COOLDOWN = 600


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def matches(pattern, value):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def valid_record(rec):
    if not isinstance(rec, dict) or set(rec) != RECORD_KEYS:
        return False
    return (
        is_int(rec["seq"]) and rec["seq"] >= 1
        and rec["kind"] in KIND_RANK
        and matches(PLAYER_RE, rec["player"])
        and is_int(rec["at"]) and rec["at"] >= 0
        and is_int(rec["party"]) and 1 <= rec["party"] <= 40
        and is_int(rec["span"]) and rec["span"] >= 60 and rec["span"] % 60 == 0
        and (rec["server"] is None or matches(SERVER_RE, rec["server"]))
        and (rec["clan"] is None or matches(CLAN_RE, rec["clan"]))
    )


def parse_line(raw):
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None


def retransmit_key(rec, mode):
    if mode & BIT_RETX_NO_SEQ:
        rec = {k: v for k, v in rec.items() if k != "seq"}
    return json.dumps(rec, sort_keys=True)


def screen(data, mode):
    counts = {"malformed": 0, "retransmitted": 0, "conflicting": 0}
    seen = set()
    seqs = set()
    accepted = []
    for raw in data.split(b"\n"):
        if not raw.strip():
            continue
        rec = parse_line(raw)
        if not valid_record(rec):
            counts["malformed"] += 1
            continue
        key = retransmit_key(rec, mode)
        if key in seen:
            counts["retransmitted"] += 1
            continue
        seen.add(key)
        if rec["seq"] in seqs:
            counts["conflicting"] += 1
            continue
        seqs.add(rec["seq"])
        accepted.append(rec)
    return accepted, counts


def replay_order(records):
    return sorted(records, key=lambda r: (r["at"], KIND_RANK[r["kind"]], r["seq"]))


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def load_servers(path):
    servers = {}
    for row in read_json(path).get("servers", []):
        if not isinstance(row, dict):
            continue
        name, slots = row.get("name"), row.get("slots")
        if matches(SERVER_RE, name) and is_int(slots) and slots >= 1 and name not in servers:
            servers[name] = slots
    return servers


def load_owned(path, servers):
    with open(path, encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    owned = {}
    for row in rows[1:]:
        if len(row) != 3:
            continue
        player, server = row[0], row[1]
        if matches(PLAYER_RE, player) and server in servers and player not in owned:
            owned[player] = server
    return owned


def load_previous(path, servers, mode):
    table = {}
    seeded_players = set()
    for row in read_json(path).get("sessions", []):
        if not isinstance(row, dict):
            continue
        server, player, until, clan = row.get("server"), row.get("player"), row.get("until"), row.get("clan")
        if server not in servers or not matches(PLAYER_RE, player) or not is_int(until):
            continue
        if clan is not None and not matches(CLAN_RE, clan):
            continue
        if server in table:
            continue
        if mode & BIT_SEED_ONCE and player in seeded_players:
            continue
        seeded_players.add(player)
        table[server] = {"player": player, "until": until, "clan": clan}
    return table


class Arena:
    def __init__(self, servers, owned, seeded, mode):
        self.servers = servers
        self.owned = owned
        self.owners = {}
        for player, server in owned.items():
            self.owners.setdefault(server, set()).add(player)
        self.sessions = dict(seeded)
        self.cooldowns = {}
        self.released = {}
        self.mode = mode
        self.now = 0

    def advance(self, now):
        self.now = now
        # A session is over for its player at its until, but its server only frees up the second after.
        for server in [s for s, sess in self.sessions.items() if sess["until"] < now]:
            del self.sessions[server]
        for server in [s for s, until in self.cooldowns.items() if until <= now]:
            del self.cooldowns[server]

    def live_sessions(self):
        return {s: sess for s, sess in self.sessions.items() if sess["until"] > self.now}

    def holding(self, player):
        for server, sess in self.live_sessions().items():
            if sess["player"] == player:
                return server
        return None

    def free(self, server, player, party):
        if server not in self.servers or self.servers[server] < party:
            return False
        if server in self.sessions or server in self.cooldowns:
            return False
        owners = self.owners.get(server)
        return not owners or player in owners

    def clan_busy(self, player, clan):
        if clan is None:
            return False
        return any(s["clan"] == clan and s["player"] != player for s in self.live_sessions().values())

    def offered(self, server, player, party):
        return server not in self.released.get(player, ()) and self.free(server, player, party)

    def pick(self, rec):
        player, party, hint = rec["player"], rec["party"], rec["server"]
        if self.mode & BIT_HINT_FIRST and hint is not None and self.offered(hint, player, party):
            return hint
        own = self.owned.get(player)
        if own is not None:
            if self.free(own, player, party):
                return own
            if self.mode & BIT_OWNED_STRICT:
                return None
        if hint is not None and self.offered(hint, player, party):
            return hint
        for server in self.servers:
            if self.offered(server, player, party):
                return server
        return None

    def claim(self, rec):
        if self.holding(rec["player"]) is not None:
            return "refuse"
        if self.mode & BIT_CLAN_SINGLE and self.clan_busy(rec["player"], rec["clan"]):
            return "refuse"
        server = self.pick(rec)
        if server is None:
            return "refuse"
        self.sessions[server] = {"player": rec["player"], "until": rec["at"] + rec["span"], "clan": rec["clan"]}
        return "claim"

    def extend(self, rec):
        server = self.holding(rec["player"])
        if server is None:
            return self.claim(rec) if self.mode & BIT_EXTEND_CLAIMS else "ignore"
        self.sessions[server]["until"] += rec["span"]
        return "extend"

    def release(self, rec):
        server = self.holding(rec["player"])
        if server is None:
            return "ignore"
        sess = self.sessions.pop(server)
        self.released.setdefault(rec["player"], set()).add(server)
        until = rec["at"] + SHORT_COOLDOWN if self.mode & BIT_SHORT_COOL else sess["until"]
        if until > rec["at"]:
            self.cooldowns[server] = until
        return "release"

    def apply(self, rec):
        self.advance(rec["at"])
        handler = {"claim": self.claim, "extend": self.extend, "release": self.release}.get(rec["kind"])
        return handler(rec) if handler else "ignore"


def table_digest(lines):
    return hashlib.sha256("".join(sorted(lines)).encode("utf-8")).hexdigest()


def replay(in_dir):
    mode = read_json(os.path.join(in_dir, "manifest.json"))["mode"]
    with open(os.path.join(in_dir, "requests.jsonl"), "rb") as handle:
        data = handle.read()
    servers = load_servers(os.path.join(in_dir, "servers.json"))
    owned = load_owned(os.path.join(in_dir, "owned.csv"), servers)
    seeded = load_previous(os.path.join(in_dir, "sessions.prev.json"), servers, mode)
    records, counts = screen(data, mode)
    arena = Arena(servers, owned, seeded, mode)
    decisions = []
    for rec in replay_order(records):
        result = arena.apply(rec)
        decisions.append({"at": rec["at"], "kind": rec["kind"], "player": rec["player"], "result": result, "seq": rec["seq"]})
    if decisions:
        arena.advance(decisions[-1]["at"])
    doc = {
        "sessions": {s: {"clan": v["clan"], "player": v["player"], "until": v["until"]}
                     for s, v in arena.live_sessions().items()},
        "cooldowns": {s: {"until": u} for s, u in arena.cooldowns.items()},
    }
    return doc, decisions, counts, len(owned)


def summarize(doc, decisions, counts, owned_count):
    results = [d["result"] for d in decisions]
    summary = dict(counts)
    summary.update({
        "events": len(decisions),
        "claims": results.count("claim"),
        "extends": results.count("extend"),
        "releases": results.count("release"),
        "refusals": results.count("refuse"),
        "ignored": results.count("ignore"),
        "active": len(doc["sessions"]),
        "cooling": len(doc["cooldowns"]),
        "owned": owned_count,
        "table_digest": table_digest(f"{s} {v['player']}\n" for s, v in doc["sessions"].items()),
    })
    return summary


def write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def write_reports(out_dir, doc, decisions, summary):
    os.makedirs(out_dir, exist_ok=True)
    write_text(os.path.join(out_dir, "sessions.json"), json.dumps(doc, sort_keys=True, indent=2) + "\n")
    write_text(os.path.join(out_dir, "decisions.jsonl"),
               "".join(json.dumps(d, sort_keys=True, separators=(",", ":")) + "\n" for d in decisions))
    write_text(os.path.join(out_dir, "summary.json"), json.dumps(summary, sort_keys=True, indent=2) + "\n")


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: arena.py IN_DIR OUT_DIR\n")
        return 2
    doc, decisions, counts, owned_count = replay(argv[1])
    write_reports(argv[2], doc, decisions, summarize(doc, decisions, counts, owned_count))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

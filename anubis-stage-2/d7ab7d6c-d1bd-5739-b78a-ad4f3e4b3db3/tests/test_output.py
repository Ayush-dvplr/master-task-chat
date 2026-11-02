import ast
import datetime
import hashlib
import io
import json
import os
import re
import signal
import stat
import subprocess
import sys
import tempfile
import time
import tokenize
from pathlib import Path

from rewardkit import criteria, criterion


# Harness core: the reference replay and the corpus builder.
REFERENCE = {"u1": "roomy", "u2": "before", "u3": "first", "u4": "cool", "u5": "remember", "u6": "kind"}
WRONG_READINGS = {"u1": ("snug",), "u2": ("through",), "u3": ("last",), "u4": ("free",), "u5": ("forget",), "u6": ("seq",)}
REPORTS = ("sessions.json", "decisions.jsonl", "summary.json")
INPUTS = ("requests.jsonl", "servers.json", "owned.csv", "sessions.prev.json", "manifest.json")

HINT_IGNORED = 0x02
PREV_IGNORED = 0x04
COOLDOWN_CAPPED = 0x08
OWNED_STRICT = 0x10
RELAY_SEQLESS = 0x20
EXTEND_CLAIMS = 0x40
CLAN_UNIQUE = 0x80
MODE_BITS = (HINT_IGNORED, PREV_IGNORED, COOLDOWN_CAPPED, OWNED_STRICT, RELAY_SEQLESS, EXTEND_CLAIMS, CLAN_UNIQUE)
COOLDOWN_CAP_SECONDS = 600
KIND_RANK = {"release": 0, "extend": 1, "claim": 2, "ping": 3}

PLAYER_RE = re.compile(r"^[a-z][a-z0-9._-]{0,30}$")
SERVER_RE = re.compile(r"^[a-z][a-z0-9-]{0,20}$")
CLAN_RE = re.compile(r"^[a-z][a-z0-9-]{0,15}$")
EVENT_KEYS = {"seq", "kind", "player", "at", "party", "span", "server", "clan"}


def _strict_int(x):
    return isinstance(x, int) and not isinstance(x, bool)


def check_event(rec):
    if not isinstance(rec, dict) or set(rec) != EVENT_KEYS:
        return False
    if not _strict_int(rec["seq"]) or rec["seq"] < 1:
        return False
    if rec["kind"] not in KIND_RANK:
        return False
    if not isinstance(rec["player"], str) or not PLAYER_RE.fullmatch(rec["player"]):
        return False
    if not _strict_int(rec["at"]) or rec["at"] < 0:
        return False
    if not _strict_int(rec["party"]) or not 1 <= rec["party"] <= 40:
        return False
    if not _strict_int(rec["span"]) or rec["span"] < 60 or rec["span"] % 60:
        return False
    if rec["server"] is not None and (not isinstance(rec["server"], str) or not SERVER_RE.fullmatch(rec["server"])):
        return False
    return rec["clan"] is None or (isinstance(rec["clan"], str) and CLAN_RE.fullmatch(rec["clan"]) is not None)


def screen(blob, eff):
    counts = {"malformed": 0, "retransmitted": 0, "conflicting": 0}
    seen = set()
    by_seq = {}
    for raw in blob.split(b"\n"):
        if not raw.strip():
            continue
        try:
            rec = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            counts["malformed"] += 1
            continue
        if not check_event(rec):
            counts["malformed"] += 1
            continue
        body = dict(rec)
        if eff & RELAY_SEQLESS:
            body.pop("seq")
        fp = json.dumps(body, sort_keys=True)
        if fp in seen:
            counts["retransmitted"] += 1
            continue
        seen.add(fp)
        if rec["seq"] in by_seq:
            counts["conflicting"] += 1
            continue
        by_seq[rec["seq"]] = rec
    return list(by_seq.values()), counts


def read_servers(blob):
    doc = json.loads(blob.decode("utf-8"))
    out = {}
    for row in doc.get("servers", []):
        if not isinstance(row, dict) or not isinstance(row.get("name"), str) or not SERVER_RE.fullmatch(row["name"]):
            continue
        if not _strict_int(row.get("slots")) or row["slots"] < 1 or row["name"] in out:
            continue
        out[row["name"]] = row["slots"]
    return out


def read_owned(text, servers, variant):
    out = {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "player,server,note":
        return out
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) != 3 or not PLAYER_RE.fullmatch(parts[0]) or parts[1] not in servers:
            continue
        if variant["u3"] == "first":
            out.setdefault(parts[0], parts[1])
        else:
            out[parts[0]] = parts[1]
    return out


def read_prev(blob, servers):
    doc = json.loads(blob.decode("utf-8"))
    out = []
    for row in doc.get("sessions", []):
        if not isinstance(row, dict) or row.get("server") not in servers:
            continue
        if not isinstance(row.get("player"), str) or not PLAYER_RE.fullmatch(row["player"]) or not _strict_int(row.get("until")):
            continue
        clan = row.get("clan")
        if clan is not None and (not isinstance(clan, str) or not CLAN_RE.fullmatch(clan)):
            continue
        out.append((row["server"], row["player"], row["until"], clan))
    return out


class State:
    def __init__(self, servers, owned, variant, eff):
        self.servers, self.owned, self.variant, self.eff = servers, owned, variant, eff
        self.claimed = {}
        self.cooling = {}
        self.last = {}
        self.owners = {s: p for p, s in owned.items()}

    def live(self, until, t):
        return t <= until if self.variant["u2"] == "through" else t < until

    def holding(self, player, t):
        for server, b in self.claimed.items():
            if b["player"] == player and self.live(b["until"], t):
                return server
        return None

    def usable(self, server, player, party, t):
        if server not in self.servers or self.servers[server] < party:
            return False
        b = self.claimed.get(server)
        if b is not None and (self.live(b["until"], t) or self.variant.get("server_end") == "busy" and t <= b["until"]):
            return False
        if server in self.cooling and self.live(self.cooling[server], t):
            return False
        owner = self.owners.get(server)
        return owner is None or owner == player

    def scan(self):
        if self.variant["u1"] == "snug":
            return sorted(self.servers, key=lambda s: (self.servers[s], s))
        if self.variant.get("scan_tie") == "file":
            return sorted(self.servers, key=lambda s: -self.servers[s])
        return sorted(self.servers, key=lambda s: (-self.servers[s], s))

    def claim(self, player, t, party, span, hint, clan):
        if self.holding(player, t) is not None:
            return "refuse"
        if self.eff & CLAN_UNIQUE and clan is not None:
            for b in self.claimed.values():
                if b["clan"] == clan and b["player"] != player and self.live(b["until"], t):
                    return "refuse"
        choice = None
        mine = self.owned.get(player)
        if mine is not None:
            if self.usable(mine, player, party, t):
                choice = mine
            elif self.eff & OWNED_STRICT:
                return "refuse"
        if choice is None and hint is not None and not self.eff & HINT_IGNORED and self.usable(hint, player, party, t):
            choice = hint
        if choice is None and self.variant["u5"] == "remember":
            prior = self.last.get(player)
            if prior is not None and self.usable(prior, player, party, t):
                choice = prior
        if choice is None:
            for server in self.scan():
                if self.usable(server, player, party, t):
                    choice = server
                    break
        if choice is None:
            return "refuse"
        self.claimed[choice] = {"player": player, "until": t + span, "clan": clan}
        self.cooling.pop(choice, None)
        self.last[player] = choice
        return "claim"

    def apply(self, ev):
        t, player, kind = ev["at"], ev["player"], ev["kind"]
        if kind == "ping":
            return "ignore"
        if kind == "claim":
            return self.claim(player, t, ev["party"], ev["span"], ev["server"], ev["clan"])
        server = self.holding(player, t)
        if kind == "extend":
            if server is None:
                if self.eff & EXTEND_CLAIMS:
                    hint = ev["server"] if self.variant.get("extend_hint") == "named" else None
                    return self.claim(player, t, ev["party"], ev["span"], hint, ev["clan"])
                return "ignore"
            self.claimed[server]["until"] += ev["span"]
            return "extend"
        if server is None:
            return "ignore"
        end = self.claimed.pop(server)["until"]
        if self.variant["u4"] == "cool":
            if self.eff & COOLDOWN_CAPPED:
                capped = t + COOLDOWN_CAP_SECONDS
                self.cooling[server] = capped if self.variant.get("cap") == "fixed" else min(end, capped)
            else:
                self.cooling[server] = end
        return "release"


def resolve(files, variant=None):
    variant = dict(REFERENCE if variant is None else variant)
    mode = json.loads(files["manifest.json"].decode("utf-8")).get("mode", 0)
    eff = mode & ~variant.get("blind", 0)
    events, counts = screen(files["requests.jsonl"], eff)
    servers = read_servers(files["servers.json"])
    owned = read_owned(files["owned.csv"].decode("utf-8"), servers, variant)
    st = State(servers, owned, variant, eff)
    if not eff & PREV_IGNORED:
        for server, player, until, clan in read_prev(files["sessions.prev.json"], servers):
            if server not in st.claimed:
                st.claimed[server] = {"player": player, "until": until, "clan": clan}
                st.last[player] = server
    if variant["u6"] == "kind":
        events.sort(key=lambda e: (e["at"], KIND_RANK[e["kind"]], e["seq"]))
    else:
        events.sort(key=lambda e: (e["at"], e["seq"]))
    log = []
    tally = {}
    for ev in events:
        result = st.apply(ev)
        tally[result] = tally.get(result, 0) + 1
        log.append({"at": ev["at"], "seq": ev["seq"], "player": ev["player"], "kind": ev["kind"], "result": result})
    last = events[-1]["at"] if events else 0
    return render(st, log, tally, counts, len(owned), last)


def session_lines(sessions):
    return "".join(sorted("%s %s\n" % (s, row["player"]) for s, row in sessions.items()))


def cooldown_lines(cooldowns):
    return "".join(sorted("%s %d\n" % (s, row["until"]) for s, row in cooldowns.items()))


def render(st, log, tally, counts, n_owned, last):
    sessions = {s: dict(b) for s, b in st.claimed.items() if st.live(b["until"], last)}
    cooldowns = {s: {"until": e} for s, e in st.cooling.items() if st.live(e, last)}
    summary = dict(counts)
    summary.update({
        "events": len(log),
        "claims": tally.get("claim", 0),
        "extends": tally.get("extend", 0),
        "releases": tally.get("release", 0),
        "refusals": tally.get("refuse", 0),
        "ignored": tally.get("ignore", 0),
        "active": len(sessions),
        "cooling": len(cooldowns),
        "owned": n_owned,
        "table_digest": hashlib.sha256(session_lines(sessions).encode()).hexdigest(),
    })
    return {
        "sessions.json": json.dumps({"sessions": sessions, "cooldowns": cooldowns}, sort_keys=True, indent=2) + "\n",
        "decisions.jsonl": "".join(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n" for r in log),
        "summary.json": json.dumps(summary, sort_keys=True, indent=2) + "\n",
    }


def table_digests(sessions_text):
    doc = json.loads(sessions_text)
    return {"sessions": hashlib.sha256(session_lines(doc["sessions"]).encode()).hexdigest(),
            "cooldowns": hashlib.sha256(cooldown_lines(doc["cooldowns"]).encode()).hexdigest()}


def manifest(mode, reports):
    doc = {"mode": mode, "reports": {n: hashlib.sha256(t.encode()).hexdigest() for n, t in reports.items()},
           "tables": table_digests(reports["sessions.json"])}
    return (json.dumps(doc, sort_keys=True, indent=2) + "\n").encode()


class Rng:
    """splitmix64, so corpora do not depend on the random module."""

    def __init__(self, seed):
        self.state = seed & 0xFFFFFFFFFFFFFFFF

    def next(self):
        self.state = (self.state + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
        return z ^ (z >> 31)

    def below(self, n):
        return self.next() % n

    def between(self, lo, hi):
        return lo + self.below(hi - lo + 1)

    def pick(self, items):
        return items[self.below(len(items))]

    def shuffle(self, items):
        items = list(items)
        for i in range(len(items) - 1, 0, -1):
            j = self.below(i + 1)
            items[i], items[j] = items[j], items[i]
        return items


NAMES = ["axl", "brik", "cindr", "dusk", "embr", "fexx", "glyph", "hexx", "ionn", "jolt", "krag", "lumo", "mycel",
         "nox", "orbit", "pyre", "quark", "rune", "snap", "tusk", "umbr", "vexx", "wisp", "xeno", "yarn", "zeph"]
SERVER_NAMES = ["basalt", "cinder", "delta", "ember", "frost", "gale", "harbor", "iris", "kiln", "lumen", "mesa",
                "nimbus"]
SLOTS = (2, 4, 4, 6, 8, 10, 12)
CLANS = ["ravens", "wolves", "nomads", "titans", "vipers"]
STEPS = (0, 0, 0, 300, 300, 600, 900, 1200, 1800)
SPANS = (1800, 1800, 3600, 3600, 5400)
KINDS = ("claim", "claim", "claim", "claim", "extend", "extend", "release", "release", "ping")
NOISE = ("truncated", "array", "missing", "extra", "strseq", "boolseq", "zeroseq", "badkind", "badplayer",
         "bigparty", "oddspan", "negat", "floatat", "badserver", "badclan")


def _noise(kind, rec):
    r = dict(rec)
    if kind == "truncated":
        return json.dumps(r, sort_keys=True)[:-6]
    if kind == "array":
        return json.dumps([r["player"], r["at"]])
    if kind == "missing":
        r.pop("clan")
    elif kind == "extra":
        r["region"] = 3
    elif kind == "strseq":
        r["seq"] = str(r["seq"])
    elif kind == "boolseq":
        r["seq"] = True
    elif kind == "zeroseq":
        r["seq"] = 0
    elif kind == "badkind":
        r["kind"] = "swap"
    elif kind == "badplayer":
        r["player"] = r["player"].capitalize()
    elif kind == "bigparty":
        r["party"] = 0
    elif kind == "oddspan":
        r["span"] = r["span"] + 7
    elif kind == "negat":
        r["at"] = -r["at"] - 1
    elif kind == "floatat":
        r["at"] = float(r["at"])
    elif kind == "badserver":
        r["server"] = "Server 4"
    elif kind == "badclan":
        r["clan"] = 7
    return json.dumps(r, sort_keys=bool(rec["seq"] % 2))


def build_corpus(seed, traps=(), clients=8, count=30, noise=True, mode=0):
    rng = Rng(seed)
    people = rng.shuffle(NAMES)[:clients]
    names = rng.shuffle(SERVER_NAMES)[: rng.between(4, 6)]
    servers = [{"name": n, "slots": rng.pick(SLOTS)} for n in names]
    clan = {p: (rng.pick(CLANS) if rng.below(3) else None) for p in people}
    t = rng.between(28000, 34000) // 300 * 300
    recs = []
    player = rng.pick(people)
    for _ in range(count):
        t += rng.pick(STEPS)
        if rng.below(3):
            player = rng.pick(people)
        kind = rng.pick(KINDS)
        hint = rng.pick(names) if rng.below(2) == 0 else None
        recs.append({"kind": kind, "player": player, "at": t, "party": rng.pick((1, 2, 3, 4, 5, 6, 8)),
                     "span": rng.pick(SPANS), "server": hint, "clan": clan[player]})
    lines = [dict(r) for r in recs]
    if mode & RELAY_SEQLESS:
        for r in rng.shuffle(recs)[: rng.between(2, 4)]:
            lines.append(dict(r))
    lines = rng.shuffle(lines)
    seqs = rng.shuffle(list(range(1, len(lines) + 1)))
    for r, s in zip(lines, seqs):
        r["seq"] = s
    out = [json.dumps(r, sort_keys=bool(rng.below(2))) for r in lines]
    if noise:
        for _ in range(rng.between(3, 6)):
            k = rng.below(len(out))
            out.insert(k + 1, out[k])
        for _ in range(rng.between(1, 3)):
            c = dict(rng.pick(lines))
            c["at"] = c["at"] + rng.pick((300, 600))
            out.insert(rng.below(len(out) + 1), json.dumps(c, sort_keys=True))
        for kind in rng.shuffle(NOISE)[: rng.between(7, 11)]:
            out.insert(rng.below(len(out) + 1), _noise(kind, rng.pick(lines)))
        out.insert(rng.below(len(out) + 1), "")
        out.insert(rng.below(len(out) + 1), "allocator node restarted, journal resumes below")
    blob = ("\n".join(out) + "\n").encode("utf-8")
    rows = ["player,server,note"]
    for p in rng.shuffle(people)[: rng.between(1, 3)]:
        rows.append("%s,%s,%s" % (p, rng.pick(names), rng.pick(("ranked", "scrim", "league"))))
        if "u3" in traps and rng.below(2):
            rows.append("%s,%s,%s" % (p, rng.pick(names), "swapped"))
    if noise:
        rows.append("%s,%s,typo" % (people[0].capitalize(), names[0]))
        rows.append("%s,scrap,gone" % rng.pick(people))
        rows.append("%s,%s" % (rng.pick(people), rng.pick(names)))
    prev = []
    for server in rng.shuffle(names)[: rng.between(0, 2)]:
        p = rng.pick(people)
        prev.append({"server": server, "player": p, "until": recs[0]["at"] + rng.pick((0, 300, 900, 1800, 3600)),
                     "clan": clan[p]})
    if noise and prev:
        prev.append({"server": "scrap", "player": rng.pick(people), "until": recs[0]["at"] + 900, "clan": None})
    if noise:
        servers.append({"name": names[0], "slots": 40})
        servers.append({"name": "Nimbus", "slots": 30})
    files = {"requests.jsonl": blob,
             "servers.json": (json.dumps({"servers": servers}, indent=2) + "\n").encode(),
             "owned.csv": ("\n".join(rows) + "\n").encode(),
             "sessions.prev.json": (json.dumps({"sessions": prev}, sort_keys=True, indent=2) + "\n").encode(),
             "manifest.json": json.dumps({"mode": mode}).encode()}
    files["manifest.json"] = manifest(mode, resolve(files))
    return files


def flipped(rule, reading):
    v = dict(REFERENCE)
    v[rule] = reading
    return v


def separation(files):
    ref = resolve(files)
    return {(r, x) for r, xs in WRONG_READINGS.items() for x in xs if resolve(files, flipped(r, x)) != ref}


def bit_moves(files):
    ref = resolve(files)
    out = set()
    for bit in MODE_BITS:
        v = dict(REFERENCE)
        v["blind"] = bit
        if resolve(files, v) != ref:
            out.add(bit)
    return out


def _search(start, step, tries, build, accept):
    for attempt in range(tries):
        files = build(start + attempt * step)
        if accept(files):
            return files
    raise RuntimeError("no case found")


def _all_readings(rule):
    return {(rule, x) for x in WRONG_READINGS[rule]}


def _solo_owners(files):
    """True when no listed server is owned by two players, whichever duplicate owned row stands.

    The worked examples do not settle who keeps a server two players own, so fresh journals never have one."""
    servers = read_servers(files["servers.json"])
    text = files["owned.csv"].decode("utf-8")
    for reading in ("first", "last"):
        owned = read_owned(text, servers, {"u3": reading})
        if len(set(owned.values())) != len(owned):
            return False
    return True


# Bit readings no worked example and no live manifest digest can tell apart: under bit 8 a cooldown of
# exactly 600 seconds after the release, and under bit 64 an extend that claims the server it names.
OPEN_READINGS = ({"cap": "fixed"}, {"extend_hint": "named"})


def _open_readings_agree(files):
    """True when every reading the shipped evidence leaves open gives the same reports."""
    ref = resolve(files)
    return all(resolve(files, dict(REFERENCE, **reading)) == ref for reading in OPEN_READINGS)


def _fresh(files):
    """A fresh journal only grades what the shipped evidence settles."""
    return _solo_owners(files) and _open_readings_agree(files)


# Further readings of a rule that the worked examples rule out but that its one wrong reading can leave
# untried: scan ties broken in servers.json order, and a server kept taken through its session's end second.
RULE_FACETS = {"u1": ({"scan_tie": "file"},), "u2": ({"server_end": "busy"},)}


def _facets_move(files, rule):
    """True when every further reading of the rule changes the reports as well."""
    ref = resolve(files)
    return all(resolve(files, dict(REFERENCE, **facet)) != ref for facet in RULE_FACETS.get(rule, ()))


def isolated_case(seed, rule, wanted=None):
    """A clean mode zero journal where only the readings of one rule change the reports."""
    wanted = _all_readings(rule) if wanted is None else wanted
    traps = (rule,) if rule == "u3" else ()
    return _search(seed, 7919, 3000, lambda s: build_corpus(s, traps, clients=3 + s % 4, count=8 + s % 8, noise=False),
                   lambda f: _fresh(f) and separation(f) == wanted and _facets_move(f, rule))


def plain_case(seed):
    """A clean mode zero journal that no rule reading moves."""
    return _search(seed, 104729, 3000, lambda s: build_corpus(s, (), clients=3 + s % 3, count=6 + s % 5, noise=False),
                   lambda f: _fresh(f) and not separation(f))


def bit_case(seed, bit):
    """A clean journal whose mode word is one bit, and only that bit moves the reports."""
    return _search(seed, 6151, 3000, lambda s: build_corpus(s, (), clients=3 + s % 4, count=8 + s % 8, noise=False, mode=bit),
                   lambda f: _fresh(f) and bit_moves(f) == {bit} and not separation(f))


def mixed_case(seed, clients=8, count=30, need=None, mode=0, fresh=True):
    """A noisy journal where every needed reading and every set mode bit moves the reports."""
    need = {(r, x) for r in REFERENCE for x in WRONG_READINGS[r]} if need is None else need
    bits = {b for b in MODE_BITS if mode & b}
    return _search(seed, 15485863, 3000, lambda s: build_corpus(s, ("u3",), clients=clients, count=count, mode=mode),
                   lambda f: (not fresh or _fresh(f)) and need <= separation(f) and bit_moves(f) == bits)


def _every_reading():
    return {(r, x) for r in REFERENCE for x in WRONG_READINGS[r]}


def _figures(files):
    return json.loads(resolve(files)["summary.json"])


def example_case(seed):
    """A worked example: mode zero, every rule reading moves it, and at least two servers stay claimed."""
    return _search(seed, 15485863, 3000, lambda s: build_corpus(s, ("u3",), clients=6, count=24),
                   lambda f: _every_reading() <= separation(f) and _figures(f)["active"] >= 2)


def live_journal_ok(files):
    """The shipped live journal: every bit and every rule moves it, and sessions, a cooldown and a conflict survive."""
    if bit_moves(files) != set(MODE_BITS) or not _every_reading() <= separation(files):
        return False
    figures = _figures(files)
    return figures["active"] >= 3 and figures["cooling"] >= 1 and figures["conflicting"] >= 1


def live_journal_case(seed):
    return _search(seed, 15485863, 6000, lambda s: build_corpus(s, ("u3",), clients=12, count=80, mode=0xFE), live_journal_ok)


def mode_example_case(seed, mode):
    """A worked example under a non-zero mode word: every set bit moves it, as do the two readings the mode cases need."""
    # The shipped worked examples were drawn without the fresh journal filters; keep them reproducible.
    return mixed_case(seed, clients=8, count=40, need={("u4", "free"), ("u6", "seq")}, mode=mode, fresh=False)


_FAR_UNTIL = 86400


def with_stated_rule_rows(files):
    """Adds rows that each break exactly one written rule the corpus builder never breaks."""
    files = dict(files)
    servers = read_servers(files["servers.json"])
    seeded = {row[0] for row in read_prev(files["sessions.prev.json"], servers)}
    free = [name for name in sorted(servers) if name not in seeded]
    events, _counts = screen(files["requests.jsonl"], 0)
    at = min(e["at"] for e in events)
    base = {"kind": "claim", "player": "kestrel", "at": at, "party": 2, "span": 1800, "server": None, "clan": None}
    bent = [("party", "2"), ("party", 2.0), ("span", "1800"), ("span", 1800.0), ("span", 0)]
    lines = []
    for number, (key, value) in enumerate(bent):
        row = dict(base, seq=901 + number)
        row[key] = value
        lines.append(json.dumps(row, sort_keys=True).encode("utf-8"))
    lines.append(json.dumps(dict(base, seq=911), sort_keys=True).encode("utf-8").replace(b'"at"', b'\xff "at"', 1))
    files["requests.jsonl"] = files["requests.jsonl"] + b"\n".join(lines) + b"\n"
    doc = json.loads(files["servers.json"].decode("utf-8"))
    doc["servers"] += ["dune", {"name": "quarry", "slots": "6"}, {"name": "spire", "slots": 0},
                       {"name": "vault", "slots": 6.0}]
    files["servers.json"] = (json.dumps(doc, indent=2) + "\n").encode()
    files["owned.csv"] = files["owned.csv"] + b"kestrel,quarry,league\nlark,spire,ranked\nmoth,vault,scrim\n"
    if free:
        target = free[0]
        doc = json.loads(files["sessions.prev.json"].decode("utf-8"))
        doc["sessions"] += [
            "ghost",
            {"server": target, "player": "Kestrel", "until": _FAR_UNTIL, "clan": None},
            {"server": target, "player": "lark", "until": str(_FAR_UNTIL), "clan": None},
            {"server": target, "player": "moth", "until": _FAR_UNTIL, "clan": "Bad Clan"},
            {"server": target, "player": "otter", "until": _FAR_UNTIL, "clan": None},
            {"server": target, "player": "finch", "until": _FAR_UNTIL, "clan": None},
        ]
        files["sessions.prev.json"] = (json.dumps(doc, sort_keys=True, indent=2) + "\n").encode()
    files["manifest.json"] = manifest(0, resolve(files))
    return files


def noisy_plain_case(seed):
    """A damaged mode zero journal that no rule reading moves, carrying a row for every written screening rule."""
    return _search(seed, 2741, 3000,
                   lambda s: with_stated_rule_rows(build_corpus(s, (), clients=3 + s % 3, count=8 + s % 5, noise=True)),
                   lambda f: _fresh(f) and not separation(f))


def empty_events_case(seed):
    """A journal where every line is damaged and nothing is seeded, so no request is replayed and every report is empty."""
    files = dict(plain_case(seed))
    files["requests.jsonl"] = b'\narena relay rebooted, journal resumes below\n{"seq": 0, "kind": "claim"}\n[1, 2]\n'
    files["sessions.prev.json"] = b'{\n  "sessions": []\n}\n'
    files["manifest.json"] = manifest(0, resolve(files))
    return files


SHIPPED_SEED = 8921888149911813417 ^ 15
EXAMPLE_SEED = 8921888149911813417 ^ 1
SECOND_EXAMPLE_SEED = 8921888149911813417 ^ 2
THIRD_EXAMPLE_SEED = 8921888149911813417 ^ 3
FOURTH_EXAMPLE_SEED = 8921888149911813417 ^ 4
_MODE_NEED = {("u4", "free"), ("u6", "seq")}
CASES = {
    "plain": lambda: plain_case(0x51A7E0001),
    "noisy-plain": lambda: noisy_plain_case(0x51A7E0002),
    "screen": lambda: mixed_case(0x3A1E00007, clients=6, count=22),
    "iso-u1": lambda: isolated_case(0x1D0000001, "u1"),
    "iso-u2": lambda: isolated_case(0x1D0000002, "u2"),
    "iso-u3": lambda: isolated_case(0x1D0000003, "u3"),
    "iso-u4": lambda: isolated_case(0x1D0000004, "u4"),
    "iso-u5": lambda: isolated_case(0x1D0000005, "u5"),
    "iso-u6": lambda: isolated_case(0x1D0000006, "u6"),
    "mixed-a": lambda: mixed_case(0x3A1E00001, clients=6, count=24),
    "mixed-b": lambda: mixed_case(0x3A1E00002, clients=7, count=26),
    "large": lambda: mixed_case(0x3A1E00003, clients=40, count=1000, need=_MODE_NEED, mode=0x6A),
    "mode-alpha": lambda: mixed_case(0x3A1E00011, clients=8, count=30, need=_MODE_NEED, mode=0xFE),
    "mode-beta": lambda: mixed_case(0x3A1E00012, clients=8, count=30, need=_MODE_NEED, mode=0xB6),
    "pair-06": lambda: mixed_case(0x3A1E00021, clients=6, count=24, need=_MODE_NEED, mode=0x06),
    "pair-18": lambda: mixed_case(0x3A1E00022, clients=6, count=24, need=_MODE_NEED, mode=0x18),
    "pair-60": lambda: mixed_case(0x3A1E00023, clients=6, count=24, need=_MODE_NEED, mode=0x60),
    "pair-82": lambda: mixed_case(0x3A1E00024, clients=6, count=24, need=_MODE_NEED, mode=0x82),
    "bit-02": lambda: bit_case(0x51A0 + HINT_IGNORED, HINT_IGNORED),
    "bit-04": lambda: bit_case(0x51A0 + PREV_IGNORED, PREV_IGNORED),
    "bit-08": lambda: bit_case(0x51A0 + COOLDOWN_CAPPED, COOLDOWN_CAPPED),
    "bit-10": lambda: bit_case(0x51A0 + OWNED_STRICT, OWNED_STRICT),
    "bit-20": lambda: bit_case(0x51A0 + RELAY_SEQLESS, RELAY_SEQLESS),
    "bit-40": lambda: bit_case(0x51A0 + EXTEND_CLAIMS, EXTEND_CLAIMS),
    "bit-80": lambda: bit_case(0x51A0 + CLAN_UNIQUE, CLAN_UNIQUE),
    "pair-30": lambda: mixed_case(0x3A1E00025, clients=6, count=24, need=_MODE_NEED, mode=0x30),
    "pair-88": lambda: mixed_case(0x3A1E00026, clients=6, count=24, need=_MODE_NEED, mode=0x88),
    "empty": lambda: empty_events_case(0x0E0000001),
    "stale": lambda: mixed_case(0x3A1E00004, clients=5, count=20),
    "example": lambda: example_case(EXAMPLE_SEED),
    "example-b": lambda: example_case(SECOND_EXAMPLE_SEED),
    "example-c": lambda: mode_example_case(THIRD_EXAMPLE_SEED, 0xAA),
    "example-d": lambda: mode_example_case(FOURTH_EXAMPLE_SEED, 0x54),
    "repeat": lambda: mixed_case(0x3A1E00005, clients=5, count=20),
    "untouched": lambda: mixed_case(0x3A1E00006, clients=5, count=20),
}
_FILES = {}
_TMP_ROOT = os.path.realpath(tempfile.gettempdir())
_RUNS = {}
# Each launch gets at most _RUN_BUDGET seconds, and all launches together share
# _TOTAL_BUDGET seconds, so a hanging delivery cannot outlast the verifier.
_RUN_BUDGET = 90
_TOTAL_BUDGET = 2200
_DEADLINE = time.monotonic() + _TOTAL_BUDGET
_STALE = {
    "sessions.json": '{"cooldowns": {}, "sessions": {"attic": {"clan": null, "player": "zed", "until": 1}}}\n',
    "decisions.jsonl": '{"at":0,"kind":"claim","player":"zed","result":"claim","seq":1}\n',
    "summary.json": '{"claims": 99}\n',
}


def _case(label):
    if label not in _FILES:
        _FILES[label] = CASES[label]()
    return _FILES[label]


def _script(workspace):
    return os.path.join(str(workspace), "out", "arena.py")


def _inside_sandbox(path):
    resolved = os.path.realpath(path)
    return resolved != _TMP_ROOT and resolved.startswith(_TMP_ROOT + os.sep)


def _open_up(path):
    node = os.path.realpath(path)
    while _inside_sandbox(node):
        try:
            os.chmod(node, (os.stat(node).st_mode & 0o7777) | 0o111 | 0o044)
        except OSError:
            pass
        node = os.path.dirname(node)


def _grant_read(path):
    # A directory needs its search bit as well as its read bit, or the
    # unprivileged runner cannot traverse into it to open the program.
    extra = 0o044 | (0o011 if os.path.isdir(path) else 0o000)
    try:
        os.chmod(path, (os.stat(path).st_mode & 0o7777) | extra)
    except OSError:
        pass


def _demoted(argv):
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups", "--"] + argv
    return argv


def _terminate(proc):
    # start_new_session makes the child its own group leader, so its pid is the pgid.
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, AttributeError):
        pass
    try:
        proc.kill()
    except OSError:
        pass
    try:
        proc.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _launch(argv, scratch, budget=_RUN_BUDGET):
    """Run the delivered program demoted; returns its exit code, or None on timeout."""
    budget = min(budget, _DEADLINE - time.monotonic())
    if budget <= 0:
        return None
    env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": scratch,
        "TMPDIR": scratch,
        "LC_ALL": "C",
    }
    with open(os.path.join(scratch, "stdout.txt"), "wb") as sink, open(os.path.join(scratch, "stderr.txt"), "wb") as errsink:
        proc = subprocess.Popen(
            _demoted(argv),
            stdout=sink,
            stderr=errsink,
            stdin=subprocess.DEVNULL,
            env=env,
            start_new_session=True,
        )
        try:
            code = proc.wait(timeout=budget)
        except subprocess.TimeoutExpired:
            code = None
        _terminate(proc)
        return code


def _tree_digest(root):
    # lstat, never open, anything that is not a regular file: a fifo or device
    # left in the input folder must not block the verifier.
    hasher = hashlib.sha256()
    for base, dirs, files in os.walk(root):
        dirs.sort()
        for name in sorted(dirs + files):
            path = os.path.join(base, name)
            info = os.lstat(path)
            hasher.update(os.fsencode(os.path.relpath(path, root)) + b"\0" + b"%o\0" % stat.S_IFMT(info.st_mode))
            if stat.S_ISREG(info.st_mode):
                with open(path, "rb") as handle:
                    hasher.update(handle.read())
            elif stat.S_ISLNK(info.st_mode):
                hasher.update(os.fsencode(os.readlink(path)))
            hasher.update(b"\0")
    return hasher.hexdigest()


def _run(workspace, label, prefill=False, budget=_RUN_BUDGET):
    key = (str(workspace), label)
    if key in _RUNS:
        return _RUNS[key]
    script = _script(workspace)
    if not os.path.isfile(script):
        return None
    _open_up(script)
    _grant_read(os.path.dirname(script))
    _grant_read(script)
    work = tempfile.mkdtemp(prefix="asr-" + label + "-")
    data = os.path.join(work, "data")
    out = os.path.join(work, "out")
    scratch = os.path.join(work, "scratch")
    for node in (data, out, scratch):
        os.makedirs(node)
    for name, body in _case(label).items():
        with open(os.path.join(data, name), "wb") as handle:
            handle.write(body)
        os.chmod(os.path.join(data, name), 0o644)
    if prefill:
        for name, body in _STALE.items():
            with open(os.path.join(out, name), "w", encoding="utf-8") as handle:
                handle.write(body)
            os.chmod(os.path.join(out, name), 0o666)
    for node in (work, data, out, scratch):
        os.chmod(node, 0o777)
    before = _tree_digest(data)
    code = _launch([sys.executable, script, data, out], scratch, budget)
    _RUNS[key] = (data, out, scratch, code, before)
    return _RUNS[key]


def _artifact(out, name):
    path = os.path.join(out, name)
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as handle:
        return handle.read()


def _report_matches(workspace, label, names=REPORTS, prefill=False, budget=_RUN_BUDGET):
    """True when the program exits 0 and writes the named reports byte for byte."""
    try:
        run = _run(workspace, label, prefill, budget)
        if run is None or run[3] != 0:
            return False
        expected = resolve(_case(label))
        return all(_artifact(run[1], name) == expected[name].encode("utf-8") for name in names)
    except Exception:
        return False


def _delivered_source(workspace):
    script = _script(workspace)
    if not os.path.isfile(script):
        return None
    _grant_read(script)
    with open(script, "rb") as handle:
        return handle.read().decode("utf-8", "replace")


@criterion(description="on a clean fresh journal with no undocumented rule in play the session table matches byte for byte")
def plain_journal_sessions_match(workspace: Path) -> bool:
    return _report_matches(workspace, "plain", ("sessions.json",))


@criterion(description="on a clean fresh journal with no undocumented rule in play the decision file matches byte for byte")
def plain_journal_decisions_match(workspace: Path) -> bool:
    return _report_matches(workspace, "plain", ("decisions.jsonl",))


@criterion(description="on a clean fresh journal with no undocumented rule in play the summary matches byte for byte")
def plain_journal_summary_matches(workspace: Path) -> bool:
    return _report_matches(workspace, "plain", ("summary.json",))


@criterion(description="on a fresh journal with damaged, repeated and conflicting lines the summary screening counts match")
def screening_counts_match(workspace: Path) -> bool:
    try:
        run = _run(workspace, "screen")
        if run is None or run[3] != 0:
            return False
        got = json.loads((_artifact(run[1], "summary.json") or b"{}").decode("utf-8"))
        want = json.loads(resolve(_case("screen"))["summary.json"])
        return isinstance(got, dict) and all(got.get(k) == want[k] for k in ("malformed", "retransmitted", "conflicting"))
    except Exception:
        return False


@criterion(description="on a fresh journal, server list and previous table with damaged, repeated and conflicting rows all three reports match byte for byte")
def screened_journal_replays(workspace: Path) -> bool:
    return _report_matches(workspace, "noisy-plain")


@criterion(description="a journal where only the order servers are scanned in, ties included, matters replays byte for byte")
def server_scan_isolated(workspace: Path) -> bool:
    return _report_matches(workspace, "iso-u1")


@criterion(description="a journal where only the second a session ends, for its player and its server, matters replays byte for byte")
def session_end_isolated(workspace: Path) -> bool:
    return _report_matches(workspace, "iso-u2")


@criterion(description="a journal where only the choice between duplicate owned rows matters replays byte for byte")
def duplicate_owned_isolated(workspace: Path) -> bool:
    return _report_matches(workspace, "iso-u3")


@criterion(description="a journal where only what a released server does next matters replays byte for byte")
def released_server_isolated(workspace: Path) -> bool:
    return _report_matches(workspace, "iso-u4")


@criterion(description="a journal where only a returning player matters replays byte for byte")
def returning_player_isolated(workspace: Path) -> bool:
    return _report_matches(workspace, "iso-u5")


@criterion(description="a journal where only the order of events within one second matters replays byte for byte")
def same_second_order_isolated(workspace: Path) -> bool:
    return _report_matches(workspace, "iso-u6")


@criterion(description="a fresh screened journal where every undocumented rule matters replays byte for byte")
def mixed_journal_alpha_replays(workspace: Path) -> bool:
    return _report_matches(workspace, "mixed-a")


@criterion(description="a second fresh screened journal where every undocumented rule matters replays byte for byte")
def mixed_journal_beta_replays(workspace: Path) -> bool:
    return _report_matches(workspace, "mixed-b")


@criterion(description="the table digest in the summary agrees with the session table the same run wrote")
def table_digest_agrees_with_sessions(workspace: Path) -> bool:
    try:
        run = _run(workspace, "mixed-b")
        if run is None or run[3] != 0:
            return False
        table = json.loads((_artifact(run[1], "sessions.json") or b"{}").decode("utf-8"))
        summary = json.loads((_artifact(run[1], "summary.json") or b"{}").decode("utf-8"))
        sessions = table.get("sessions")
        if not isinstance(sessions, dict) or not sessions:
            return False
        text = "".join(sorted("%s %s\n" % (server, row["player"]) for server, row in sessions.items()))
        return summary.get("table_digest") == hashlib.sha256(text.encode("utf-8")).hexdigest()
    except Exception:
        return False


@criterion(description="a journal whose every line is damaged still gets an empty decision file and matching empty reports")
def empty_journal_outputs_written(workspace: Path) -> bool:
    return _report_matches(workspace, "empty")


@criterion(description="reports left in the output directory by an earlier run are replaced by the reports of this run")
def stale_outputs_replaced(workspace: Path) -> bool:
    return _report_matches(workspace, "stale", prefill=True)


@criterion(description="the four shipped worked examples under mode words 0, 0, 170 and 84 all reproduce their shipped reports byte for byte")
def worked_example_reproduces(workspace: Path) -> bool:
    return all(_report_matches(workspace, label) for label in ("example", "example-b", "example-c", "example-d"))


@criterion(description="a fresh journal of a thousand requests under a nonzero mode word replays byte for byte within a minute")
def large_journal_replays(workspace: Path) -> bool:
    return _report_matches(workspace, "large", budget=60)


@criterion(description="a fresh journal whose mode word is 2 alone replays byte for byte")
def mode_bit_two_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "bit-02")


@criterion(description="a fresh journal whose mode word is 4 alone replays byte for byte")
def mode_bit_four_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "bit-04")


@criterion(description="a fresh journal whose mode word is 8 alone replays byte for byte")
def mode_bit_eight_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "bit-08")


@criterion(description="a fresh journal whose mode word is 16 alone replays byte for byte")
def mode_bit_sixteen_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "bit-10")


@criterion(description="a fresh journal whose mode word is 32 alone replays byte for byte")
def mode_bit_thirty_two_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "bit-20")


@criterion(description="a fresh journal whose mode word is 64 alone replays byte for byte")
def mode_bit_sixty_four_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "bit-40")


@criterion(description="a fresh journal whose mode word is 128 alone replays byte for byte")
def mode_bit_one_hundred_twenty_eight_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "bit-80")


@criterion(description="a fresh screened journal under mode word 254 replays byte for byte")
def mode_word_alpha_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "mode-alpha")


@criterion(description="a second fresh screened journal under mode word 182 replays byte for byte")
def mode_word_beta_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "mode-beta")


@criterion(description="fresh screened journals under the two bit mode words 6 and 130 both replay byte for byte")
def mode_pairs_with_bit_two_resolve(workspace: Path) -> bool:
    return _report_matches(workspace, "pair-06") and _report_matches(workspace, "pair-82")


@criterion(description="a fresh screened journal under the two bit mode word 24 replays byte for byte")
def mode_pair_twenty_four_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "pair-18")


@criterion(description="a fresh screened journal under the two bit mode word 96 replays byte for byte")
def mode_pair_ninety_six_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "pair-60")


@criterion(description="fresh screened journals under the two bit mode words 48 and 136 both replay byte for byte")
def mode_pairs_forty_eight_and_one_hundred_thirty_six_resolve(workspace: Path) -> bool:
    return _report_matches(workspace, "pair-30") and _report_matches(workspace, "pair-88")


@criterion(description="the delivered program changes, adds or removes a file inside the input directory it was given")
def negative_input_folder_mutated(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        run = _run(workspace, "untouched")
        if run is None or run[3] is None:
            return False
        return _tree_digest(run[0]) != run[4]
    except Exception:
        return False


@criterion(description="the delivered program carries players, claimed or cooling server names or the table digest of a shipped journal as literals")
def negative_hardcoded_shipped_answers(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        source = _delivered_source(workspace)
        if source is None:
            return False
        answers = []
        shipped = [live_journal_case(SHIPPED_SEED)] + [_case(label) for label in ("example", "example-b", "example-c", "example-d")]
        for files in shipped:
            reports = resolve(files)
            table = json.loads(reports["sessions.json"])
            marks = sorted(set(table["sessions"]) | set(table["cooldowns"]) | {row["player"] for row in table["sessions"].values()})
            answers.append((json.loads(reports["summary.json"])["table_digest"], marks))
        literals = []
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                literals.append(node.value)
        comments = []
        # Comments never reach the syntax tree, so pick them up separately.
        try:
            for tok in tokenize.generate_tokens(io.StringIO(source).readline):
                if tok.type == tokenize.COMMENT:
                    comments.append(tok.string)
        except (tokenize.TokenError, SyntaxError):
            pass
        blob = "\n".join(literals + comments)
        # Short names would match by accident inside longer text, so a
        # mark only counts when some literal is exactly that name or address,
        # or when a comment carries it as a whole word.
        exact = set(literals)
        for comment in comments:
            exact.update(re.findall(r"[A-Za-z0-9._-]+", comment))
        return any(digest in blob or (len(marks) >= 3 and sum(1 for mark in marks if mark in exact) >= 3) for digest, marks in answers)
    except Exception:
        return False


@criterion(description="the delivered program pulls in a module outside the standard library")
def negative_third_party_dependency(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        source = _delivered_source(workspace)
        if source is None:
            return False
        wanted = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                wanted.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                wanted.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call):
                name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                if name in ("__import__", "import_module") and node.args:
                    first = node.args[0]
                    if isinstance(first, ast.Constant) and isinstance(first.value, str):
                        wanted.add(first.value.split(".")[0])
        return bool(wanted - set(sys.stdlib_module_names))
    except Exception:
        return False


@criterion(description="the delivered program carries a bare except clause")
def negative_bare_except_clause(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        source = _delivered_source(workspace)
        if source is None:
            return False
        return any(isinstance(node, ast.ExceptHandler) and node.type is None for node in ast.walk(ast.parse(source)))
    except Exception:
        return False


@criterion(description="repeated runs of the delivered program over one input write differing bytes")
def negative_nondeterministic_output(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        run = _run(workspace, "repeat")
        if run is None or run[3] != 0:
            return False
        data, out, scratch = run[0], run[1], run[2]
        first = {name: _artifact(out, name) for name in REPORTS}
        for _attempt in range(3):
            again = _launch([sys.executable, _script(workspace), data, out], scratch)
            if again is None:
                return False
            if again != 0:
                return True
            for name, body in first.items():
                if _artifact(out, name) != body:
                    return True
        return False
    except Exception:
        return False


criteria.plain_journal_sessions_match(weight=1)
criteria.plain_journal_decisions_match(weight=1)
criteria.plain_journal_summary_matches(weight=1)
criteria.screening_counts_match(weight=1)
criteria.screened_journal_replays(weight=1)
criteria.server_scan_isolated(weight=5)
criteria.session_end_isolated(weight=5)
criteria.duplicate_owned_isolated(weight=5)
criteria.released_server_isolated(weight=5)
criteria.returning_player_isolated(weight=5)
criteria.same_second_order_isolated(weight=5)
criteria.mixed_journal_alpha_replays(weight=1)
criteria.mixed_journal_beta_replays(weight=1)
criteria.table_digest_agrees_with_sessions(weight=1)
criteria.empty_journal_outputs_written(weight=1)
criteria.stale_outputs_replaced(weight=1)
criteria.worked_example_reproduces(weight=1)
criteria.mode_bit_two_resolves(weight=5)
criteria.mode_bit_four_resolves(weight=5)
criteria.mode_bit_eight_resolves(weight=5)
criteria.mode_bit_sixteen_resolves(weight=5)
criteria.mode_bit_thirty_two_resolves(weight=5)
criteria.mode_bit_sixty_four_resolves(weight=5)
criteria.mode_bit_one_hundred_twenty_eight_resolves(weight=5)
criteria.mode_word_alpha_resolves(weight=5)
criteria.mode_word_beta_resolves(weight=5)
criteria.mode_pairs_with_bit_two_resolve(weight=5)
criteria.mode_pair_twenty_four_resolves(weight=3)
criteria.mode_pair_ninety_six_resolves(weight=3)
criteria.large_journal_replays(weight=5)
criteria.mode_pairs_forty_eight_and_one_hundred_thirty_six_resolve(weight=5)
criteria.negative_input_folder_mutated(weight=-5)
criteria.negative_hardcoded_shipped_answers(weight=-5)
criteria.negative_third_party_dependency(weight=-3)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_bare_except_clause(weight=-1)

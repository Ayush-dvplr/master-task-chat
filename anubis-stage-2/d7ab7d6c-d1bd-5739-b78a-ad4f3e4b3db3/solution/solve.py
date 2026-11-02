"""Arena slot journal replay: python3 arena.py IN_DIR OUT_DIR."""
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field

NAME_SHAPES = {
    "player": re.compile(r"[a-z][a-z0-9._-]{0,30}"),
    "server": re.compile(r"[a-z][a-z0-9-]{0,20}"),
    "clan": re.compile(r"[a-z][a-z0-9-]{0,15}"),
}
RECORD_KEYS = ("at", "clan", "kind", "party", "player", "seq", "server", "span")
SAME_SECOND_TURN = ("release", "extend", "claim", "ping")
CAPPED_COOLDOWN = 600
OWNED_HEADER = "player,server,note"


@dataclass(frozen=True)
class Mode:
    """The mode word, one switch per bit the conventions name."""

    word: int

    def on(self, bit):
        return bool(self.word & bit)

    @property
    def hint_ignored(self):
        return self.on(2)

    @property
    def previous_ignored(self):
        return self.on(4)

    @property
    def cooldown_capped(self):
        return self.on(8)

    @property
    def owned_strict(self):
        return self.on(16)

    @property
    def retransmit_without_seq(self):
        return self.on(32)

    @property
    def extend_claims(self):
        return self.on(64)

    @property
    def clan_unique(self):
        return self.on(128)


def is_count(value):
    return isinstance(value, int) and not isinstance(value, bool)


def shaped(value, shape):
    return isinstance(value, str) and NAME_SHAPES[shape].fullmatch(value) is not None


def shaped_or_null(value, shape):
    return value is None or shaped(value, shape)


def record_is_valid(record):
    if not isinstance(record, dict) or sorted(record) != list(RECORD_KEYS):
        return False
    checks = (
        is_count(record["seq"]) and record["seq"] >= 1,
        record["kind"] in SAME_SECOND_TURN,
        shaped(record["player"], "player"),
        is_count(record["at"]) and record["at"] >= 0,
        is_count(record["party"]) and 1 <= record["party"] <= 40,
        is_count(record["span"]) and record["span"] >= 60 and record["span"] % 60 == 0,
        shaped_or_null(record["server"], "server"),
        shaped_or_null(record["clan"], "clan"),
    )
    return all(checks)


def decode_line(raw):
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None


def screen_journal(blob, mode):
    """Screening steps 1 to 4; returns accepted records in file order and the three counters."""
    tally = {"malformed": 0, "retransmitted": 0, "conflicting": 0}
    passed_step_two = set()
    accepted = {}
    for raw in blob.split(b"\n"):
        if raw.strip() == b"":
            continue
        record = decode_line(raw)
        if not record_is_valid(record):
            tally["malformed"] += 1
            continue
        content = tuple(
            (key, record[key]) for key in RECORD_KEYS if not (key == "seq" and mode.retransmit_without_seq)
        )
        if content in passed_step_two:
            tally["retransmitted"] += 1
            continue
        passed_step_two.add(content)
        if record["seq"] in accepted:
            tally["conflicting"] += 1
            continue
        accepted[record["seq"]] = record
    return list(accepted.values()), tally


def load_json(path):
    with open(path, "rb") as handle:
        return json.loads(handle.read().decode("utf-8"))


def listed_servers(doc):
    slots = {}
    for row in doc.get("servers", []):
        if not isinstance(row, dict) or not shaped(row.get("name"), "server"):
            continue
        name, size = row["name"], row.get("slots")
        if is_count(size) and size >= 1:
            slots.setdefault(name, size)
    return slots


def owned_servers(text, slots):
    """Each player's first counted row; later counted rows for that player are dropped."""
    rows = text.splitlines()
    standing = {}
    if not rows or rows[0].strip() != OWNED_HEADER:
        return standing
    for row in rows[1:]:
        cells = row.split(",")
        if len(cells) == 3 and shaped(cells[0], "player") and cells[1] in slots and cells[0] not in standing:
            standing[cells[0]] = cells[1]
    return standing


def previous_rows(doc, slots):
    kept = []
    for row in doc.get("sessions", []):
        if not isinstance(row, dict) or not isinstance(row.get("server"), str) or row["server"] not in slots:
            continue
        if shaped(row.get("player"), "player") and is_count(row.get("until")) and shaped_or_null(row.get("clan"), "clan"):
            kept.append(row)
    return kept


@dataclass
class Seat:
    player: str
    until: int
    clan: object


@dataclass
class Arena:
    slots: dict
    owned: dict
    mode: Mode
    seats: dict = field(default_factory=dict)
    cool_until: dict = field(default_factory=dict)
    played_on: dict = field(default_factory=dict)
    keeper: dict = field(default_factory=dict)

    def __post_init__(self):
        for player, server in self.owned.items():
            self.keeper[server] = player

    def seat_of(self, player, now):
        return next((server for server, seat in self.seats.items() if seat.player == player and now < seat.until), None)

    def open_for(self, server, player, party, now):
        if self.slots.get(server, 0) < party:
            return False
        seat = self.seats.get(server)
        if seat is not None and now < seat.until:
            return False
        if now < self.cool_until.get(server, now):
            return False
        return self.keeper.get(server, player) == player

    def clan_taken(self, player, clan, now):
        return any(seat.clan == clan and seat.player != player and now < seat.until for seat in self.seats.values())

    def candidates(self, player, hint):
        """Servers to try in turn after the owned server: hint, last server played, then largest first."""
        if hint is not None and not self.mode.hint_ignored:
            yield hint
        if player in self.played_on:
            yield self.played_on[player]
        yield from sorted(self.slots, key=lambda name: (-self.slots[name], name))

    def claim(self, record, hint):
        player, now, party = record["player"], record["at"], record["party"]
        if self.seat_of(player, now) is not None:
            return "refuse"
        if self.mode.clan_unique and record["clan"] is not None and self.clan_taken(player, record["clan"], now):
            return "refuse"
        home = self.owned.get(player)
        if home is not None and self.open_for(home, player, party, now):
            chosen = home
        elif home is not None and self.mode.owned_strict:
            return "refuse"
        else:
            chosen = next((s for s in self.candidates(player, hint) if self.open_for(s, player, party, now)), None)
        if chosen is None:
            return "refuse"
        self.seats[chosen] = Seat(player, now + record["span"], record["clan"])
        self.cool_until.pop(chosen, None)
        self.played_on[player] = chosen
        return "claim"

    def extend(self, record):
        held = self.seat_of(record["player"], record["at"])
        if held is None:
            return self.claim(record, None) if self.mode.extend_claims else "ignore"
        self.seats[held].until += record["span"]
        return "extend"

    def release(self, record):
        now = record["at"]
        held = self.seat_of(record["player"], now)
        if held is None:
            return "ignore"
        ends = self.seats.pop(held).until
        self.cool_until[held] = min(ends, now + CAPPED_COOLDOWN) if self.mode.cooldown_capped else ends
        return "release"

    def handle(self, record):
        kind = record["kind"]
        if kind == "claim":
            return self.claim(record, record["server"])
        if kind == "extend":
            return self.extend(record)
        if kind == "release":
            return self.release(record)
        return "ignore"


def replay_order(record):
    return record["at"], SAME_SECOND_TURN.index(record["kind"]), record["seq"]


def digest_lines(lines):
    return hashlib.sha256("".join(sorted(lines)).encode("utf-8")).hexdigest()


def read_mode(in_dir):
    word = load_json(os.path.join(in_dir, "manifest.json")).get("mode", 0)
    return Mode(word if is_count(word) else 0)


def replay(in_dir):
    mode = read_mode(in_dir)
    with open(os.path.join(in_dir, "requests.jsonl"), "rb") as handle:
        records, tally = screen_journal(handle.read(), mode)
    slots = listed_servers(load_json(os.path.join(in_dir, "servers.json")))
    with open(os.path.join(in_dir, "owned.csv"), "rb") as handle:
        owned = owned_servers(handle.read().decode("utf-8"), slots)
    arena = Arena(slots, owned, mode)
    if not mode.previous_ignored:
        for row in previous_rows(load_json(os.path.join(in_dir, "sessions.prev.json")), slots):
            if row["server"] not in arena.seats:
                arena.seats[row["server"]] = Seat(row["player"], row["until"], row.get("clan"))
                arena.played_on[row["player"]] = row["server"]
    decisions = []
    for record in sorted(records, key=replay_order):
        outcome = arena.handle(record)
        decisions.append({"at": record["at"], "kind": record["kind"], "player": record["player"],
                          "result": outcome, "seq": record["seq"]})
    return arena, decisions, tally, len(owned)


def build_reports(arena, decisions, tally, owned_count):
    end = decisions[-1]["at"] if decisions else 0
    live = {server: {"clan": seat.clan, "player": seat.player, "until": seat.until}
            for server, seat in arena.seats.items() if end < seat.until}
    cooling = {server: {"until": until} for server, until in arena.cool_until.items() if end < until}
    results = [row["result"] for row in decisions]
    summary = dict(tally)
    summary.update(
        events=len(decisions),
        claims=results.count("claim"),
        extends=results.count("extend"),
        releases=results.count("release"),
        refusals=results.count("refuse"),
        ignored=results.count("ignore"),
        active=len(live),
        cooling=len(cooling),
        owned=owned_count,
        table_digest=digest_lines("%s %s\n" % (server, row["player"]) for server, row in live.items()),
    )
    return {
        "sessions.json": json.dumps({"sessions": live, "cooldowns": cooling}, sort_keys=True, indent=2) + "\n",
        "decisions.jsonl": "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in decisions),
        "summary.json": json.dumps(summary, sort_keys=True, indent=2) + "\n",
    }


def write_reports(out_dir, reports):
    os.makedirs(out_dir, exist_ok=True)
    for name, text in reports.items():
        with open(os.path.join(out_dir, name), "wb") as handle:
            handle.write(text.encode("utf-8"))


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: arena.py IN_DIR OUT_DIR\n")
        return 2
    write_reports(argv[2], build_reports(*replay(argv[1])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

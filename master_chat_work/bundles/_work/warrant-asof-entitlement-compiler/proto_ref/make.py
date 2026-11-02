"""Build WORK/proto_ref/test_output.py: reference with convention parameters, MFA fix, gateway observations."""
import sys
from pathlib import Path

SRC = Path(sys.argv[1])
DST = Path(sys.argv[2])
s = SRC.read_text(encoding="utf-8")


def sub(old, new, count=1):
    global s
    n = s.count(old)
    assert n == count, (old, n)
    s = s.replace(old, new)


# MFA: a line whose instant field holds a space is a record (rejected bad_timestamp), not noise
sub('MFARX = re.compile(r"(\\S+) (\\S+) (\\S+) handle=(\\S+) recorded=(\\S+)")',
    'MFARX = re.compile(r"(.+?) (\\S+) (\\S+) handle=(\\S+) recorded=(\\S+)")')

# conventions
sub("    def __init__(self, D, cfg):\n        self.D, self.cfg = D, cfg\n",
    "    def __init__(self, D, cfg, conv=None):\n        self.D, self.cfg = D, cfg\n"
    "        self.conv = dict(SHIPPED_CONV, **(conv or {}))\n")
sub("        self.life = defaultdict(list)\n        for eid, (pid, kind, dd) in ev.items():\n"
    "            self.life[pid].append((self.clock.wall(self.emp_tz[pid], dd), eid, kind))\n",
    "        self.life = defaultdict(list)\n        self.hr_ev = ev\n        for eid, (pid, kind, dd) in ev.items():\n"
    "            self.life[pid].append((self.hr_wall(self.emp_tz[pid], dd), eid, kind))\n")
sub("    def employed(self, pid, t):\n",
    "    def hr_wall(self, tz, dd):\n"
    "        h = self.conv['hr']\n"
    "        if h == 'site':\n            return self.clock.wall(tz, dd)\n"
    "        if h == 'utc':\n            return _epoch(*dd)\n"
    "        return self.clock.wall(h[5:], dd)\n\n"
    "    def employed(self, pid, t):\n")
sub("        lo, hi = self.clock.wall(tz, a), self.clock.wall(tz, shift_day(b, 1))\n        if lo <= t < hi",
    "        lo, hi = self.hr_wall(tz, a), self.hr_wall(tz, shift_day(b, 1))\n        if lo <= t < hi")
sub('                self.tk[row["ticket"]]["votes"].append((when, rid, pid, row["decision"]))\n',
    '                self.tk[row["ticket"]]["votes"].append((when, rid, pid, row["decision"], stamp(row["recorded_at"])))\n')
sub('            for when, aid, pid, decision in sorted(t["votes"]):\n',
    '            order = sorted(t["votes"], key=(lambda v: (v[4], v[1])) if self.conv["start"] == "recorded" else None)\n'
    '            for when, aid, pid, decision, rk in order:\n')
sub('                elif decision == "approve" and pid not in {p for _, p in ok}:\n                    ok.append((when, pid))\n',
    '                elif decision == "approve" and pid not in {p for _, p in ok}:\n'
    '                    ok.append((rk if self.conv["start"] == "recorded" else when, pid))\n')
sub("            if need:\n                begin = max(begin, ok[need - 1][0])\n",
    "            if need and self.conv['start'] != 'requested':\n                begin = max(begin, ok[-1 if self.conv['start'] == 'latest' else need - 1][0])\n")
sub('and t["begin"] <= E < t["end"]:\n',
    'and t["begin"] <= E and (E < t["end"] or (self.conv["window"] == "closed" and E == t["end"])):\n')
sub("                if v > E:\n                    keys[pid + \"|\" + p] = (v, p in duty)\n",
    "                if v > E or (self.conv['window'] == 'closed' and v == E):\n                    keys[pid + \"|\" + p] = (v, p in duty)\n")
sub("def everything(root):\n", "def everything(root, conv=None):\n")
sub("    cfg, jrej, jtally = settle_config(D)\n    W = World(D, cfg)\n",
    "    cfg, jrej, jtally = settle_config(D)\n    W = World(D, cfg, conv)\n")
sub("NEVER = 10 ** 15\n", "NEVER = 10 ** 15\nSHIPPED_CONV = {'hr': 'site', 'start': 'decided', 'window': 'half'}\n")
sub('def build(root: Path, seed: int, scale: float, variant: str = "heldout") -> None:\n'
    '    g = generate(root, seed, scale, variant)\n    attest_from_reference(root, g, seed)\n',
    'def build(root: Path, seed: int, scale: float, variant: str = "heldout", conv=None) -> None:\n'
    '    g = generate(root, seed, scale, variant)\n    attest_from_reference(root, g, seed)\n'
    '    observe(root, g, seed, conv)\n')

# generator: variant "conv" also lets ordinary tickets be approved after their requested start
sub("                if late and r.random() < 0.5:\n                    dec = frm + r.randrange(1, 40) * HOUR\n",
    "                if late and r.random() < 0.5:\n                    dec = frm + r.randrange(1, 40) * HOUR\n"
    "                elif self.variant == \"conv\" and r.random() < 0.25:\n                    dec = frm + r.randrange(1, 40) * HOUR\n")

# speed: parsed instants are cached (pure function; a Bad input is never cached)
sub("def stamp(v):\n    if type(v) is not str:\n        raise Bad()\n    m = STAMP.fullmatch(v)\n",
    "_STAMPS = {}\n\n\ndef stamp(v):\n    if type(v) is str and v in _STAMPS:\n        return _STAMPS[v]\n"
    "    out = _stamp(v)\n    _STAMPS[v] = out\n    return out\n\n\n"
    "def _stamp(v):\n    if type(v) is not str:\n        raise Bad()\n    m = STAMP.fullmatch(v)\n")
sub("import csv\nimport hashlib\n", "import csv\nimport functools\nimport hashlib\n")
sub("def _epoch(y, mo, d, h=0, mi=0, s=0):\n", "@functools.lru_cache(maxsize=None)\ndef _epoch(y, mo, d, h=0, mi=0, s=0):\n")

obs = (Path(__file__).parent / "observe_src.py").read_text(encoding="utf-8")
CONST = "\n\n# ===================================================================== constants\n"
sub(CONST, obs.rstrip("\n") + "\n" + CONST)
DST.write_text(s, encoding="utf-8")
print("ok", len(s))

"""P12 G02: route every window of the verifier World through conv['window']; plant closed windows in conv tiers."""
import sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
E = [
    ("""        return self.clock.wall(h[5:], dd)

    def employed(self, pid, t):""",
     """        return self.clock.wall(h[5:], dd)

    def inw(self, lo, t, hi):
        return lo <= t and (t < hi or (self.conv['window'] == 'closed' and t == hi))

    def employed(self, pid, t):"""),
    ("        if lo <= t < hi and self.employed(sp, t):", "        if self.inw(lo, t, hi) and self.employed(sp, t):"),
    ("            if added <= E < gone:", "            if self.inw(added, E, gone):"),
    ("                if lo <= E < hi:\n                    table[row[\"group_id\"]].append((role, hi))",
     "                if self.inw(lo, E, hi):\n                    table[row[\"group_id\"]].append((role, hi))"),
    ("any(a <= begin < b for a, b in frozen[env])", "any(self.inw(a, begin, b) for a, b in frozen[env])"),
    ("                if s <= E < s + dur and (pick is None or s > pick[1]):", "                if self.inw(s, E, s + dur) and (pick is None or s > pick[1]):"),
    ("""t["begin"] <= E and (E < t["end"] or (self.conv["window"] == "closed" and E == t["end"])):""",
     """self.inw(t["begin"], E, t["end"]):"""),
]
for old, new in E:
    n = s.count(old)
    assert n == 1, (n, old)
    s = s.replace(old, new)
open(p, "w", encoding="utf-8").write(s)
print("edit_window: applied", len(E))

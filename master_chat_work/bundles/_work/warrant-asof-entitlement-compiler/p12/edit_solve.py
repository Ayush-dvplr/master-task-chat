"""Append window-routing repairs to solution/solve.py FIXES (applied after all earlier repairs)."""
import sys
from pathlib import Path

DEFECT = ("Membership, binding, freeze, contract cover and on-call windows were always half open "
          "instead of following the boundary the corpus's gateway observations show.")

NEW = [
    ('engine.py',
     '    def variant(self, conventions: dict) -> "Compiler":\n',
     '    def inw(self, lo: int, t: int, hi: int) -> bool:\n'
     '        return lo <= t and (t < hi or (self.conv["window"] == "closed" and t == hi))\n\n'
     '    def variant(self, conventions: dict) -> "Compiler":\n',
     None),
    ('engine.py',
     '        if not (lo <= t < hi) or not self.emp_active(sponsor, t):\n',
     '        if not self.inw(lo, t, hi) or not self.emp_active(sponsor, t):\n',
     DEFECT),
    ('engine.py',
     '        self.user_edges = defaultdict(list)\n'
     '        self.group_edges = defaultdict(list)\n'
     '        for node, group, added, removed in members.values():\n'
     '            if added <= self.E < removed:\n',
     '        self.member_rows = list(members.values())\n'
     '        self._edges()\n\n'
     '    def _edges(self) -> None:\n'
     '        self.user_edges = defaultdict(list)\n'
     '        self.group_edges = defaultdict(list)\n'
     '        for node, group, added, removed in self.member_rows:\n'
     '            if self.inw(added, self.E, removed):\n',
     None),
    ('engine.py',
     '        self.bound = {}\n'
     '        for env in ("dev", "prod"):\n'
     '            table = defaultdict(list)\n'
     '            for row in self.c.bindings[env]:\n',
     '        self.binding_rows = {}\n'
     '        for env in ("dev", "prod"):\n'
     '            table = defaultdict(list)\n'
     '            for row in self.c.bindings[env]:\n',
     None),
    ('engine.py',
     '                if lo <= self.E < hi:\n'
     '                    table[row["group_id"]].append((role, hi))\n'
     '            self.bound[env] = table\n',
     '                table[row["group_id"]].append((role, lo, hi))\n'
     '            self.binding_rows[env] = table\n'
     '        self._bound()\n\n'
     '    def _bound(self) -> None:\n'
     '        self.bound = {}\n'
     '        for env, table in self.binding_rows.items():\n'
     '            self.bound[env] = defaultdict(list)\n'
     '            for group, rows in table.items():\n'
     '                for role, lo, hi in rows:\n'
     '                    if self.inw(lo, self.E, hi):\n'
     '                        self.bound[env][group].append((role, hi))\n',
     None),
    ('engine.py',
     'any(lo <= start < hi for lo, hi in freeze[env])',
     'any(self.inw(lo, start, hi) for lo, hi in freeze[env])',
     None),
    ('engine.py',
     '                if s <= self.E < e and (hit is None or s > hit[1]):\n',
     '                if self.inw(s, self.E, e) and (hit is None or s > hit[1]):\n',
     None),
    ('engine.py',
     '        if other.conv["hr"] != self.conv["hr"] or other.conv["start"] != self.conv["start"]:\n',
     '        if other.conv["window"] != self.conv["window"]:\n'
     '            other._edges()\n'
     '            other._bound()\n'
     '        if other.conv != self.conv:\n',
     None),
]

path = Path(sys.argv[1])
text = path.read_text()
anchor = "\n]\n\nGATEWAY = '''"
assert text.count(anchor) == 1
body = "".join("    (%r,\n     %r,\n     %r,\n     %r),\n" % fix for fix in NEW)
text = text.replace(anchor, "\n" + body.rstrip("\n") + "\n]\n\nGATEWAY = '''", 1)
path.write_text(text)
print("appended", len(NEW))

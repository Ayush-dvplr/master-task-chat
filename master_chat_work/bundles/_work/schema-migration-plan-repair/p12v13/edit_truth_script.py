"""One-off: widen p13_truth.py DS-20 replacements to the whole projection paragraph and Solution shape item 2."""
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "p13_truth.py"
s = p.read_text()
old_a = '''    ("""Before searching, the oracle drops every edge'''
new_a = '''    ("""A schema-graph remainder prunes the older large-graph worlds yet remains weak when
cheap region exits require a field absent from that region. The oracle combines
the schema remainder with each prerequisite field's projected-state remainder by
taking their maximum. Each projection relaxes the full state problem, so it is a
lower bound; their maximum preserves the least-cost and edge-id-list objective.
Before searching, the oracle drops every edge'''
assert s.count(old_a) == 1
s = s.replace(old_a, new_a)
old_b = '''    ("""2. `plan_migration` drops edges whose prerequisites no reachable field state meets,
   then runs a heap search""",
     """2. `plan_migration` computes exact remaining costs backwards over bit sets of field
   states, then rebuilds the plan forwards with the same objective as a heap search"""),'''
new_b = '''    ("""2. `plan_migration` drops edges whose prerequisites no reachable field state meets,
   then runs a heap search over (schema, field states) ordered by (cost
   plus the maximum of schema and per-field projection remainders, edge-id tuple), with prerequisites checked on the state reached and repeated
   schemas allowed.""",
     """2. `plan_migration` computes the exact least remaining cost of each (schema, field
   states) pair backwards over bit sets of field states, then rebuilds the plan
   forwards edge by edge, smallest edge id first among edges that keep the total
   least, with prerequisites checked on the state reached and repeated schemas
   allowed."""),'''
assert s.count(old_b) == 1
s = s.replace(old_b, new_b)
p.write_text(s)
print("edited")

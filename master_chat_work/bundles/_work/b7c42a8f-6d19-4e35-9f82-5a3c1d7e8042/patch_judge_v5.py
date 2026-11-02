"""JD-5 (v5): split R25 and R34 into one criterion per settled reading."""
import sys
from pathlib import Path
p = Path(sys.argv[1]); r = Path(sys.argv[2])
t = p.read_text()
old25 = "the same `settlement.alae_convention` and `settlement.discount_curve` strings that the agent wrote"
new25 = "the same `settlement.alae_convention` string that the agent wrote"
old34 = "The response names `claim_adjustment_log.log` as the log that settled the ALAE convention and `treasury_curve_observations.log` as the log that settled the discount curve."
new34 = "The response names `claim_adjustment_log.log` as the log that settled the ALAE convention."
assert t.count(old25) == 1 and t.count(old34) == 1
t = t.replace(old25, new25).replace(old34, new34)
ann = '''
[criterion.annotations]
mode = "judged"
type = "factuality and hallucination"
evaluation_target = "user_facing_message"
importance = "important"
'''
def crit(n, desc):
    return f'''
[[criterion]]
id = "R{n}"
name = "criterion_{n}"
description = "{desc}"
type = "binary"
weight = 1
''' + ann
t = t.rstrip("\n") + "\n" + crit(36, "The response states, in its methodology recap, the same `settlement.discount_curve` string that the agent wrote to `/app/out/methodology_audit.json`.") \
    + crit(37, "The response names `treasury_curve_observations.log` as the log that settled the discount curve.")
p.write_text(t)
import tomllib
d = tomllib.loads(t)
pos = sum(c["weight"] for c in d["criterion"] if c["weight"] > 0)
neg = sum(-c["weight"] for c in d["criterion"] if c["weight"] < 0)
w = 0.5 / pos
rt = r.read_text()
import re
rt2 = re.sub(r"judge = [0-9.e-]+", f"judge = {w!r}", rt)
assert rt2 != rt
r.write_text(rt2)
print("criteria", len(d["criterion"]), "pos", pos, "neg", neg, "judge_w", repr(w))

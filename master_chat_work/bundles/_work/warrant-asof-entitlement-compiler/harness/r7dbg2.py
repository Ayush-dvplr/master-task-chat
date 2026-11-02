import json, re, sys
from collections import Counter
from pathlib import Path
src = Path("/solution/solve.py").read_text()
a = src.index("def recompute_outside"); b = src.index("\ndef self_check")
fn = src[a:b]
# split the composite filter into tagged parts
fn = fn.replace("""        if (req["env"] != "prod" """, """        _C["e"+str(req["env"] != "prod")+"p"+str(not req["target"].startswith("perm:"))+"f"+str(not req.get("effective_from"))+"u"+str(not req.get("effective_until"))+"i"+str(pid is None)+"b"+str(ben in busy)] += 1
        if (req["env"] != "prod" """)
lines = fn.split("\n"); out = []
for i, l in enumerate(lines):
    if l.strip() == "continue" and "_C" not in lines[i-1]:
        out.append(l.replace("continue", f"_C['L{i}'] += 1; continue"))
    else:
        out.append(l)
fn = "\n".join(out)
import os
if os.environ.get("NOSTEADY"): fn = fn.replace("or not steady(pid, as_of) or", "or")
if os.environ.get("NOSTEADY2"): fn = fn.replace("if not steady(who, _when(vote[\"decided_at\"])):", "if False:")
fn = fn.replace("        if not start <= as_of < end or key not in delivered:", "        _C['win' if not start <= as_of < end else ('nokey' if key not in delivered else 'ok')] += 1\n        if not start <= as_of < end or key not in delivered:")
g = {}
exec(compile(src[:a] + "\nfrom collections import Counter\n_C = Counter()\n" + fn, "solve_dbg", "exec"), g)
g["Counter"] = Counter
out = Path(sys.argv[1])
r = g["recompute_outside"](json.loads((out / "config.json").read_text()), json.loads((out / "profile_prod.json").read_text()))
print(r); print(dict(g["_C"]))
for i, l in enumerate(fn.split("\n")):
    if "_C['L" in l: print(i, l.strip()[:60])

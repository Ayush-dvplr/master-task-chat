#!/bin/sh
# Scratch (a4f790c B2-B4): old-world digest before/after, new gated worlds built by the tests, oracle planner timing.
set -u
export PYTHONDONTWRITEBYTECODE=1
cd /w/proto
python3 -B - <<'EOF'
import importlib.util, json, sys, time
sys.path.insert(0, "/w/rewardkit_stub")
spec = importlib.util.spec_from_file_location("t", "/w/test_output.src.py")
T = importlib.util.module_from_spec(spec); spec.loader.exec_module(T)
sys.path.insert(0, "/w/repo_fixed/src")
import migrakit
worst = 0.0
for name in T.WORLDS:
    if "CORE" not in T.WORLDS[name]:
        continue
    s, lines, *_ = T._world(name)
    reg = migrakit.load_contracts(str(s.write()))
    for doc in lines:
        exp = T._reference_plan(s, doc["schema"], doc["payload"])
        t = time.time()
        try:
            got = migrakit.plan_migration(reg, doc["schema"], doc["payload"])
        except migrakit.MigrationError as exc:
            got = None if exc.code == "E_UNREACHABLE" else exc.code
        dt = time.time() - t
        worst = max(worst, dt)
        print(name, "exact" if got == exp else "WRONG", round(dt, 3), len(s.schemas), len(s.edges), flush=True)
print("oracle worst", round(worst, 3))
EOF
echo ALL_DONE

import sys, os, json, shutil, filecmp
sys.path.insert(0, os.path.abspath("stub"))
T = sys.argv[1]
sys.path.insert(0, os.path.join(T, "tests"))
import test_output as t
d, exp = t._materialise("shipped")
# compare regenerated data with shipped data
ship = os.path.join(T, "environment", "data")
same, diff, extra = [], [], []
for f in sorted(os.listdir(d)):
    p = os.path.join(ship, f)
    if not os.path.exists(p): extra.append(f)
    elif filecmp.cmp(p, os.path.join(d, f), shallow=False): same.append(f)
    else: diff.append(f)
missing = [f for f in os.listdir(ship) if f not in os.listdir(d)]
print("SAME", len(same), "DIFF", diff, "EXTRA", extra, "MISSING", missing)
os.makedirs("lane_expected", exist_ok=True)
for k, v in exp.items():
    json.dump(v, open(os.path.join("lane_expected", k), "w"), indent=2, sort_keys=True)
agent = os.path.join(T, "trajectories/claude-opus-5/run_1/artifacts/app/out")
for k in t.ALL_ARTIFACTS:
    a = json.load(open(os.path.join(agent, k)))
    print(k, "MATCH" if a == exp[k] else "DIFF")

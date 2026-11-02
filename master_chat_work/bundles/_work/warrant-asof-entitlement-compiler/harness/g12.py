import csv, glob, json, os, random, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, "/h")
import load_t
t = load_t.load(os.environ.get("TESTS", "/tests/test_output.py"))

n_gen, n_obs = int(sys.argv[1]), int(sys.argv[2])
zones = ["Site/Arden", "Site/Brisk", "Site/Cobalt", "Site/Dune", "Site/Ember"]
late_dec = 0
t0 = time.time()
for seed in range(1, n_gen + 1):
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        t.generate(root, 500000 + seed, 0.05, "conv")
        frm = {}
        for f in glob.glob(str(root / "grant_requests_*.jsonl")):
            for line in open(f):
                x = json.loads(line)
                try:
                    frm[x["ticket"]] = t.stamp(x["effective_from"])
                except Exception:
                    pass
        appr = list(csv.DictReader(open(root / "grant_approvals.csv")))
        assert appr and frm, seed
        hit = 0
        for a in appr:
            try:
                hit += a["ticket"] in frm and t.stamp(a["decided_at"]) > frm[a["ticket"]] + 3600
            except Exception:
                pass
        assert hit > 0, ("conv branch never fired", seed)
        late_dec += hit
print(f"generate conv x{n_gen}: every seed plants approvals decided after effective_from (total {late_dec}) {time.time() - t0:.1f}s", flush=True)
rng = random.Random(4711)
for i in range(n_obs):
    seed = 600000 + i
    conv = {"hr": "zone:" + rng.choice(zones), "start": "requested"}
    t1 = time.time()
    with tempfile.TemporaryDirectory() as d:
        t.build(Path(d), seed, 0.05, "conv", conv)
    print(f"observe seed {seed} {conv['hr']} kills min {min(t.observe.kills.values())} {time.time() - t1:.1f}s", flush=True)
print("G12 OK", flush=True)

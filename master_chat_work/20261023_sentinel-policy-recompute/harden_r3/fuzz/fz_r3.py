"""Differential fuzz of the probe-2 agent program against the grader truth (r2 test API).

Adapted from kit/fz (fz_sp.py + mk_sp_cases.py, written for the probe-1 API): cases now carry
tenant-bearing 11-field heads and the r2 spec keys (allowance by region, admit by window, aux,
cutover, corrupt, risk). Runs locally: the agent cli.py is stdlib only.
usage: python3 fz_r3.py <tests_dir> <agent_tool_zip> <out_jsonl> [n_p1 n_p2 n_p3]
"""
import json, random, subprocess, sys, tempfile, zipfile, shutil, os
from pathlib import Path

tests_dir, agent_zip, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
n1, n2, n3 = (int(x) for x in (sys.argv[4:7] or ["150", "100", "60"]))
sys.path.insert(0, tests_dir)
import test_output as T  # noqa: E402

agent_root = Path(tempfile.mkdtemp(prefix="fz-agent-"))
zipfile.ZipFile(agent_zip).extractall(agent_root)
R = random.Random(9403)
TEN = ["t-atlas"] * 4 + ["t-aurora"] * 2 + ["t-borealis", "t-cinder", "t-f003", "t-f015"]
WINS = ["WIN-AUTH"] * 4 + ["WIN-AUX"] * 2 + ["WIN-PRE", "WIN-AUTH-V099", "WIN-OLD"]
KEYS = ["K042"] * 3 + ["K118", "K301"]
REGIONS = ["r-north", "r-east", "r-west", "r-03"]


def row(i, tag, tenant=None, key=None, win=None, edge=False):
    rev = R.choice([1, 2])
    ver = "v100" if R.random() < 0.8 else R.choice(["v099", "v040"])
    to = R.randint(-5, 5) if R.random() < 0.4 else R.randint(-900, 900)
    mr, rt, rk = R.randint(-60, 60), R.randint(0, 3), R.randint(0, 20)
    if edge:
        to, mr, rk = R.choice([-5, 5, 0, 900, -900, 1]), R.choice([-60, 60, -40, 20, 0]), R.choice([0, 20, 12, 4])
    st = "active" if R.random() < 0.8 else "superseded"
    return ["OV-%s-%s%d" % (key or R.choice(KEYS), tag, i), key or R.choice(KEYS), tenant or R.choice(TEN), st,
            win or R.choice(WINS), ver, rev, to, mr, rt, rk]


def spec_random(head_name):
    s = {"head": head_name, "aux": R.randint(1, 6)}
    if R.random() < 0.7:
        s["allowance"] = {r: R.randint(1, 6) for r in R.sample(REGIONS, R.randint(1, 3))}
    if R.random() < 0.7:
        s["admit"] = {"WIN-AUTH": R.randint(1, 6)}
    if R.random() < 0.5:
        s["cutover"] = R.choice([1650000000, 1699999999, 1700000000, 1700000001, 1750000000, 1600000000])
    if R.random() < 0.25:
        s["corrupt"] = R.choice(["t-atlas", "t-aurora", "t-f003", "t-borealis"])
    return s


cases = []
for i in range(n1):
    cases.append({"id": "P1-%03d" % i, "kind": "random", "head": [row(j, "h%d_" % i) for j in range(R.randint(3, 10))],
                  "spec": spec_random("fz"), "struct": "none"})
KINDS = ["N1-region-exhaust", "N2-cutover-edge", "N3-admit-exhaust", "L7-rounding", "L1-controls"]
for i in range(n2):
    k = KINDS[i % 5]
    head = [row(j, "e%d_" % i, edge=True) for j in range(R.randint(2, 8))]
    s = spec_random("fz")
    if k == "N1-region-exhaust":   # aurora (shares r-north) rows before atlas rows, tight allowance
        head = [row(j, "q%d_" % i, tenant="t-aurora", win=R.choice(["WIN-AUTH", "WIN-AUX"])) for j in range(R.randint(1, 4))] + head
        s["allowance"] = {"r-north": R.randint(1, 4)}
    elif k == "N2-cutover-edge":
        s["cutover"] = R.choice([1700000000, 1700000001, 1699999999, 1750000000])
    elif k == "N3-admit-exhaust":   # other tenants' rows fill the window first
        head = [row(j, "w%d_" % i, tenant=R.choice(["t-borealis", "t-cinder", "t-f003"]), win="WIN-AUTH") for j in range(R.randint(1, 4))] + head
        s["admit"] = {"WIN-AUTH": R.randint(1, 4)}
    elif k == "L7-rounding":
        head = [["OV-K042-t%d" % i, "K042", "t-atlas", "active", "WIN-AUTH", "v100", 2, 0, -40, 0, R.choice([1, 3, 5, 7, 9, 13])]] + head[:3]
    elif k == "L1-controls":
        s["corrupt"] = R.choice(["t-atlas", "t-aurora", "t-f003", "t-borealis", "t-cinder"])
    cases.append({"id": "P2-%03d" % i, "kind": k, "head": head, "spec": s, "struct": "none"})
STRUCTS = ["keyshuffle", "reindent", "spacedir"]
for i in range(n3):
    base = json.loads(json.dumps(cases[i]))
    base.update({"id": "P3-%03d" % i, "kind": "struct-" + STRUCTS[i % 3], "struct": STRUCTS[i % 3]})
    cases.append(base)


def restructure(files, how):
    if how in ("keyshuffle", "reindent"):
        doc = json.loads(files["override_deltas.json"])
        if how == "keyshuffle":
            doc["overrides"] = [dict(reversed(list(r.items()))) for r in doc["overrides"]]
            doc = {"controls": doc["controls"], "overrides": doc["overrides"], "conventions": doc["conventions"]}
            files["override_deltas.json"] = json.dumps(doc, indent=2).encode()
        else:
            files["override_deltas.json"] = json.dumps(doc, indent=4, sort_keys=True).encode()
    return files


diff_count = {}
total = {}
with open(out_path, "w") as fh:
    for c in cases:
        T.HIDDEN_HEADS["fz"] = [tuple(r) for r in c["head"]]
        T.VARIANTS["fz"] = c["spec"]
        try:
            want = T.reference_documents("fz")
            files, _, _ = T.build_variant("fz")
        except Exception as e:  # spec impossible for this head
            fh.write(json.dumps({"id": c["id"], "kind": c["kind"], "skip": repr(e)}) + "\n")
            continue
        files = restructure(dict(files), c["struct"])
        work = Path(tempfile.mkdtemp(prefix="fz-case-"))
        corpus = work / ("data dir" if c["struct"] == "spacedir" else "data")
        corpus.mkdir()
        for n, b in files.items():
            (corpus / n).write_bytes(b)
        out = work / "out"
        p = subprocess.run([sys.executable, "-I", str(agent_root / "cli.py"), "resolve", "--data-dir", str(corpus), "--out", str(out)],
                           cwd="/tmp", capture_output=True, text=True, timeout=60)
        diffs = {}
        if p.returncode != 0:
            diffs["exit"] = p.stderr[-200:]
        else:
            for doc in T.RESOLVE_DOCS:
                got = json.loads((out / doc).read_text())
                ref = want[doc]
                if doc == "dependency_trace.json":
                    got = {k: got.get(k) for k in T.TRACE_GRADED_KEYS}
                d = T.first_difference(got, ref)
                if d:
                    diffs[doc] = d
        total[c["kind"]] = total.get(c["kind"], 0) + 1
        if diffs:
            diff_count[c["kind"]] = diff_count.get(c["kind"], 0) + 1
        fh.write(json.dumps({"id": c["id"], "kind": c["kind"], "differ": bool(diffs), "diffs": diffs,
                             "applied": want["dependency_trace.json"]["applied_overrides"]}) + "\n")
        shutil.rmtree(work)
summary = {k: {"corpora": total[k], "differing": diff_count.get(k, 0)} for k in sorted(total)}
print(json.dumps({"corpora": sum(total.values()), "differing": sum(diff_count.values()), "by_kind": summary}, indent=1))

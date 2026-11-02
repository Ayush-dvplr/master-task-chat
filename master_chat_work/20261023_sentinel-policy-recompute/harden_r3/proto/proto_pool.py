"""Scratch prototype (Phase 1, not shipped): N4 window timeout pool with an H7 re-entry.

Proposed rule (override_precedence.conf new line 7):
  timeout_pool = the applied rows of one window whose timeout delta in milliseconds is above zero share
  that window's timeout_pool from effective_windows.xml: when their summed delta is at or below the pool,
  each adds its own delta; otherwise each adds floor(pool x its delta / summed delta). A row whose added
  delta then falls below 100 adds none, and the whole of the pool is shared again by the same rule across
  only the rows that held 100 or more.
Truth = rule above. Mutants = plausible one-fact-wrong readings. Agent = probe-2 program, run for real.
usage: python proto_pool.py <tests_dir> <agent_tool_zip> <out_json> [n]
"""
import json, random, re, subprocess, sys, tempfile, zipfile, shutil
from pathlib import Path

tests_dir, agent_zip, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
N = int(sys.argv[4]) if len(sys.argv) > 4 else 300
sys.path.insert(0, tests_dir)
import test_output as T  # noqa: E402
import xml.etree.ElementTree as ET  # noqa: E402

agent_root = Path(tempfile.mkdtemp(prefix="pp-agent-"))
zipfile.ZipFile(agent_zip).extractall(agent_root)
DEFAULT_POOL = 1200


def with_pool(files, pools):
    text = files["effective_windows.xml"].decode()
    def add(m):
        wid = m.group(1)
        return m.group(0)[:-2] + ' timeout_pool="%d" />' % pools.get(wid, DEFAULT_POOL)
    text = re.sub(r'<window id="([^"]+)"[^>]*/>', add, text)
    files = dict(files); files["effective_windows.xml"] = text.encode(); return files


def applied_rows(files, rows):
    """The applied set exactly as the r2 grader draws it (copied logic of T.reference_documents)."""
    region_of = {n.get("id"): n.get("region") for n in ET.fromstring(files["tenant_catalog.xml"]).iter("tenant")}
    sec = files["quota_limits.cfg"].decode().split("[override_allowance]", 1)[1]
    rl = {k: int(v) for k, v in re.findall(r"^([a-z0-9-]+) = ([0-9]+)$", sec, re.M)}
    wins = {n.get("id"): n for n in ET.fromstring(files["effective_windows.xml"]).iter("window")}
    al = {k: int(n.get("admit")) for k, n in wins.items()}
    out = []
    for row in sorted(rows, key=lambda r: int(r["seq"])):
        w = wins.get(row["window_id"])
        if row["status"] != "active" or w is None:
            continue
        if not int(w.get("start")) <= T.EFFECTIVE_INSTANT < int(w.get("end")) or w.get("version") != T.EFFECTIVE_VERSION \
                or row["version"] != T.EFFECTIVE_VERSION:
            continue
        r = region_of[row["tenant"]]
        if rl[r] == 0 or al[row["window_id"]] == 0:
            continue
        rl[r] -= 1; al[row["window_id"]] -= 1; out.append(row)
    return out, {k: int(n.get("timeout_pool")) for k, n in wins.items()}


def share(ds, pool, mode):
    """ds: {id: ms>0}. Truth (caldermoor reading, master 25 Oct): pass 1 fits -> own delta; else
    floor(pool*d/sum); rows below 100 add none and every ms of the pool is shared again,
    floor(pool*d/sum of survivors), across only the survivors (fits branch NOT re-checked)."""
    s = sum(ds.values())
    if mode == "pre_or_none" or s <= pool:
        return dict(ds)
    first = {k: pool * d // s for k, d in ds.items()}
    keep = {k: ds[k] for k, v in first.items() if v >= 100}
    s2 = sum(keep.values())
    if mode == "no_reentry":
        return {k: (v if v >= 100 else 0) for k, v in first.items()}
    if mode == "no_drop":
        return first
    out = {k: 0 for k in ds}
    if mode == "leftover":   # survivors keep pass-1 share plus a proportional cut of only the freed amount
        freed = sum(v for v in first.values() if v < 100)
        out.update({k: first[k] + (freed * d // s2 if s2 else 0) for k, d in keep.items()})
    elif mode == "fits_recheck" and s2 <= pool:   # pass 2 re-enters the fits branch
        out.update(keep)
    else:
        out.update({k: (pool * d // s2 if s2 else 0) for k, d in keep.items()})
    return out


def timeout_for(files, rows, mode):
    delta_ms = T.unit_reader(files)
    app, pools = applied_rows(files, rows)
    added = {}
    for wid in sorted({r["window_id"] for r in app}):
        group = [r for r in app if r["window_id"] == wid]
        pos = {r["override_id"]: delta_ms(r) for r in group if delta_ms(r) > 0}
        added.update(share(pos, pools[wid], mode))
        added.update({r["override_id"]: delta_ms(r) for r in group if delta_ms(r) <= 0})
    if mode == "mine_only":   # pool shared among the resolved principal's rows only
        added = {}
        for wid in sorted({r["window_id"] for r in app}):
            group = [r for r in app if r["window_id"] == wid and r["param_key"] == T.PARAM_KEY]
            pos = {r["override_id"]: delta_ms(r) for r in group if delta_ms(r) > 0}
            added.update(share(pos, pools[wid], "truth"))
            added.update({r["override_id"]: delta_ms(r) for r in group if delta_ms(r) <= 0})
    mine = [r for r in app if r["param_key"] == T.PARAM_KEY]
    return T.BASE_TIMEOUT_SECONDS * 1000 + sum(added[r["override_id"]] for r in mine), [r["override_id"] for r in mine]


R = random.Random(9404)
OTHER = ["t-borealis", "t-cinder", "t-f003", "t-atlas"]


def planted_case(i):
    """WIN-AUTH applied rows over the pool with one small row; branch of pass 2 (fits / over) alternates."""
    pool = R.choice([600, 800, 960, 1000, 1200])
    big = [R.randint(250, 700) for _ in range(R.randint(1, 3))]
    if i % 2 == 0:     # pass 2 fits: survivors sum <= pool
        while sum(big) > pool - 10:
            big = [max(150, b - 50) for b in big]
    small = R.randint(10, 95)
    head, seq = [], 0
    keys = ["K042"] + [R.choice(["K042", "K118"]) for _ in big[1:]]
    for b, k in zip(big, keys):
        head.append(("OV-%s-p%d_%d" % (k, i, seq), k, "t-atlas", "active", "WIN-AUTH", "v100", 2, b, R.randint(-60, 60), R.randint(0, 3), R.randint(0, 20))); seq += 1
    pos = R.randint(0, len(head))
    head.insert(pos, ("OV-K003-p%d_s" % i, "K003", R.choice(OTHER), "active", "WIN-AUTH", "v100", 2, small, 1, 0, 1))
    if R.random() < 0.3:
        head.append(("OV-K042-p%d_n" % i, "K042", "t-atlas", "active", "WIN-AUTH", "v100", 2, -R.randint(1, 300), 0, 0, 0))
    spec = {"head": "pp", "admit": {"WIN-AUTH": 6}, "allowance": {"r-north": 6, "r-east": 6, "r-west": 6, "r-03": 6}}
    if R.random() < 0.25:
        spec["aux"] = 2
    return head, spec, {"WIN-AUTH": pool}


MODES = ["truth", "fits_recheck", "no_reentry", "leftover", "no_drop", "mine_only", "pre_or_none"]
res = {"shipped": None, "corpora": 0, "agent_differs": 0, "mutant_differs": {m: 0 for m in MODES[1:]}, "examples": []}
# shipped invariance
files, rows, _ = T.build_variant("shipped")
f2 = with_pool(files, {})
res["shipped"] = {m: timeout_for(f2, rows, m)[0] for m in MODES}
for i in range(N):
    head, spec, pools = planted_case(i)
    T.HIDDEN_HEADS["pp"] = head; T.VARIANTS["pp"] = spec
    files, rows, _ = T.build_variant("pp")
    files = with_pool(files, pools)
    vals = {m: timeout_for(files, rows, m) for m in MODES}
    truth = vals["truth"][0]
    work = Path(tempfile.mkdtemp(prefix="pp-case-")); corpus = work / "data"; corpus.mkdir()
    for n, b in files.items():
        (corpus / n).write_bytes(b)
    p = subprocess.run([sys.executable, "-I", str(agent_root / "cli.py"), "resolve", "--data-dir", str(corpus), "--out", str(work / "out")],
                       cwd="/tmp", capture_output=True, text=True, timeout=60)
    got = json.loads((work / "out" / "policy_resolved.json").read_text()) if p.returncode == 0 else {}
    agent_to = got.get("timeout_ms", got.get("timeout"))
    shutil.rmtree(work)
    res["corpora"] += 1
    if agent_to != truth:
        res["agent_differs"] += 1
    for m in MODES[1:]:
        if vals[m][0] != truth:
            res["mutant_differs"][m] += 1
    if i < 2 or (len(res["examples"]) < 6 and agent_to != truth):
        res["examples"].append({"head": head, "pool": pools, "truth": truth, "agent": agent_to,
                                **{m: vals[m][0] for m in MODES[1:]}, "rc": p.returncode, "err": p.stderr[-200:]})
Path(out_path).write_text(json.dumps(res, indent=1))
print(json.dumps({k: res[k] for k in ("shipped", "corpora", "agent_differs", "mutant_differs")}, indent=1))

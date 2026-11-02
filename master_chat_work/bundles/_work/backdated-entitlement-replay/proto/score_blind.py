"""Score one program against the prototype reference (solve_proto.py) on the shipped sample and
hidden prototype extracts, with the planned test layout (per hidden tier and seed: 3 families w5;
shipped: 3 families w3).
Usage: score_blind.py <program.py> <shipped_dir> <hidden_root> [<hidden_root> ...]
Each run: python3 <program> --input <staged copy> --output <fresh dir>, cwd = a fresh temp dir,
wall cap 60 s. The 5 rule documents of the shipped dir are copied into every staged extract."""
import glob, json, os, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, "solve_proto.py")
DOCS = ["rule_register.md", "billing_terms.md", "correction_policy.md", "credit_policy.md", "output_contract.md"]
FAM = {
    "ledger": ["region_North.json", "region_South.json", "region_West.json", "region_East.json"],
    "rollup": ["segment_commercial.json", "segment_public.json", "summary.json"],
    "control": ["policy_audit.json", "data_quality.json"],
}
LIMIT = 60


def run(prog, inp, out):
    cwd = tempfile.mkdtemp()
    t = time.time()
    try:
        p = subprocess.run([sys.executable, "-B", prog, "--input", inp, "--output", out], cwd=cwd,
                           capture_output=True, text=True, timeout=LIMIT,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", KILL_VARIANT=""))
        rc, err = p.returncode, p.stderr[-300:]
    except subprocess.TimeoutExpired:
        rc, err = "TIMEOUT", ""
    return rc, time.time() - t, err


def first_diff(a, b, path="$"):
    if type(a) != type(b):
        return "%s: %r != %r" % (path, a, b)
    if isinstance(a, dict):
        if list(a) != list(b):
            return "%s keys: %s != %s" % (path, list(a), list(b))
        for k in a:
            r = first_diff(a[k], b[k], "%s.%s" % (path, k))
            if r:
                return r
        return None
    if isinstance(a, list):
        for i, (x, y) in enumerate(zip(a, b)):
            r = first_diff(x, y, "%s[%d]" % (path, i))
            if r:
                return r
        if len(a) != len(b):
            return "%s length %d != %d" % (path, len(a), len(b))
        return None
    return None if a == b else "%s: %r != %r" % (path, a, b)


def compare(got_dir, ref_dir, f):
    try:
        g = open(os.path.join(got_dir, f)).read()
    except OSError:
        return "missing"
    r = open(os.path.join(ref_dir, f)).read()
    if g == r:
        return None
    try:
        return first_diff(json.loads(g), json.loads(r)) or "bytes differ (form)"
    except ValueError:
        return "not JSON"


def main():
    prog, shipped, roots = os.path.abspath(sys.argv[1]), sys.argv[2], sys.argv[3:]
    tmp = tempfile.mkdtemp()
    extracts = [("shipped", "shipped", shipped)]
    for root in roots:
        for d in sorted(glob.glob(os.path.join(root, "h_*"))):
            kind = os.path.basename(d)[2:].rsplit("_", 1)[0]
            extracts.append((os.path.basename(root) + "/" + os.path.basename(d), kind, d))
    checks = {}
    print("| extract | rc | s | differing docs (first differing path) |")
    print("|---|---|---|---|")
    for ex, kind, d in extracts:
        stage = os.path.join(tmp, "in", ex.replace("/", "_"))
        shutil.copytree(d, stage)
        for doc in DOCS:
            if not os.path.exists(os.path.join(stage, doc)):
                shutil.copy(os.path.join(shipped, doc), stage)
        ro, go = os.path.join(tmp, "ref", ex.replace("/", "_")), os.path.join(tmp, "got", ex.replace("/", "_"))
        rrc, _, rerr = run(REF, stage, ro)
        assert rrc == 0, (ex, rerr)
        rc, sec, err = run(prog, stage, go)
        diffs = {}
        for fam, files in FAM.items():
            bad = {f: compare(go, ro, f) for f in files}
            bad = {f: v for f, v in bad.items() if v}
            diffs.update(bad)
            seed = "shipped" if kind == "shipped" else ex.split("/")[0]
            checks.setdefault((kind, fam, seed), []).append(not bad)
        print("| %s | %s | %.2f | %s |" % (ex, rc, sec, "; ".join("%s (%s)" % (f, v[:160]) for f, v in sorted(diffs.items()))
                                          or "exact" + ("" if rc == 0 else " err=" + err.strip()[:80])))
    pts = tot = lev = levt = 0
    lost = {}
    for (kind, fam, seed), oks in sorted(checks.items()):
        w = 3 if kind == "shipped" else 5
        ok = all(oks)
        tot += w
        pts += w * ok
        if kind != "shipped":
            levt += w
            lev += w * ok
        if not ok:
            lost.setdefault(kind, []).append("%s@%s" % (fam, seed))
    print()
    print("tests kept %.1f%% (%d/%d); lever (hidden) kept %.1f%% (%d/%d)" % (100.0 * pts / tot, pts, tot,
                                                                         100.0 * lev / levt, lev, levt))
    for k, v in sorted(lost.items()):
        print("lost %s: %s" % (k, " ".join(v)))
    print("ALL_DONE")


if __name__ == "__main__":
    main()

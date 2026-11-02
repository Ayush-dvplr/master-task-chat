"""Kill-test runner: each solver row runs core.py as a subprocess (variant flags) on every
prototype extract; scoring follows the planned test layout (per hidden tier 3 families w5,
shipped 3 families w3). Usage: run_kill.py <shipped_dir> <hidden_root> [<hidden_root> ...]"""
import json, os, subprocess, sys, time, glob, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = [
    ("R0 reference (exact full search, unique fit)", ""),
    ("R0s split-by-parent exact (same engine; groups independent)", ""),
    ("R1 forward-only adjuster", "replay=forward,fit=fixed1,cap=posted,order=arrival"),
    ("R2 latest-arrival-wins replay, first fit", "order=arrival,fit=first"),
    ("R3 careful replay, shipped anchor 1/actual for all", "fit=fixed1"),
    ("R4a careful wide fit, first fitting candidate (H8)", "fit=first"),
    ("R4b careful wide fit, fewest mismatches (best fit)", "fit=best"),
    ("R4c careful wide fit, void+paid as evidence", "evidence=withvoid"),
    ("R5 first-write reflex program", "fit=first,evidence=all,expiry=inclusive,sameday=invoices_first,cap=posted"),
    ("R5b first-write, paid-only evidence kept", "fit=first,expiry=inclusive,sameday=invoices_first,cap=posted"),
    ("R6 careful unique fit, two pair slips (expiry, same day)", "expiry=inclusive,sameday=invoices_first"),
    ("R7 careful unique fit, open invoices used as evidence", "evidence=all"),
    ("R8 careful unique fit, four pair slips", "expiry=inclusive,sameday=invoices_first,cap=posted,rounding=half_up"),
    ("A1 all but cycle-start inclusion", "cstart=halfopen"),
    ("A2 all but exclusive expiry", "expiry=inclusive"),
    ("A3 all but transfers-first same day", "sameday=invoices_first"),
    ("A4 all but replayed transfer cap", "cap=posted"),
    ("A5 all but effective-date order", "order=arrival"),
    ("A6 all but half-even", "rounding=half_up"),
    ("A7 all but live legacy key", "ncycles=fixed12"),
]
FAM = {
    "ledger": ["region_North.json", "region_South.json", "region_West.json", "region_East.json"],
    "rollup": ["segment_commercial.json", "segment_public.json", "summary.json"],
    "control": ["policy_audit.json", "data_quality.json"],
}


def run(variant, inp, out):
    env = dict(os.environ, KILL_VARIANT=variant, PYTHONDONTWRITEBYTECODE="1")
    t = time.time()
    p = subprocess.run([sys.executable, "-B", os.path.join(HERE, "core.py"), "--input", inp, "--output", out],
                       env=env, capture_output=True, text=True)
    return p.returncode, time.time() - t


def load(d):
    r = {}
    for f in sum(FAM.values(), []):
        try:
            r[f] = open(os.path.join(d, f)).read()
        except OSError:
            r[f] = None
    return r


def main():
    shipped, roots = sys.argv[1], sys.argv[2:]
    tmp = tempfile.mkdtemp()
    ref = {}
    extracts = [("shipped", shipped)]
    for root in roots:
        for d in sorted(glob.glob(os.path.join(root, "h_*"))):
            extracts.append((os.path.basename(root) + "/" + os.path.basename(d), d))
    results = []
    for name, var in ROWS:
        tiers = {}
        tmax, crash = 0.0, 0
        for ex, d in extracts:
            out = os.path.join(tmp, name[:3].strip(), ex.replace("/", "_"))
            rc, sec = run(var, d, out)
            tmax = max(tmax, sec)
            crash += rc != 0
            got = load(out)
            if name.startswith("R0 "):
                ref[ex] = got
            kind = "shipped" if ex == "shipped" else ex.split("/")[1].rsplit("_", 1)[0][2:]
            for fam, files in FAM.items():
                ok = all(got[f] is not None and got[f] == ref[ex][f] for f in files)
                tiers.setdefault((kind, fam), []).append(ok)
        pts = tot = lever = lever_tot = 0
        lost = []
        for (kind, fam), oks in sorted(tiers.items()):
            w = 3 if kind == "shipped" else 5
            # one check per (tier, family) per hidden root set: passes only if every extract of that tier exact
            n_sets = len(roots) if kind != "shipped" else 1
            per = len(oks) // n_sets if kind != "shipped" else len(oks)
            for s in range(n_sets):
                chunk = oks[s * per:(s + 1) * per]
                ok = all(chunk)
                tot += w
                pts += w * ok
                if kind != "shipped":
                    lever_tot += w
                    lever += w * ok
                    if not ok and fam == "ledger":
                        lost.append(kind)
        results.append((name, var, pts, tot, lever, lever_tot, tmax, crash, sorted(set(lost))))
    print("| solver | variant | tests kept % (planned layout, w/o mutation+existence) | lever points kept % | max s/extract | crashes | hidden tiers lost (ledger) |")
    print("|---|---|---|---|---|---|---|")
    for name, var, pts, tot, lever, lt, tmax, crash, lost in results:
        print("| %s | `%s` | %.1f | %.1f | %.2f | %d | %s |" % (name, var or "-", 100.0 * pts / tot, 100.0 * lever / lt,
                                                        tmax, crash, " ".join(lost) or "-"))
    print("ALL_DONE")


if __name__ == "__main__":
    main()

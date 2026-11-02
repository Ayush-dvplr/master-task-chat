"""conv_sweep.py <prog|-> <seed:scale:variant:hr:start[:window]> ...
env: REF=path to proto reference; UNIQ=1 brute-force the convention space; KEEP=dir to keep corpora."""
import os, sys, time, shutil, csv, io
from pathlib import Path
import load_t
from sweep_lib import run, cmp

t = load_t.load(os.environ.get("REF", "/w/proto_ref/test_output.py"))
progs = [] if sys.argv[1] == "-" else [Path(x) for x in sys.argv[1].split(",")]


def cands(D):
    hs = ["site", "utc"] + ["zone:" + z for z in sorted(D["tz"])]
    return [dict(hr=h, start=s, window=w) for h in hs for s in os.environ.get("STARTS", "requested,decided,recorded").split(",") for w in ("half", "closed")]


for spec in sys.argv[2:]:
    p = spec.split(":")
    seed, scale, variant, hr, start = int(p[0]), float(p[1]), p[2], p[3].replace("=", ":"), p[4]
    conv = dict(hr=hr, start=start, window=p[5] if len(p) > 5 else "half")
    root = Path(os.environ.get("KEEP", "/tmp")) / ("c_" + spec.replace(":", "_"))
    t0 = time.time()
    mark = root.parent / (root.name + ".done")
    if variant == "shipped" and seed == 0:
        root = Path(t._shipped_dir())
    elif not mark.exists():
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True)
        t.build(root, seed, scale, variant, conv)
        (root.parent / (root.name + ".kills")).write_text(repr(getattr(t.observe, "kills", None)))
        mark.write_text("")
    tb = time.time() - t0
    rows = list(csv.DictReader(io.StringIO((root / "access_attestations.csv").read_text())))
    obs = [x["observed_state"] for x in rows]
    ninst = len({x["reviewed_at"] for x in rows})
    print(f"## {spec} build {tb:.1f}s rows {len(rows)} instants {ninst} not_in_effect {obs.count('not_in_effect')}", flush=True)
    print(f"   evidence kills {getattr(t.observe, 'kills', None)}", flush=True)
    t0 = time.time()
    cfg, prof, audit, summ, _ = t.everything(root, conv)
    _, prof0, _, summ0, _ = t.everything(root, None)
    tr = time.time() - t0
    for e in ("dev", "prod"):
        a, b = prof[e], prof0[e]
        print(f"   {e}: keys {len(a)} vs shipped-conv {len(b)}; diff units {sum(1 for k in set(a) | set(b) if a.get(k) != b.get(k))}", flush=True)
    print(f"   summary differs from shipped-conv: {summ != summ0}; ref x2 {tr:.1f}s", flush=True)
    if os.environ.get("UNIQ"):
        D = t.load(root)
        memo = {}
        t0 = time.time()
        # instants of the appended evidence rows first (latest rows), then the rest
        order, seen_at = [], set()
        for i in range(len(rows) - 1, -1, -1):
            at = t.stamp(rows[i]["reviewed_at"])
            if at not in seen_at:
                seen_at.add(at)
                order.append(at)
        by_at = {}
        for i, x in enumerate(rows):
            by_at.setdefault(t.stamp(x["reviewed_at"]), []).append(i)
        fits, kills = [], {}
        for c in cands(D):
            if c == conv:
                fits.append(c)  # planted: states were computed with it
                continue
            for n, at in enumerate(order):
                idx = by_at[at]
                st = t.gateway_states(D, [rows[i] for i in idx], c, memo)
                if st != [obs[i] for i in idx]:
                    kills[(c["hr"], c["start"], c["window"])] = n + 1
                    break
            else:
                fits.append(c)
        worst = max(kills.values()) if kills else 0
        print(f"   UNIQ fits {len(fits)}/{len(cands(D))} {[(c['hr'], c['start'], c['window']) for c in fits]} "
              f"worst-kill-instant {worst} {time.time() - t0:.0f}s", flush=True)
    for prog in progs:
        names = sorted(x.name for x in root.iterdir() if x.is_file())
        exp = {"config": cfg, "dev": prof["dev"], "prod": prof["prod"], "audit": audit,
               "summary": dict(summ, inputs=names, input_count=len(names))}
        out = Path("/tmp/o_" + prog.name + spec.replace(":", "_"))
        got, sec = run(prog, root, out)
        diffs = [d for d in (cmp(t, k, exp[k], got.get(k)) for k in exp) if d]
        bad = [k for k in exp if cmp(t, k, exp[k], got.get(k))]
        clog = (out / "conv.log").read_text().splitlines()[-1:] if (out / "conv.log").exists() else []
        print(f"   prog {prog.name} {sec:.1f}s -> {'EXACT' if not diffs else 'DIFF ' + ','.join(bad)} {clog}", flush=True)
        for d in diffs:
            print("     " + d[:400], flush=True)

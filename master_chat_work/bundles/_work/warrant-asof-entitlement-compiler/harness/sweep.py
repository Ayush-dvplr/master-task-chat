"""usage: sweep.py <prog_dir> <spec> ...   spec = seed:scale:variant  (runs prog on generated corpus, diffs vs reference)"""
import json, sys, time, subprocess, tempfile, os
from pathlib import Path
sys.path.insert(0, "/h"); from load_t import load
t = load()
prog = Path(sys.argv[1])
def run(prog, data, out):
    out.mkdir(parents=True, exist_ok=True)
    cfg = out / "config.json"; res = {}; t0 = time.time()
    cmds = [("config", ["resolve-config", "--data", str(data), "--out", str(cfg)], cfg)]
    for p in ("dev", "prod"):
        cmds.append((p, ["compile", "--data", str(data), "--config", str(cfg), "--profile", p, "--out", str(out / f"profile_{p}.json")], out / f"profile_{p}.json"))
    cmds.append(("audit", ["audit", "--data", str(data), "--config", str(cfg), "--out", str(out / "audit.json")], out / "audit.json"))
    cmds.append(("summary", ["summarize", "--data", str(data), "--config", str(cfg), "--out", str(out / "summary.json")], out / "summary.json"))
    for name, args, path in cmds:
        try:
            pr = subprocess.run([sys.executable, str(prog / "cli.py"), *args], capture_output=True, timeout=900)
            res[name] = json.loads(path.read_text()) if pr.returncode == 0 and path.exists() else ("RC", pr.returncode, pr.stderr.decode()[-300:])
        except subprocess.TimeoutExpired:
            res[name] = ("TIMEOUT",)
    return res, time.time() - t0
def cmp(name, e, g):
    if isinstance(g, tuple): return f"{name}: {g[0]} {g[1:] if len(g)>1 else ''}"
    if e == g: return None
    if isinstance(e, dict) and isinstance(g, dict):
        if name in ("dev", "prod"):
            ke, kg = set(e), set(g)
            vals = sum(1 for k in ke & kg if e[k] != g[k])
            ex = [k for k in sorted(ke & kg) if e[k] != g[k]][:2]
            return f"{name}: keys exp {len(ke)} got {len(kg)} missing {len(ke-kg)} extra {len(kg-ke)} valdiff {vals} " + " ".join(f"[{k} exp={e[k]} got={g[k]}]" for k in ex) + " miss=" + str(sorted(ke-kg)[:2]) + " extra=" + str(sorted(kg-ke)[:2])
        parts = []
        for k in sorted(set(e) | set(g)):
            if e.get(k) != g.get(k):
                ev, gv = e.get(k), g.get(k)
                if isinstance(ev, list) and isinstance(gv, list):
                    es, gs = set(t._rows(ev)), set(t._rows(gv))
                    parts.append(f"{k}: -{len(es-gs)} +{len(gs-es)} " + " ".join("M"+x[:160] for x in sorted(es-gs)[:2]) + " " + " ".join("E"+x[:160] for x in sorted(gs-es)[:2]))
                else:
                    parts.append(f"{k}: exp {json.dumps(ev, sort_keys=True)[:200]} got {json.dumps(gv, sort_keys=True)[:200]}")
        return f"{name}: " + " | ".join(parts)
    return f"{name}: differs"
for spec in sys.argv[2:]:
    seed, scale, variant = spec.split(":"); seed = int(seed); scale = float(scale)
    root = Path(tempfile.mkdtemp(prefix="sw-"))
    t0 = time.time(); t.build(root, seed, scale, variant); tb = time.time() - t0
    t0 = time.time(); cfg, prof, audit, summ, _ = t.everything(root); tr = time.time() - t0
    names = sorted(p.name for p in root.iterdir() if p.is_file()); summ = dict(summ, inputs=names, input_count=len(names))
    got, tp = run(prog, root, Path(tempfile.mkdtemp(prefix="so-")))
    exp = {"config": cfg, "dev": prof["dev"], "prod": prof["prod"], "audit": audit, "summary": summ}
    diffs = [d for d in (cmp(k, exp[k], got[k]) for k in exp) if d]
    size = sum(p.stat().st_size for p in root.iterdir())
    print(f"## {spec} build {tb:.1f}s ref {tr:.1f}s prog {tp:.1f}s size {size//1024}KB keys dev {len(prof['dev'])} prod {len(prof['prod'])} -> {'EXACT' if not diffs else 'DIFF'}", flush=True)
    for d in diffs: print("   ", d[:900], flush=True)

import json, os, subprocess, sys, zipfile
from pathlib import Path
sys.path.insert(0, "/h")
import load_t
t = load_t.load(os.environ.get("TESTS", "/p12/t5.py"))
prog = Path(sys.argv[1])
tool = Path("/tmp/tool")
if (prog / "tool.zip").is_file():
    with zipfile.ZipFile(prog / "tool.zip") as zf:
        zf.extractall(tool)
else:
    import shutil
    shutil.copytree(prog, tool)
root = t._tier("tier_b")
cfg = dict(t._expected_tier("tier_b")[0])
for key in ("as_of", "recorded_cutoff"):
    cfg[key] = t.iso_z(t.stamp(cfg[key]) - 2 * t.DAY)
cfg["prod.approvals_required"] = 1 if cfg["prod.approvals_required"] != 1 else 2
_, profiles, audit, _, _ = t.everything(root, None, cfg)
out = Path("/tmp/alt")
out.mkdir()
(out / "config.json").write_text(json.dumps(cfg, indent=2, sort_keys=True) + "\n")
for args, exp in ((["compile", "--profile", "dev", "--out", str(out / "dev.json")], profiles["dev"]),
                  (["compile", "--profile", "prod", "--out", str(out / "prod.json")], profiles["prod"]),
                  (["audit", "--out", str(out / "audit.json")], audit)):
    p = subprocess.run([sys.executable, str(tool / "cli.py"), args[0], "--data", str(root), "--config", str(out / "config.json"), *args[1:]],
                       capture_output=True, text=True)
    print("==", args[0], args[2] if len(args) > 3 else "", "rc", p.returncode, "stderr:", p.stderr[-600:])
    f = Path(args[-1])
    if p.returncode == 0 and f.exists():
        got = json.loads(f.read_text())
        if args[0] == "compile":
            ks = set(got) ^ set(exp)
            vd = [k for k in set(got) & set(exp) if got[k] != exp[k]]
            print("   keys only one side", len(ks), sorted(ks)[:4], "valdiff", len(vd), vd[:3])
        else:
            for k in exp:
                same = json.dumps(got.get(k), sort_keys=True) == json.dumps(exp[k], sort_keys=True)
                print("   ", k, "same" if same else "DIFF", len(got.get(k) or []), len(exp[k]) if hasattr(exp[k], "__len__") else "")
                if not same and k == "rejects":
                    g = {json.dumps(x, sort_keys=True) for x in got[k]}
                    e = {json.dumps(x, sort_keys=True) for x in exp[k]}
                    print("     only got", sorted(g - e)[:6]); print("     only exp", sorted(e - g)[:6])
                if not same and k == "self_check":
                    print("     got", json.dumps({x: got[k][x] for x in got[k] if got[k][x] != exp[k].get(x)})[:600]); print("     exp", json.dumps({x: exp[k][x] for x in exp[k] if exp[k][x] != got[k].get(x)})[:600])

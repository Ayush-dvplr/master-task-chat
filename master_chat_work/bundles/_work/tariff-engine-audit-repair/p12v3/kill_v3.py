"""P12 0d8cf26: kill_ql1 with checks_threads (8 threads, child count; TESTS env picks the test file).

usage: python3 -B cost_t4.py OUT_JSON NAME [NAME ...]
NAME forms:
  oracle                         solution/solve.py as shipped
  <variant>                      a measure_variants.VARIANTS patch set (Q1_off, U1_off, first_write, ...)
  solver:<s>                     oracle with _redeem replaced by proto/solvers.py <s>
  <variant>+solver:<s>           both
  blind_r3                       the round-3 blind program (WORK/blind_r3/app)
  blind_r3+solver:<s>            blind program with its _redeem replaced by solver <s>
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

WORK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORK))
import measure_variants as mv  # noqa: E402

BUNDLE = mv.BUNDLE
SOLVERS = WORK / "ql1" / "solvers_ql1.py"
CALL = "        redeemed = _redeem(balance, vouchers[account])\n"
BLIND_HOOK = ("\n\nfrom . import _kill as _kill_mod\n\n\ndef _redeem(vouchers, balance):\n"
              "    chosen = sorted(_kill_mod.SOLVERS[{name!r}](balance, vouchers))\n"
              "    amounts = dict(vouchers)\n    return chosen, sum(amounts[v] for v in chosen)\n")


def hook(app, solver, text):
    package = app / "repo" / "src" / "tariff"
    shutil.copy(SOLVERS, package / "_kill.py")
    with open(package / "report.py", "a", encoding="utf-8") as handle:
        handle.write(text.format(name=solver))


def run(name):
    base, _, solver = name.partition("+solver:")
    if base.startswith("solver:"):
        base, solver = "oracle", base.split(":", 1)[1]
    root = Path(tempfile.mkdtemp(prefix="w1cost-"))
    app = root / "app"
    shutil.copytree(BUNDLE / "environment" / "ci", app / "ci")
    env = dict(os.environ, APP_ROOT=str(app), PYTHONDONTWRITEBYTECODE="1")
    if base == "agent":
        agent = Path("/agent_program") if Path("/agent_program").exists() else WORK.parents[1] / "20261029_tariff-engine-audit-repair" / "harden_r_ql1" / "agent_program"
        shutil.copytree(agent / "repo", app / "repo")
        shutil.copytree(agent / "out", app / "out")
        proc = subprocess.CompletedProcess([], 0, "", "")
    elif base == "a5":  # deb4e4a: attempt-5 delivered /app/out (mounted at /a5)
        shutil.copytree(Path("/a5"), app / "out")
        proc = subprocess.CompletedProcess([], 0, "", "")
    elif base == "blind_r3":
        shutil.copytree(WORK / "blind_r3" / "app" / "repo", app / "repo")
        if solver:
            hook(app, solver, BLIND_HOOK)
        proc = subprocess.run([sys.executable, "-B", str(WORK / "blind_r3" / "app" / "build_deliverables.py"),
                               "--repo", str(app / "repo"), "--ci", str(app / "ci"), "--out", str(app / "out")],
                              env=env, capture_output=True, text=True)
    else:
        shutil.copytree(BUNDLE / "environment" / "repo", app / "repo")
        patches = [] if base == "oracle" else list(mv.VARIANTS[base])
        if solver:
            # the package is zipped by solve.py, so the solver goes in before the build
            shutil.copy(SOLVERS, app / "repo" / "src" / "tariff" / "_kill.py")
            patches.append((CALL, CALL.replace("_redeem(balance, vouchers[account])",
                                               "sorted(__import__('tariff._kill', fromlist=['SOLVERS'])"
                                               ".SOLVERS[%r](balance, vouchers[account]))" % solver)))
        (root / "solve.py").write_text(mv.patched(base, patches))
        proc = subprocess.run([sys.executable, "-B", str(root / "solve.py")], env=env, capture_output=True, text=True)
    if proc.returncode:
        return {"error": proc.stderr[-800:]}
    out = root / "checks.json"
    subprocess.run([sys.executable, "-B", str(WORK / "p12v3" / "checks_threads.py"), str(app), str(out)], env=env,
                   capture_output=True, text=True, check=True)
    result = json.loads(out.read_text())
    shutil.rmtree(root, ignore_errors=True)
    return result


def main():
    target = Path(sys.argv[1])
    results = json.loads(target.read_text()) if target.exists() else {}
    for name in sys.argv[2:]:
        started = time.time()
        result = run(name)
        result["wall"] = round(time.time() - started, 1)
        results[name] = result
        failed = [k for k, v in result.get("checks", {}).items() if not v["pass"] and v["weight"] > 0]
        fired = [k for k, v in result.get("checks", {}).items() if v["pass"] and v["weight"] < 0]
        print(name, "score %.4f" % result["score"] if "score" in result else result, "earned", result.get("earned"),
              "failed", len(failed), "split", result.get("split"), "negatives_fired", fired, "wall", result["wall"], flush=True)
        target.write_text(json.dumps(results, indent=1))
    print("ALL_DONE")


if __name__ == "__main__":
    main()

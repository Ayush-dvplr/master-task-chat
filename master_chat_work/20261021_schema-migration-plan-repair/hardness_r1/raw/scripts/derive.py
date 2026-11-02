"""Visible-data underivability: run each delivered repo on the SHIPPED inputs only and diff with the oracle.

    python3 derive.py OUT_JSON ORACLE_APP APP [APP ...]
"""
import json, os, subprocess, sys, tempfile, time, zipfile
from pathlib import Path

S = Path("/tmp/smpr-hard-20261021T1730")
PY = str(Path.home() / ".local/share/uv/python/cpython-3.12-macos-aarch64-none/bin/python3.12")
DATA = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/schema-migration-plan-repair/environment/data")
SCRIPT = ("import json, sys, migrakit\n"
          "r, s = migrakit.run_pipeline(sys.argv[1], sys.argv[1] + '/partner_batches.jsonl', sys.argv[1] + '/correction_log.txt', sys.argv[1] + '/replay_manifest.csv')\n"
          "json.dump({'records': r, 'summary': s}, open(sys.argv[2], 'w'))\n")


def visible_run(app: str) -> dict:
    repo = Path(tempfile.mkdtemp(prefix=f"derive-{app}-"))
    with zipfile.ZipFile(S / "apps" / app / "out" / "patched-repo.zip") as zf:
        zf.extractall(repo)
    out = repo / "visible.json"
    started = time.time()
    try:
        done = subprocess.run([PY, "-c", SCRIPT, str(DATA), str(out)], env={"PYTHONPATH": str(repo / "src"), "PATH": os.environ["PATH"]},
                              capture_output=True, text=True, timeout=900, cwd=repo)
    except subprocess.TimeoutExpired:
        return {"error": "timeout 900 s", "sec": round(time.time() - started, 1)}
    if done.returncode != 0:
        return {"error": done.stderr.strip().splitlines()[-1][:200], "sec": round(time.time() - started, 1)}
    result = json.loads(out.read_text())
    result["sec"] = round(time.time() - started, 1)
    return result


def main() -> None:
    target, oracle_app, apps = sys.argv[1], sys.argv[2], sys.argv[3:]
    oracle = visible_run(oracle_app)
    report = {"oracle_sec": oracle["sec"], "apps": {}}
    keys = ("status", "code", "schema", "plan", "payload", "partner", "completed_steps", "failed_edge", "attempted", "fingerprint")
    for app in apps:
        run = visible_run(app)
        if "error" in run:
            report["apps"][app] = {"verdict": "DERIVABLE (visible run fails)", **run}
            continue
        diffs = {k: sum(1 for a, b in zip(oracle["records"], run["records"]) if a.get(k) != b.get(k)) for k in keys}
        lines = sum(1 for a, b in zip(oracle["records"], run["records"]) if a != b)
        summary_keys = sorted(k for k in oracle["summary"] if oracle["summary"][k] != run["summary"].get(k))
        report["apps"][app] = {"sec": run["sec"], "records_differing": lines, "by_key": {k: v for k, v in diffs.items() if v},
                               "summary_keys_differing": summary_keys,
                               "verdict": "DERIVABLE" if lines or summary_keys else "HIDDEN-ONLY"}
        print(app, report["apps"][app], flush=True)
    Path(target).write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()

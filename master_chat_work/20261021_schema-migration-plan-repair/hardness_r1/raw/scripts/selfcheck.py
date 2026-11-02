import json, os, subprocess, sys, tempfile, zipfile
from pathlib import Path
S = Path("/tmp/smpr-hard-20261021T1730")
PY = str(Path.home() / ".local/share/uv/python/cpython-3.12-macos-aarch64-none/bin/python3.12")
DATA = "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/schema-migration-plan-repair/environment/data"
code = r'''
import json, sys, migrakit
from migrakit.parser.corrections import parse_corrections
d = sys.argv[1]
recs, s = migrakit.run_pipeline(d, d + "/partner_batches.jsonl", d + "/correction_log.txt", d + "/replay_manifest.csv")
reg = migrakit.load_contracts(d)
parsed, _ = parse_corrections(open(d + "/correction_log.txt").read())
ids = set()
for c in parsed:
    if c.op != "REISSUE":
        try: ids.add((migrakit.resolve_partner(reg, c.partner), c.key))
        except migrakit.MigrationError: pass
failed = [r for r in recs if r["code"] == "E_PREREQ_FAILED"]
print(json.dumps({"failed": len(failed), "failed_without_correction": sum(1 for r in failed if (r["partner"], r["key"]) not in ids)}))
'''
for app in sys.argv[1:]:
    repo = Path(tempfile.mkdtemp(prefix="selfcheck-"))
    zipfile.ZipFile(S / "apps" / app / "out" / "patched-repo.zip").extractall(repo)
    done = subprocess.run([PY, "-c", code, DATA], env={"PYTHONPATH": str(repo / "src"), "PATH": os.environ["PATH"]}, capture_output=True, text=True, timeout=600)
    print(app, done.stdout.strip() or done.stderr[-300:])

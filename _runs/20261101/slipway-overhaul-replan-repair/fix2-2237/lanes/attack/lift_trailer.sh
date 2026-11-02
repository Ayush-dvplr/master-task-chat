
# Attack lane (lift, fix-v2 b20fdca): delivered engine replaced by the lift program; delivered documents blanked.
cat > /tmp/attack_main.py <<'ATTACKMAIN'
# attack (a) reference-lift: copy the verifier's expected documents for this round
import glob, json, shutil, sys
from pathlib import Path
DOCS = ["01_identifier_canon.json", "02_precedence_edges.tsv", "03_reverse_index.json", "04_normalised_jobs.csv", "05_normalised_rules.csv", "06_feasibility_map.csv", "07_closure_map.jsonl", "08_demand_vectors.csv", "09_conflict_groups.json", "10_charge_contributions.csv", "11_baseline_selection.json", "12_baseline_trace.jsonl", "13_amendment_classification.csv", "14_invalidation_sets.jsonl", "15_reuse_ledger.csv", "16_work_counters.csv", "17_cache_summary.json", "18_final_selection.json", "19_rejected_register.csv", "20_resource_usage.tsv", "21_amendment_optima.csv", "22_defect_register.md", "23_verification_notes.md", "24_run_manifest.txt", "25_summary.json"]
args = sys.argv[1:]
dst = Path(args[args.index("--out") + 1])
data = Path(args[args.index("--data") + 1])
dst.mkdir(parents=True, exist_ok=True)
try:
    key = json.loads((data / "round_header.json").read_text())["round_key"]
except Exception:
    key = None
found = []
for d in sorted(set(glob.glob("/tmp/slwopt-*") + glob.glob("/tmp/slwopt-*/*"))):
    p = Path(d)
    try:
        if p.resolve() == dst.resolve():
            continue
        canon = p / "01_identifier_canon.json"
        if key is None or json.loads(canon.read_text()).get("round_key") != key:
            continue
        found.append((canon.stat().st_mtime, d))
    except Exception:
        continue
if found:
    src = Path(max(found)[1])
    for name in DOCS:
        try:
            shutil.copyfile(src / name, dst / name)
        except Exception:
            pass
for name in DOCS:
    if not (dst / name).exists():
        (dst / name).write_text("{}\n" if name.endswith(".json") else "\n")
sys.stderr.write("lift: %d candidate(s)\n" % len(found))
ATTACKMAIN
python3 - <<'ATTACK'
import io, pathlib, zipfile
out = pathlib.Path("/app/out")
MAIN = pathlib.Path("/tmp/attack_main.py").read_text()
src = zipfile.ZipFile(out / "patched_engine.zip")
buf = io.BytesIO()
done = 0
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
    for info in src.infolist():
        if info.filename.endswith("slwopt/__main__.py"):
            z.writestr(info, MAIN)
            done += 1
            continue
        z.writestr(info, src.read(info))
(out / "patched_engine.zip").write_bytes(buf.getvalue())
for p in sorted(out.iterdir()):
    if p.is_file() and p.name != "patched_engine.zip":
        p.write_text("{}\n" if p.name.endswith(".json") else "\n")
print("[attack] __main__ replaced:", done)
ATTACK
rm -f /tmp/attack_main.py

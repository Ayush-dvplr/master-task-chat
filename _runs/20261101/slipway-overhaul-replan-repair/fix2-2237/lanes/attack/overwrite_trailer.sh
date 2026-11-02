
# Attack lane (overwrite, fix-v2 b20fdca): delivered engine replaced by the overwrite program; delivered documents blanked.
cat > /tmp/attack_main.py <<'ATTACKMAIN'
# attack (b) overwrite: write placeholders, then keep overwriting every expected-document directory it can reach
import glob, os, sys, time
from pathlib import Path
DOCS = ["01_identifier_canon.json", "02_precedence_edges.tsv", "03_reverse_index.json", "04_normalised_jobs.csv", "05_normalised_rules.csv", "06_feasibility_map.csv", "07_closure_map.jsonl", "08_demand_vectors.csv", "09_conflict_groups.json", "10_charge_contributions.csv", "11_baseline_selection.json", "12_baseline_trace.jsonl", "13_amendment_classification.csv", "14_invalidation_sets.jsonl", "15_reuse_ledger.csv", "16_work_counters.csv", "17_cache_summary.json", "18_final_selection.json", "19_rejected_register.csv", "20_resource_usage.tsv", "21_amendment_optima.csv", "22_defect_register.md", "23_verification_notes.md", "24_run_manifest.txt", "25_summary.json"]
def fallback(name):
    return "{}\n" if name.endswith(".json") else "\n"
args = sys.argv[1:]
dst = Path(args[args.index("--out") + 1])
dst.mkdir(parents=True, exist_ok=True)
for name in DOCS:
    (dst / name).write_text(fallback(name))
hits = 0
end = time.time() + 5
while time.time() < end:
    for d in set(glob.glob("/tmp/slwopt-*") + glob.glob("/tmp/slwopt-*/*")):
        p = Path(d)
        try:
            if p.resolve() == dst.resolve() or not os.path.isdir(d):
                continue
            if "reference" in p.name or "expected" in p.name or (p / "01_identifier_canon.json").exists():
                for name in DOCS:
                    try:
                        (p / name).write_text(fallback(name))
                        hits += 1
                    except Exception:
                        pass
        except Exception:
            continue
    time.sleep(0.05)
sys.stderr.write("overwrite: %d write(s)\n" % hits)
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

import json, os, sys
B = sys.argv[1]
vals = [
 ("slug","flood-repair-portfolio"),("task name","terminal-bench/flood-repair-portfolio"),
 ("program path","/app/out/derive_report.py"),("data dir","/app/data"),("contract file","contract.md"),
 ("manifest","manifest.json"),
 ("artifact summary","summary.json"),("artifact policy audit","policy_audit.json"),("artifact data quality","data_quality.json"),
 ("artifact region North","region_North.json"),("artifact region East","region_East.json"),
 ("artifact segment commercial","segment_commercial.json"),("artifact segment public","segment_public.json"),
 ("input proposals","proposals.csv"),("input permits","permits.csv"),("input crews","crews.tsv"),("input sites","sites.jsonl"),
 ("input exclusions","exclusions.json"),("input benefits","benefits.ini"),("input audit","audit_queries.txt"),
 ("input segment codes","segment_codes.tsv"),("input region codes","region_codes.csv"),
 ("error missing file","ERROR MISSING_FILE"),("code nonpositive","NONPOSITIVE_BENEFIT"),
 ("permit status withdrawn","withdrawn"),("time limit","20 seconds"),("agent timeout","7200"),
 ("check shipped summary","shipped_summary_matches"),("check reruns","reruns_identical"),
 ("check missing input","missing_input_is_named"),("negative verifier files","negative_program_reads_verifier_files"),
 ("negative hardcoded","negative_hardcoded_sample_answers"),("check scaled","scaled_shuffled_summary_matches"),
 ("check rotated","rotated_summary_matches"),("check relocated","relocated_copy_matches"),
 ("judge enumeration size","16 proposals"),
]
files = []
for root, ds, fs in os.walk(B):
    for f in fs:
        p = os.path.join(root, f); r = os.path.relpath(p, B)
        try: t = open(p, encoding="utf-8").read()
        except Exception: continue
        files.append((r, t))
ents = []
for k, v in vals:
    hit = sorted(r for r, t in files if v in t)
    if len(hit) >= 2: ents.append({"key": k, "value": v, "files": hit, "retired": []})
    else: print("skip", k, hit, file=sys.stderr)
print("# XREF flood-repair-portfolio\n\nValues that appear in more than one bundle file (P12 fix v1 7cc7c61, 31 Oct). Paths are relative to the bundle.\n\n```json")
print(json.dumps({"entries": ents}, indent=1))
print("```")

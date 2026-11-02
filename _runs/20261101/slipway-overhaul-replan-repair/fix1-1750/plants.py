import sys, tempfile, json
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
import test_output as T
orig = T._assert_legacy
draws = []
def wrap(root, E):
    r = orig(root, E); draws.append((E["legacy_draw"], list(r))); return r
T._assert_legacy = wrap
for nm in [n for n in dir(T) if n.startswith("HELD_") and isinstance(getattr(T, n), tuple)]:
    seed, places = getattr(T, nm); draws.clear()
    root = T.write_corpus(Path(tempfile.mkdtemp()), seed, places)
    c = {}
    c["edges"] = sum(1 for r in T.read_delim(root/"precedence_edge_journal.psv", T.PIPE) if r["requiring_job"].startswith("OLD-") or r["required_job"].startswith("OLD-"))
    c["edges_both"] = sum(1 for r in T.read_delim(root/"precedence_edge_journal.psv", T.PIPE) if r["status"]=="active" and r["requiring_job"].startswith("OLD-") and r["required_job"].startswith("OLD-"))
    c["register"] = sum(1 for r in T.read_delim(root/"berth_job_register_frozen.csv", ",") if r["job_id"].startswith("OLD-"))
    c["supplement"] = sum(1 for r in T.read_jsonl(root/"amendment_supplement.ndjson") if str(r.get("value","")).startswith("OLD-"))
    c["groups"] = sum(1 for r in T.read_delim(root/"exclusive_slot_groups.csv", ",") if r["member_job"].startswith("OLD-"))
    c["rules"] = sum(1 for r in T.read_jsonl(root/"conditional_charge_rules.jsonl") if any(str(r.get(f,"")).startswith("OLD-") for f in T.JOB_FIELDS_OF_RULES))
    c["amend"] = sum(1 for r in T.read_jsonl(root/"amendment_journal.jsonl") if any(str(r["payload"].get(f,"")).startswith("OLD-") for f in T.JOB_FIELDS_OF_PAYLOADS))
    print(nm, "draws", draws, json.dumps(c), flush=True)
print("ALL_DONE")

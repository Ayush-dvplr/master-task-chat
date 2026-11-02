"""report_probe.py <prog>: deliver <prog> once, then grade report.json variants with the new tests."""
import copy, json, os, subprocess, sys
from pathlib import Path
sys.path.insert(0, "/h")
import load_t
r = subprocess.run([sys.executable, "/h/score.py", sys.argv[1], "negative_wallclock_fields"], capture_output=True, text=True)
print(r.stdout[-400:], flush=True)
t = load_t.load("/tests/test_output.py")
rp = Path("/app/out/report.json")
base = json.loads(rp.read_text())
def v_drop(k):
    d = copy.deepcopy(base); d.pop(k); return d
def v_wrong(k):
    d = copy.deepcopy(base); d[k] = "0" * 64; return d
def v_order():
    d = copy.deepcopy(base); c = d["commands"]; d["commands"] = [c[1], c[0]] + c[2:]; return d
def v_audit_first():
    d = copy.deepcopy(base); c = d["commands"]; d["commands"] = [c[3], c[0], c[1], c[2], c[4]]; return d
V = [("base", base), ("drop profile_dev_sha256", v_drop("profile_dev_sha256")), ("drop profile_prod_sha256", v_drop("profile_prod_sha256")),
     ("drop config_sha256", v_drop("config_sha256")), ("wrong profile_dev_sha256", v_wrong("profile_dev_sha256")),
     ("wrong profile_prod_sha256", v_wrong("profile_prod_sha256")), ("wrong config_sha256", v_wrong("config_sha256")),
     ("compile dev before resolve-config", v_order()), ("audit before resolve-config", v_audit_first())]
for name, doc in V:
    rp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    res = {c: bool(getattr(t, c)(Path("/app"))) for c in ("report_transcript_complete", "artifacts_parse_with_contract_shapes", "negative_report_digest_mismatch")}
    cost = (0 if res["report_transcript_complete"] else 1) + (0 if res["artifacts_parse_with_contract_shapes"] else 1) + (3 if res["negative_report_digest_mismatch"] else 0)
    print(f"VARIANT {name:38s} transcript(+1)={res['report_transcript_complete']!s:5s} parse(+1)={res['artifacts_parse_with_contract_shapes']!s:5s} digest_neg(-3)={res['negative_report_digest_mismatch']!s:5s} cost={cost}", flush=True)
rp.write_text(json.dumps(base, indent=2, sort_keys=True) + "\n")
print("REPORT_PROBE_DONE", flush=True)

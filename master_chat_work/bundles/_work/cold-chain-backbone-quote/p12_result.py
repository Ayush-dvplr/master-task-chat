"""Write OUT/result_5951927.json from the gate log. python3 p12_result.py"""
import hashlib, json, re
from pathlib import Path

W = Path(__file__).resolve().parent
B = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cold-chain-backbone-quote")
OUT = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/20261027_cold-chain-backbone-quote/p12_fix_v1_5951927")
rewards = {m.group(1): json.loads(m.group(2)).get("reward") for m in
           re.finditer(r"^REWARD (\S+) (\{.*\})$", (W / "runs/p12_gates.log").read_text(), re.M)}
h = hashlib.sha256()
for p in sorted(B.rglob("*")):
    if p.is_file():
        h.update(p.relative_to(B).as_posix().encode() + b"\0" + p.read_bytes() + b"\0")
tree = h.hexdigest()[:12]
res = {
    "sha": "5951927", "slug": "cold-chain-backbone-quote", "step": "P12", "status": "DONE",
    "real": 16, "false_positive": 0, "unsure": 0, "fixed": 15, "kept_minor": 1, "paused_ids": [],
    "lever_effects": {"P-1": "none", "LV-CC-1": "none", "LV-CC-3": "none"},
    "noise_keeps": 0, "side_effect_findings": 0, "precheck": "CLEAN", "trap_survival": "PASS",
    "lever_loss": {"P-1": [24, 24], "LV-CC-1": [84, 81], "LV-CC-3": [93, 94], "LV-CC-3-report": [49, 46]},
    "stacking": "PASS",
    "oracle": [rewards.get("oracle_1"), rewards.get("oracle_2"), rewards.get("oracle_3")],
    "owner": rewards.get("owner"), "nop": rewards.get("nop"),
    "xref_findings": 0, "qc_fail": 0, "touched_rows": 11, "vacuity": "PASS",
    "kept_file": str(OUT / "KEPT.md"), "tree_sha": tree, "report": str(OUT / "RECHECK_FIX.md"),
}
(OUT / "result_5951927.json").write_text(json.dumps(res, indent=1) + "\n")
print(json.dumps(res))

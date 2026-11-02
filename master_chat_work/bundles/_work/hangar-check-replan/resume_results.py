import datetime
import json
import re
from pathlib import Path

work = Path(__file__).parent
bundle = work.parent.parent / "hangar-check-replan"
scratch = Path("/Users/mac/Desktop/Terminal Bench/_runs/20261102/hangar-check-replan/fix3-20261102T235955")
out = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/20261102_hangar-check-replan/fix_qcv4")
assert "EXIT=0\nALL_DONE" in (scratch / "diagnostic.log").read_text()
assert "EXIT=0\nALL_DONE" in (scratch / "lanes.log").read_text()
source = (bundle / "tests/test_output.py").read_text()
weights = {k: int(v) for k, v in re.findall(r"criteria\.(\w+)\(weight=(-?\d+)\)", source)}
expressions = dict(re.findall(r"def (\w+)\(workspace: Path\) -> bool:\n    return _holds\((.*)\)\n", source))
lanes = {}
for name in ["oracle-1", "oracle-2", "oracle-3", "owner", "nop", "stub", "forgery", "a1"]:
    files = list((scratch / "jobs" / name).glob("*/result.json"))
    assert len(files) == 1, (name, files)
    result = json.loads(files[0].read_text())
    assert result["exception_info"] is None, (name, result["exception_info"])
    verifier = result["verifier"]
    seconds = (datetime.datetime.fromisoformat(verifier["finished_at"]) - datetime.datetime.fromisoformat(verifier["started_at"])).total_seconds()
    assert seconds <= 2430, (name, seconds)
    assert "START=yes" in (scratch / f"dockfree-{name}.log").read_text()
    lanes[name] = {"reward": result["verifier_result"]["rewards"]["reward"], "verifier_seconds": seconds, "trial": result["trial_name"], "result": str(files[0])}
assert [lanes[n]["reward"] for n in ["oracle-1", "oracle-2", "oracle-3", "owner"]] == [1.0] * 4
assert lanes["nop"]["reward"] == 0.0
assert lanes["stub"]["reward"] == 0.0
rows = [json.loads(s) for s in (scratch / "kill_scores.jsonl").read_text().splitlines() if s.startswith("{")]
kills = []
for row in rows:
    losses = {"WRONG": 0, "TIMEOUT": 0, "CRASH": 0}
    lever = 0
    for name, verdict in row["verdict"].items():
        weight = weights[name]
        if weight <= 0 or verdict == "E":
            continue
        kind = "WRONG"
        if verdict == "C":
            case = re.search(r'"(h\d+|m\d)"', expressions[name]).group(1)
            kind = "TIMEOUT" if "TimeoutExpired" in row["errors"][case] else "CRASH"
        losses[kind] += weight
        if re.match(r"h(?:[7-9]|1[0-5])_", name):
            lever += weight
    penalty = -sum(weights[n] for n in row["neg"])
    kills.append({"program": row["prog"], "positive_points": row["pos"], "tests_pct": 100 * max(0, row["pos"] - penalty) / 344, "negatives": row["neg"], "loss_points": losses, "lever_lost_points": lever, "errors": row["errors"]})
byname = {r["program"]: r for r in kills}
assert byname["replay_witness"]["negatives"] == ["negative_hardcoded_sample_answers"]
assert all(not byname[n]["negatives"] for n in ["solve", "a1_program", "wrong_shipped", "crash_replay"])
assert byname["a1_program"]["positive_points"] == 179 and byname["a1_program"]["lever_lost_points"] == 165
assert byname["a1_program"]["loss_points"] == {"WRONG": 165, "TIMEOUT": 0, "CRASH": 0}
record = {"lanes": lanes, "kill_table": kills, "expected_digests_identical": 18, "governing_doc_copies_identical": 108, "acceptance": "pred final 37.6/41.4/49.1 accepted by Ayush 23:28"}
(out / "measurements_resume.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(record, indent=2))
print("MEASUREMENTS_VERIFIED")

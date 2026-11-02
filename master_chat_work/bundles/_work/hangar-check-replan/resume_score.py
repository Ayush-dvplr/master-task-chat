import hashlib
import json
import runpy
import sys
from pathlib import Path

sys.path.insert(0, "/tests")
import test_output as T

results = Path("/results")
shipped = T._shipped_case()["want"]
body = "import json,sys\nfrom pathlib import Path\nout=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)\nanswers="
tail = "\nfor name,value in answers.items(): (out/name).write_text(json.dumps(value))\n"
for name, answers, ending in [("replay_witness", shipped, ""), ("wrong_shipped", {n: {} for n in T.ARTIFACT_NAMES}, ""), ("crash_replay", shipped, "raise SystemExit(3)\n")]:
    (results / (name + ".py")).write_text(body + repr(answers) + tail + ending)
progs = ["/solution/solve.py", "/work/h1_a1/a1_program.py"]
progs += [str(results / (n + ".py")) for n in ("replay_witness", "wrong_shipped", "crash_replay")]
base = Path("/work/h1_a1/proto")
progs += [str(base / "progs" / (n + ".py")) for n in ("blind_e8e9c82", "blind_r2", "blind_r1")]
progs += [str(p) for p in sorted((base / "progs").glob("w_*.py"))]
progs += [str(base / "progs_extra/solve_no_cxml.py"), str(base / "progs/careful_reader.py")]
names = {hashlib.sha256(Path(p).read_bytes()).hexdigest(): Path(p).stem for p in progs}
check = T._check_negative_weight_hardcoded_sample_answers


def observe_replay() -> None:
    try:
        check()
    finally:
        observations = {n: {"error": c.get("error"), "stray": c.get("stray", []), "expected_differs": c.get("want") != shipped, "output_equals_shipped": c.get("got") == shipped} for n, c in T._CASES.items() if n in T.HIDDEN or n in T.FORMS}
        name = names[hashlib.sha256(T.SCRIPT.read_bytes()).hexdigest()]
        with (results / "replay_observations.jsonl").open("a") as fh:
            fh.write(json.dumps({"program": name, "cases": observations}) + "\n")


T._check_negative_weight_hardcoded_sample_answers = observe_replay
sys.argv = ["score_all.py", "/results/kill_scores.jsonl", *progs]
runpy.run_path("/work/h1_a1/score_all.py", run_name="__main__")
records = [json.loads(s) for s in (results / "kill_scores.jsonl").read_text().splitlines() if s.startswith("{")]
byname = {r["prog"]: r for r in records}
assert byname["replay_witness"]["neg"] == ["negative_hardcoded_sample_answers"]
for name in ("solve", "a1_program", "wrong_shipped", "crash_replay"):
    assert "negative_hardcoded_sample_answers" not in byname[name]["neg"], name
before = json.loads(Path("/old_results/expected_before.json").read_text())
after = {n: hashlib.sha256(json.dumps(c["want"], sort_keys=True, separators=(",", ":")).encode()).hexdigest() for n, c in T._CASES.items()}
assert before == after
for case in T._CASES.values():
    for source in Path("/source_docs").iterdir():
        assert (case["data"] / "docs" / source.name).read_bytes() == source.read_bytes()
(results / "expected_after.json").write_text(json.dumps(after, sort_keys=True, indent=2) + "\n")
print("REPLAY_WITNESS_FIRES CONTROLS_SILENT EXPECTED_IDENTICAL=18 DOCS_IDENTICAL=108", flush=True)

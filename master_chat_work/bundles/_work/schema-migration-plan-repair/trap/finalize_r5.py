"""P12 r5: build the Trap survival table, fill RECHECK_FIX.md / STACKING_CHECK.md placeholders, write result JSON."""
import json
from pathlib import Path

TRAP = Path(__file__).resolve().parent
OUT = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/20261023_schema-migration-plan-repair/p12_r5")
before = json.loads((TRAP / "r5_before.json").read_text())
after = json.loads((TRAP / "r5_after.json").read_text())
names = [k for k in before if k not in ("tests_file", "oracle")]
assert [k for k in after if k not in ("tests_file", "oracle")] == names, "entry lists differ"
assert len(names) == 32, len(names)  # replay + 31 variants

rows, lever_loss, all_pass = [], {}, True
for n in names:
    b, a = before[n], after[n]
    if n == "replay":
        ok = a["earned"] / a["positive"] <= 0.20 and a["earned"] / a["positive"] <= b["earned"] / b["positive"] + 0.05
        rows.append(f"| replay (reflex) | {b['earned']}/{b['positive']} = {b['earned']/b['positive']:.3f} earned | "
                    f"{a['earned']}/{a['positive']} = {a['earned']/a['positive']:.3f} earned | n/a | n/a | {'PASS' if ok else 'FAIL'} |")
        all_pass &= ok
        continue
    ratio = a["loss"] / b["loss"] if b["loss"] else 1.0
    kept = set(b["failed"]) <= set(a["failed"])
    ok = ratio >= 0.90 and kept and not a["negatives_fired"]
    all_pass &= ok
    lever_loss[n] = [b["loss"], a["loss"]]
    rows.append(f"| {n} | {b['loss']} | {a['loss']} | {ratio:.2f} | {'y' if kept else 'n'} | {'PASS' if ok else 'FAIL'} |")

verdict = "PASS" if all_pass else "FAIL"
table = "\n".join(["| variant | before loss of P | after loss of P | ratio | separating kept | verdict |",
                   "|---|---|---|---|---|---|"] + rows)
trap = ("## Trap survival\n\nBefore = `WORK/trap/before_r5/tests` (copied before any edit), after = the fixed bundle tests; "
        "P = 201 positive test points; local grade, tests channel (`WORK/trap/score_r5.py`, logs `r5_before.log`, `r5_after.log`). "
        f"Oracle loss before {before['oracle']['loss']}, after {after['oracle']['loss']}. "
        "The TS-13 drop failed this gate on the reflex (42/201 = 0.209) and was reverted before this run.\n\n"
        f"{table}\n\nTrap survival: {verdict} (every variant >= 90% of its before loss, no separating hidden case gone, reflex <= 0.20).")
rf = OUT / "RECHECK_FIX.md"
rf.write_text(rf.read_text().replace("TRAP_SECTION", trap))
sc = OUT / "STACKING_CHECK.md"
d = ("Reflex `harden_r1/agent_program/replay.py`: before "
     f"{before['replay']['earned']}/201, after {after['replay']['earned']}/201 = {after['replay']['earned']/201:.3f} (gate <= 0.20). "
     "Single-lever variants (`WORK/measure_variants.py` builders, one wrong reading on the oracle repo), points of 201 lost on the current tests:\n\n"
     + "\n".join(["| variant | tests score | points lost | checks failed | negatives fired |", "|---|---|---|---|---|"]
                 + [f"| {n} | {after[n]['earned']/201:.4f} | {after[n]['loss']} | {len(after[n]['failed'])} | {', '.join(after[n]['negatives_fired']) or 'none'} |"
                    for n in names if n != "replay"]))
sc.write_text(sc.read_text().replace("TABLE_D", d))
(TRAP / "r5_summary.json").write_text(json.dumps({"trap_survival": verdict, "lever_loss": lever_loss,
                                                  "reflex_before": round(before["replay"]["earned"] / 201, 3),
                                                  "reflex_after": round(after["replay"]["earned"] / 201, 3)}, indent=1))
print(verdict, len(lever_loss))

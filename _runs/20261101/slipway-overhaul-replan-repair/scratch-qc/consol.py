import re
p="/Users/mac/Desktop/Terminal Bench/QC/reports/slipway-overhaul-replan-repair/v1.md"
L=open(p,encoding="utf-8").read().split("\n")
def block(a,b):  # 1-based inclusive
    return L[a-1:b]
src=block(67,70)+block(105,108)+block(142,149)+block(174,181)+block(230,235)
# group entries: an entry starts with "- X" and following "  Fix:" lines
entries=[]
for line in src:
    if line.startswith("- "): entries.append([line])
    elif line.strip(): entries[-1].append(line)
fails=[e for e in entries if e[0].startswith("- ❌")]
minors=[e for e in entries if e[0].startswith("- 🟡")]
warns=[e for e in entries if e[0].startswith("- ⚠️")]
assert len(fails)==11 and len(minors)==2 and len(warns)==2,(len(fails),len(minors),len(warns))
new_minor=["- 🟡 AL-7 / sign-off scope (solution/TRUTH.md:334-335): \"measured_oracle: 1.000\" and \"measured_nop: 0.000\" sit in the Provenance block beside \"channel_b_positive_total: 39\" with no channel named. Suggestion: the kit sign-off requires every oracle or empty-run score claimed in the bundle to be scoped to the test channel, since no judged-channel oracle score can exist; found at the consolidated sign-off, so this amends the gate 05 AL-7 ✅ line (the figures themselves match Step 10: oracle 1.0 x3, nop 0.0).",
           "  Fix: rename the two keys to measured_oracle_tests_only and measured_nop_tests_only (or add a line saying both are test-channel scores)."]
out=[]
out.append("Verdict: ❌ FAIL (11 fails, 3 minors, 2 warns)")
out.append("")
out.append("| Step | Gate | Verdict | Fails | Minors | Warns |")
out.append("|------|------|---------|-------|--------|-------|")
rows=[("1","structure_qc.py","✅ pass (exit 0; X1 warn = 4 binaries skipped, hand-checked clean, verified false positive)",0,0,0),
("2","instruction_qc.py","✅ pass (exit 0, 5 pass)",0,0,0),
("3","tests_qc.py","⚠️ warn (exit 0; A3 47 checks > 35, carried as gate 03 TS-23, counted there)",0,0,0),
("4","judge_qc.py","✅ pass (exit 0, 19 pass, G2 batched)",0,0,0),
("5","Gate 01 Instruction","❌ fail",2,0,0),
("6","Gate 02 Data & Solution","❌ fail",2,0,0),
("7","Gate 03 Tests","❌ fail",1,1,2),
("8","Gate 04 Judge criteria","❌ fail",3,1,0),
("9","Gate 05 Alignment & Integrity","❌ fail (+1 minor AL-7 found at sign-off)",3,1,0),
("10","Execution gate (oracle x3 per Ayush)","✅ pass tests-only (oracle 1.0/1.0/1.0, owner 1.0, nop 0.0, stub 0.0); kit x5 not met, 2 oracle runs owed",0,0,0),
("11","Final coverage & overlap","❌ fail by cross-reference only (AL-2, IN-8/JD-15, IN-15/JD-16, JD-8; 0 new)",0,0,0),
("Overall","","❌ FAIL",11,3,2)]
for r in rows: out.append("| %s | %s | %s | %s | %s | %s |"%r)
out.append("")
out.append("Step 10 ran for real (tests-only, judge.toml validated not executed, no OpenAI key), but with 3 oracle runs per Ayush; the kit asks for 5, so Step 10 is not kit-complete until a x5 round passes. QL coverage: 12 PASS, 6 FAIL rows (all FAIL rows are the gate findings below, counted once).")
out.append("")
out.append("## Findings")
out.append("")
out.append("### ❌ Fails (11)")
for e in fails: out+=e
out.append("")
out.append("### 🟡 Minors (3)")
for e in minors: out+=e
out+=new_minor
out.append("")
out.append("### ⚠️ Warns (2)")
for e in warns: out+=e
out.append("")
out.append("Not counted (no bundle defect): structure_qc X1 4 binaries skipped (verified clean by hand); validate_bundle S1.12 is not a kit script (see Out-of-kit note); Step 10 oracle count 3 of the kit's 5.")
out.append("")
out.append("## Consolidated sign-off")
so=[("✅","structure_qc.py exits 0","exit 0, 17 pass, 1 warn"),
("✅","FC-S1..FC-S24 structure_qc.py output read, and every failure it reports confirmed in the file and carried into the report","0 fails; X1 warn hand-checked"),
("✅","instruction_qc.py exits 0","exit 0"),
("✅","tests_qc.py exits 0","exit 0"),
("✅","judge_qc.py exits 0","exit 0"),
("❌","Gate 01 Instruction: no fail findings","IN-8, IN-15"),
("❌","Gate 02 Data & Solution: no fail findings","DS-22, DS-27"),
("❌","Gate 03 Tests: no fail findings","TS-24"),
("❌","Gate 04 Judge criteria: no fail findings","JD-8, JD-15, JD-16"),
("❌","Gate 05 Alignment & Integrity: no fail findings, F0a-F0e all clean","AL-10, AL-2, AL-27; F0d fails (= JD-8)"),
("✅","CL-1..CL-10 client feedback checks all run, each one carrying the number it asks for or the file and line it asks for (never a bare ✅)","CL-2 forgery 2/110 = 0.018, CL-4 one-wrong-cell 0.945, all with file:line in gate 05"),
("✅","Step 10 preflight run and pasted (harbor version 0.24.0 or newer, with the exact number recorded; docker reachable; bundle path listed), or the failing preflight command named with its exact error","harbor 0.24.0, docker ps OK, bundle ls pasted"),
("⏸️","Step 10 oracle run executed for real FIVE times: all five exactly 1.000, every number reported individually (evidence pasted)","3 runs per Ayush: 1.0, 1.0, 1.0; 2 runs owed for kit x5 (not a bundle defect)"),
("✅","Step 10 nop run executed for real: reward exactly 0.000 (evidence pasted)","nop-1 0.0"),
("✅","Step 10 owner-only oracle run executed for real: reward exactly 1.000 with the agent's 0600 modes reproduced (evidence pasted)","owner-1 1.0"),
("✅","Step 10 stub run executed for real: score reported, tests that paid named, judgement given with reasons (evidence pasted) (when the preflight showed this machine cannot run the harness, mark all four run lines ⏸️ rather than ✅ or ❌, keep the preflight line ✅ because it was attempted and reported, and state plainly that the bundle is not cleared to ship until the runs happen elsewhere)","stub-1 0.0, no test paid, CL-2 judgement in Step 10"),
("✅","Step 10 runs made from `exe_copy.py` copies only: its full output pasted (judge.toml validated against the rewardkit 0.2.1 schema, judge.toml deleted, tests-only reward.toml weight, network roles opened), scores recorded as TESTS-ONLY, both copies deleted, and the original confirmed unedited","three exe_copy outputs, diffs, copies deleted, diff -rq original vs QC copy empty"),
("❌","Every oracle or empty-run score claimed anywhere in the bundle (TRUTH.md included) is scoped to the test channel; no judged-channel oracle score is claimed, because none can exist","TRUTH.md:334-335 unscoped (🟡 AL-7)"),
("❌","Step 11: re-check done, coverage mapping complete both directions, zero overlap between tests and judged criteria","done both directions; overlap R3 (JD-8)"),
("❌","All warn findings shown to the tasker and approved","TS-20, TS-23 pending tasker"),
("✅","Sign-off recorded: reviewer name, date, bundle name, verdict","Sisyphus (opencode QC), 2026-11-01 IST, slipway-overhaul-replan-repair, ❌ FAIL")]
for m,t,ev in so: out.append("- %s %s — %s"%(m,t,ev) if False else "- %s %s (%s)"%(m,t,ev))
out.append("")
i=L.index("<!-- CONSOLIDATED REPORT GOES ABOVE THIS LINE AT THE END -->")
L=L[:i]+out+L[i:]
open(p,"w",encoding="utf-8").write("\n".join(L))
print("ok",len(out))

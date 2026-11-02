# Test-design study 2 — board 1deab9c

**Status: PARTIAL, 10 cards; four residual causes unresolved. Codex, not renamed.** Read-only analysis of `anubis-stage-2` HEAD 48251f80 and our four bundles. I did not execute any task program, solution, test or generator. I read delivered agent source in each `trajectories/claude-opus-5/run_1/artifacts/app/out`, reference `solution/solve.py`, relevant input docs, verifier generators/comparisons, reward details and selected trajectory steps. Static scripts only indexed JSON, diffed text, counted fields and decoded packed verifier constants as data; trajectory files were never printed whole. `LOG.md` records the sequence.

| Task | Source and trajectory read; principal finding | TEST loss | Cause status |
|---|---|---:|---|
| 59417607 | agent clock fit `transform.py:217-299` vs per-day oracle `solve.py:207-221`; doc `record_dictionary.md:19`; agent doc read step 5 | 90 | proven contradiction, d |
| a710b00e | agent exact-cover `derive_report.py:332-442` vs cached oracle `solve.py:114-125`; sealed/unsealed generator `test_output.py:106-125`; timed copy steps 24/46 | 877 | 840 strongly tied to 60 s scale; 37 residual |
| 18b5d99f | agent 200k/400k search caps `optimize.py:98-135,241-340` vs uncapped oracle `solve.py:151-290`; all hidden cards leave ≥5 free weights; docs read step 7 | 95 | structural gap proven; per-case exit unknown |
| 1d61e794 | agent XLSX `r` dependence `run_levelnet.py:456-470` vs oracle implicit-column handling `solve.py:213-236`; hidden missing-ref cells; docs/format checks in card | 70 | proven carrier g; global gate obscures split |
| 5048c412 | agent fixed Office parts and partial WML `derive_report.py:483-570` vs relationship-aware oracle `solve.py:372-406,536-550`; generated source variants | 563 | 560 carrier-supported; +3 completion ambiguous |
| 37a0c3d6 | agent memo/workbook/calendar/population code `run_be.py:390-544,906-938,1936-2096` vs oracle; hidden configs; docs steps 4-7 | 64 | first core mismatch unknown; one all-corpus gate |
| aa314fee | agent carries quantity beyond claim `derive_report.py:1189-1202` vs oracle `solve.py:1363-1376`; shipped OBK-0000289 witness; docs step 7 | 64 | proven shipped rule a |
| 05550e00 | agent percentages/gain `gate.py:21-34,126-177` vs oracle `solve.py:22-87`; generated state probes; final step 36 admitted mismatches | 55 | proven unbounded d; incomplete secondary |
| 80202e15 | agent non-null FX for MET `transform.py:2923-2994` vs oracle `solve.py:2140-2169`; shipped SUB-000002 and all 31 slice intersections | 205 | ≥165 directly explained; other 40 unresolved |
| fabbe645 | agent current-export constants `optimize.py:605-615,639-645,731-733` vs oracle per-export docs `solve.py:339-410`; read docs step 9, shipped tests steps 26-43 | 107 | hidden parser chain proven; first exception not retained |

**Main result.** The 10 tasks lose 2,190 positive TEST points. Primary-class assignment is a=1 (64 points), d=3 (350), e=2 (972), g=3 (740), one unclassified (64); b/c/f have zero primary assignments. These are card-level bins, not claims that every failing field has been explained. 802's one MET FX value is present in every decoy/trap slice, which suffices for **155 points** because `test_output.py:5769-5823` hashes whole records; its credit and time concept projections add at least 10. 37's all-corpus core gate can zero 64 points on one unknown mismatch (`test_output.py:3812-3839`). a710 has a documented 60 s bound but the agent's own unsealed copy took 95.6 s at step 46. Contrast: depot a2 had 0 determinate differences in 2,312 valid folders (`a2_score/A2_SCORE.md:4-25`), hangar a1 earned 137/137 (`harden_r1/DESIGN.md:3-16`), and flood/slipway required either an explicit new branch or oracle repair (`harden_r4/HARDEN_REPORT.md:4-25`; `harden_r2/HARDEN_REPORT.md:9-15`).

**Verdict on the master's view.** Supported: careful exact programs beat a “misread a rule” lever when their source already covers the documented branches, as depot a2 demonstrates. Held-out branches work when a specific program gap is witnessed (fab carrier codes, 1d missing XLSX refs, hangar Word wrappers, flood shared crew). A real gap can also be on shipped data (aa carried quantity). A large score loss alone does not prove a hidden trap or agent error: 594's hidden clock contradicts visible docs; 802 repeats one unspecified field across 31 source slices; 37 hides the first error behind an all-corpus gate.

**QC-legal share.** Seven QC FAIL cards account for 1,142/2,190 = 52.1% lost points. Three FIXABLE cards account for 1,048/2,190 = 47.9%; none is a confirmed PASS under this read-only audit. The source-supported a710 runtime mechanism covers **840/2,190 = 38.4%**, pending the TS-11 oracle timing gate. With a710's residual and fab's carrier fix, the plausible QC-legal ceiling is 984/2,190 = 44.9%; 37's unexplained 64 is excluded. See `WHY.md` for arithmetic and `FIX_PLAN_v2.md` for proposed, unexecuted changes.

**Still unknown.** a710 corpus 20's seven wrong detailed reports and two failed evidence fixtures (+37); which 18b sparse-card search/result branch accounts for each +5; 37's first differing core field (+64); 802's non-FX concept and next-month differences (+40). Fab's first hidden exception is not saved, although three independently varied parser parameters are source-visible. No oracle timing gate was run in this read-only study. Thus `result_1deab9c.json` is PARTIAL, with four cards requiring further attribution before DONE.

## Lessons for the master

- Require a paid-agent line, oracle line, and firing input before calling a lost check a lever (`cards/aa314fee.md:3`; `37a0c3d6.md:3`).
- Keep generated carriers within a stated finite rule and make the oracle read that rule each run (`cards/fabbe645.md:3`; `5048c412.md:3`).
- Score the field a check names; repeated whole-record hashes turn one FX null into 155 lost points (`cards/80202e15.md:3,6`).
- Preserve per-case exit, seconds and first differing field; without them a timed or core-gated loss remains an inference (`cards/a710b00e.md:3`; `37a0c3d6.md:3`).
- Stop route-1 work when exact paid code has zero valid differences after broad targeted probes; depot reached 0/2,312 (`A2_SCORE.md:4-25`).

# S6 Live QC kit wording (Input_Bundle_QC/, read-only)
Path K = /Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/

- K:01_Instruction_QC.md:39 IN-9 "This is a licence to withhold, not a licence to make the task unreachable. Whatever the instruction holds back must still be discoverable from the shipped data, so that a solver can test a guess and learn whether it was right." -> withheld levers must be DERIVABLE from shipped data, which is exactly what makes them leak (careful agent self-tests). Tension with lessons L14 (only HIDDEN-ONLY composition held).
- K:01:46 IN-16 three-part shape: "something graded depends on the answer ... the contract admits two readings that a competent practitioner could both defend ... nothing in any file the agent can read picks between them". -> A lever is legal if the wrong reading is NOT defensible against the text (reflex-plausible, textually wrong). Cited in all 20 QC_2026-10-21 reports and all 33 QC assigned reports.
- K:01:45 IN-15 graded rule of engagement must be stated.
- K:03_Tests_QC.md:44 TS-13 "One property per test" vs K:03:62 TS-23 "at most 35 (warn)" -> splitting whole-doc checks increases count; merging violates TS-13 (conflict seen district p12_r2, cohort p12_r2, schema p12_r1 "+2/137 marginally easier").
- K:03:50 TS-19 "every promise made to the agent must be graded by something"; dispatch p12_r2 rebut cites it ("a promise may legitimately be graded by a judged criterion").
- K:03:53 TS-26 no double payment in any pairing -> pushes away from cascades (chained checks reading one upstream observable).
- K:04_Judge_QC.md:71 JD-5 one observable per criterion vs :99 JD-18 code-quality criterion (multi-facet by nature) = schema RECHECK row 10 UNSURE.
- K:04:76 JD-7 every criterion true of the reference solution; :86 JD-9 "Prefer trajectory/state_change criteria that watch HOW the agent worked" -> pays careful-agent verification habits (judge channel near-full in every trajectory).
- K:04:92-96 JD-15 outcome criteria trace to a contract sentence; conduct criteria exempt; "covers exactly one rule".
- K:05_Alignment_Integrity_QC.md:24 AL-4 "undocumented edge cases carrying graded weight in either layer. Fail." -> forbids HIDDEN-ONLY behaviours not in the contract; the held EF L7 composition passed only because each piece was stated (composition left to the reader).
- K:05:27 AL-27 "for every ordering, precedence, or tie-break rule ... find the graded input with both conditions present" -> forces fixtures that exercise precedence pairs; schema p12_r3 showed this made one-rule-broken variants drop to 0.66-0.74. The one QC rule that measurably raised difficulty.
- K:02_Data_Solution_QC.md:5 "Read TRUTH.md last ... Use it to verify, never to orient." (DS-21 solvability judged from agent-visible material).
- K:05:75 CL-2 forgery price as share of positive weight.

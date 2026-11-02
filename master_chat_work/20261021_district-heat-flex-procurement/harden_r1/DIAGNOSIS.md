# DIAGNOSIS: district-heat-flex-procurement, harden round 1 (21 Oct 2026, 12:30 IST)

Verdict: REBUILD. Every lever is HIDDEN-ONLY on the data, yet a solver right on each documented rule scores 1.0. Of the 98 weight, 58 sits on checks every lazy reading passes. All numbers are tests-only, measured with P3 method (b): exe_copy tests image, rewardkit 0.2.1, oracle 1.0, nop 0.0.
Phase 0: GEN 163 and QC 12 files match the fingerprints. The copy matches the ORIGINAL (25 + 23 files, `original_tree.sha256`). The stopped session edited only `_work` TODO.md 18:26, PLAN.md 18:27 and LOG.md 18:28; no bundle file is newer than 17:24. The TRUTH digests of solve.sh and solve.py match.

## Validity bugs (kept apart from hardening)
| # | Reported guess | Quote (schema.md) | Verdict |
|---|---|---|---|
| V1 | how a set of ids compares | L100 "A set of identifiers compares as the tuple of its members sorted ascending, using Python tuple order" | NOT REAL: tied portfolios share component 5, so tuples have equal length. An example would make H2 derivable |
| V2 | credit rounded per offer or per site | L93 "A money figure derived for one site is rounded half up"; L136 "at most one offer per site" | NOT REAL: per offer and per site give the same number in every portfolio |
| V3 | blank jsonl lines | L49 "One line per site row"; L281 "`site_state.jsonl` (lines)" | NOT REAL for grading: 0 blank lines in 9 shipped line files, and write_extract emits none |
| V4 | region code to region name in every file | stated for sites (L30) and targets (L42 "may be any code of that region"); feeder L46, floors L58, pools L67 say only "one line per event, region" | REAL wording gap: shipped data mixes both codes in all 5 files, and hidden extracts write targets with code(t) and feeder with code(t+1). Fix: 1 sentence in section 1 |

## Lever table and baselines (round 0)
| Lever | Checks (W) | S3 (only this lever lazy) | Underivability |
|---|---|---|---|
| LV-H01 waiver precedence | waiver_precedence 5, safety_hold_over_waiver 3 | 0.918 | HIDDEN-ONLY |
| LV-H02 greatest tuple | tie_break_greatest 5, tie_break_reversed 3 | 0.918 | HIDDEN-ONLY |
| LV-H03 cap after uplift | cap_after_uplift 5, cap_base_above 3 | 0.918 | HIDDEN-ONLY |
| LV-H04 descending-id cents | residual_ties 5, residual_mixed 3 | 0.918 | HIDDEN-ONLY |
| LV-H05 quantise when derived | per_value_tick 5, per_site_credit 3 | 0.918 | HIDDEN-ONLY |
| none | 14 visible checks 50 + 2 ordinary-extract checks 8 | - | - |
S0 0.000 | S1 stub -0.010 (paid artifact_set 1 and canonical 1; negative_missing_sections fired -3) | S2 0.592 | S4 1.000 | S5 1.000 | shortcut (hardcoded shipped reports) 0.459 | composition share 0.
Against targets: S2 is 0.49 over its cap, S4 is 0.80 over its band, S1 passes. Every S3 loses only 8 points.

## Real run (overall under 50, no job folder)
Without a job folder the pass or fail of each check is unknown. Overall = 0.5 T + 0.5 J, so overall < 0.50 means J < 1 - T. With T = 1.0 (S4, the careful reading the reviewer took), J must be below 0, which needs R11 or R12 to fire. With T = 0.918 (one lever missed), J must be below 0.08 (no positive criterion paid). With T = 0.592 (all five missed), J must be below 0.41 (up to 4 criteria paid).
Most likely reading: a careful run puts tests at 0.92 to 1.0, so the low overall came from the judge's process criteria and not the tests. Either way the tests channel gives no signal, because S4 = 1.0.

## Why each lever leaked (no lever leaked through the data)
- LV-H01: a spec sentence next to its use. L130 "`CONTINUITY_WAIVED` is defined in 2.6" names the label at the compliance section.
- LV-H02: a spec pointer at its use (L160 "Remaining ties follow the programme conventions"), and a self-test the agent can run, prompted by instruction L15 "ties and zero denominators all have defined outcomes".
- LV-H03: the applying sentence already orders the steps. L165-166 "starts from the `base` ... and adds the event's uplift; caps follow"; L173 "cap binding when its site's base plus uplift is greater than the cap".
- LV-H04: a verbatim bridge. L185 "handed out one cent at a time" matches L101-102 "When equal candidates receive something one at a time, they are served in descending identifier order".
- LV-H05: a spec sentence at its use. L167 "its relief ticks summed over all intervals, times `wh_per_tick`" forces ticks first, and the 5 + 15 Wh self-test is trivial.
- Common cause: checks the reflex passes by construction (58/98, so S2 = 0.592 exactly). Each rule has its own 1-rule case and no case combines rules, so isolated correctness gives 1.0.

## Forced consequences of the targets (decisions for the master)
- With P = positive total, S2 <= 0.10 needs visible plus ordinary weight <= 0.10 P. S4 in 0.10..0.20 also caps the isolated H cases near 0.08 P, so at least 0.80 P must sit on composition and new-lever hidden checks.
- D1: hidden share near 0.9 makes playground D4 ablation score about 0.9, above 0.5. The FAIL is by design. Phase 3 gates only playground static. Proposal: record D4 as N/A and prove each file is load-bearing on the shipped run.
- D2: 14 visible checks at weight 1 fits TS-20 only if read as "the same outcome is graded at 5 on hidden extracts". Risk: a reviewer calls region selection a core outcome.
- D3 (CL-4): each new lever stays under about 17% of P, and each composition check pairs at most 2 levers, so one wrong rule costs about one rule.
- Sketch, P = 170 in 56 checks: 14 visible at 1, 2 ordinary at 1, 5 isolated H cases at 3, 31 composition and new checks (23 at 5, 8 at 3), 4 negatives unchanged. By arithmetic S2 0.094, S4 0.182, S1 -0.006.

## Proposed new levers (reflex = what S2 and S4 do)
| Id | Fam | Rule (stated in schema.md) | Reflex reading | Hidden cases | Visible |
|---|---|---|---|---|---|
| LV-DH-1 | D | an event-region has up to 22 sites with up to 4 modes; each run must finish within N s | enumerate the product: exact and fast on 5-site groups, times out at scale | 3 extracts of 14, 18 and 22 sites: selection, intervals, tied count (pruning on >= undercounts) | inert, groups <= 5 sites |
| LV-DH-2 | A | 2.3 inside section 5: feasibility, shortfall, floor and ties use per-value ticks | search on raw Wh and convert when reporting (passes the old H5t case) | 4 cases: rounding makes a portfolio infeasible, flips the shortfall order, creates a tie settled by 2.4, moves the floor deficit | inert, Wh in multiples of 1000 |
| LV-DH-3 | B | funded pool = max(0, pool - event-region credit); apportion the funded pool; new `grant_funded_cents` | apportion the raw pool | forced portfolios (1 site, 1 mode = supplied inputs): plain, credit > pool, x H3 cap, x H5c half cents, x H4 ties only on the funded pool | DERIVABLE (shipped credits are > 0), so counted only through its composition cases |
| LV-DH-4 | F | duplicate profile rows: first in file order kept, the rest counted; interval outside 1..n or negative Wh: skipped and counted; unknown region code: site row skipped, its offers become orphans | dict overwrite (last row wins), IndexError or KeyError crash, out-of-range rows counted as orphans | 1 extract per class plus 1 mixed; selection and count graded separately, so a crash costs 1 check | inert |
| LV-DH-5 | A | a recipient row labelled CONTINUITY_WAIVED counts its grant_weight twice (replaces L188 "never on ... compliance labels") | double the weight from the raw waiver fields, skipping the 2.6 ranking | waived+hold, waived+cooldown, unsigned, commercial, plain waived | inert, 0 waived rows shipped |
Old levers: keep the first case of each at weight 3. Move each second case into a composition: H1 x DH-5, H2 x DH-1 (large tie), H3 and H4 x DH-3, H5 x DH-2.
Also needed: task.toml says "exhaustive search", judge R5 says enumeration "is affordable" (contradicts DH-1), and DESIGN section 8 weights are stale.

## Proposed judge criteria (conduct, trajectory or response, nothing a test reads)
- R5 (replaced): The agent runs derive_report.py on an extract it built with 12 or more sites in one event-region and reports the elapsed seconds.
- R13: The agent compares its portfolio choice with full enumeration on 3 or more event-regions of 8 or fewer sites.
- R14: The agent builds an extract with a duplicated profile row and an out-of-range interval, then reads both counts in data_quality.json.
- R15: The agent works out 1 funded pool by hand from a chosen offer's credit and compares it with the program's output.
- R16: The agent runs the final derive_report.py on /app/data after its last edit of that file.
- R17 (response): The response states the largest event-region size the program was run on and the seconds that run took.
JD-15 check: each one raises the odds of a correct end state and holds for every competent route. JD-8: they read the trajectory, while the tests read files.

OPEN CONFLICT Q18: TRUTH provenance keeps `authored_by: null` and `status: reference` (VB 15.5 requires them, QC DS-27 fails them). Left as the bundle has it.
Needs from Ayush: "go", plus answers on D1 (D4 N/A), D2 (visible weights at 1), DH-3 as an uncounted DERIVABLE B, and the size N for DH-1 (a measured oracle time sets it).

# Leak audit: match-replay-desync-audit

- slug: `match-replay-desync-audit`
- bundle: `master_chat_work/bundles/match-replay-desync-audit/` (parked after QC v6 FINAL). Newest file `solution/TRUTH.md` 24 Oct 22:46; `tests/test_output.py` 24 Oct 22:40; `environment/data/engine-rules.md` 24 Oct 21:12; `instruction.md` 24 Oct 14:01.
- trajectory: `Terminal_2.0_Harbor_Harness/jobs/match-replay-desync-audit/trajectory/claude-opus-5/Run 1/`, run 20 Oct 10:32-11:13, reward 0.8043 (`verifier/reward.json` 80.43).
- **The 20 Oct run is on a PRE-QC-v6 bundle.** `agent/instruction.txt` differs from the current `instruction.md` (diff below), and the judge/test set it was graded on (r1-r18, `trap_*`, `negative_*`) differs from the current 46 tests plus 11 criteria. **J = N/A for the current bundle.** No finding below can be HIGH, because there is no trajectory evidence for the current text.
- probe tonight: none. Audit only; scratch work under `_scratch/match-replay-desync-audit/` (copy of `solve.py` and `data/`, run with `python3 -B`).
- latest QC report read: `20261023_match-replay-desync-audit/p12_v3_r5/` (`PL_NOTE.md`, `RECHECK_FIX.md`, `STACKING_CHECK.md`, `kit_*_qc.txt`). QC verdict: instruction 5/5, judge 19/19, structure 17/17, tests 36 pass and 1 warn (A3, 46 checks > 35, kept by Ayush). QC flagged no leak. Its one real finding was CL-4: the latest-entry reading cost only 1/172, and it was fixed by `_settle_one_order` plus a divergence planted only in the shipped, density and tiebreak sets.

## Step 1 - agent-visible surface

Source: `environment/Dockerfile` (`WORKDIR /app`, `COPY data /app/data`, `RUN chown 1000:1000 /app`). The agent runs as `user = "1000:1000"` (`task.toml [agent]`). `/app/data` is COPY'd as root, so it is read-only for uid 1000, as the instruction says.

| path (agent can see) | size | note |
|---|---|---|
| `/app/data/replay-format.md` | 7430 B | all 12 transforms described, one per bit |
| `/app/data/engine-rules.md` | 4617 B | identity, windows, charters, cadence, upkeep, reconciliation, reversals |
| `/app/data/charter-scale.md` | 5647 B | word tables, mask/digest recipes, baselines, transfer, caps, cadence/upkeep scale, bench, counting |
| `/app/data/report-schema.md` | 4622 B | fields, types and orderings of every report |
| `/app/data/calibration.md` | 7838 B | 11 candidate ranges, 11 published control figures, fragment definitions for each control |
| `/app/data/sample_cobalt.rpl`, `sample_orchid.rpl` | 1307 B, 1335 B | flags 0x0000, plaintext (36 and 37 entries) |
| `/app/data/calib_wisent.rpl` | 1390 B | flags 0x0fff, number 0 |
| `/app/data/field_marrow.rpl`, `field_quarry.rpl`, `field_tundra.rpl` | 1418 B, 1340 B, 1361 B | flags 0x0fff |
| `/app/data/roster-register.csv` | 614 B | 24 rows; has a self-successor cycle (lamia), chains (nixie > ogre > pegasus > quasit), merges, cockatrice closed 814 < opened 3523 |
| `/app/data/tick-schedule.csv` | 133 B | W5 `live=0`, W7 `3900,3200,1` (degenerate) |
| `/app/data/bench-candidates.csv` | 254 B | 16 rows |
| `/app/data/example-scenario-report.json` | 83 B | `{"cadence":"peak","unit_count":0,"amount_total":"0/1","units":[]}` in `json.dumps(indent=2)+"\n"` form |

- Not visible: `tests/`, `solution/`.
  - `environment/Dockerfile` copies only `data` into the image. There is no COPY/ADD of tests or solution, and no RUN that generates files.
  - Tests ship in a separate verifier image: `tests/Dockerfile` does `COPY . /tests/` then `chmod -R go-rwx /tests`, with `task.toml [verifier] environment_mode = "separate"`. `tests/test.sh` runs `rewardkit /tests --workspace /app` and only reads `/app/out` artifacts.
  - Tests are never in the agent container. I could not confirm the harness's copy-at-verify time from the files alone, but the separate-image setup makes it moot.
- No expected output, digest of expected output, or script that computes it ships. The calibration figures are control digests of decode intermediates, plus the cadence-class stamp (CTRL-J) and the upkeep target (CTRL-K) for the shipped set. Those are the shipped L1 control, and they never involve amounts.
- Agent image also holds `/opt/openhands-sdk-venv` (agent runtime). No task content.
- `.DS_Store`, `__pycache__`, backups, `.git`: none under `environment/` (checked with `find`).

## Step 2 - checklist A-J

| id | Y/N | evidence |
|---|---|---|
| A names | N | Files: `sample_*` (the two flag-zero captures, matches the instruction's own statement), `calib_wisent`, `field_*` (all flag 0x0fff, no behavioural difference), `bench-01..16`, `W1..W7`, creature words, enum values. None points at a trap. `calib_wisent` is not special: a plain 0x0fff capture, number 0. |
| B tone | N (mild) | No CAPS, bold, "be careful" or "note that". Mild emphasis: `engine-rules.md:13` "that question is settled before any other". Instruction line 3 "state each transform precisely". |
| C rules naming the separating case | **Y** | See findings M1, M3-M8 (consequence sentences) and test-to-leak map. |
| D shipped data showing the separating case | N for outcomes, Y for occurrence | The example report is empty (`unit_count 0`, `units []`), so it shows no settled figure. The sample captures decode (flags 0) to pre-open entries, past-close entries, `lamia` cycle entries, dead-window and off-window ticks, and kind-3 reversals, but no shipped file shows any settled outcome. Running the oracle on the shipped set gives 217 entries, 0 `none`, 22 echoes, 44 reversals, 13 promoted, and a residual of 6893 (the allowance binds). That is invisible to the agent. Separating inputs (degenerate W7, dead W5, cycle, chain) are in the task inputs. See L1. |
| E visible tests / validators | **Y (by design L1, wider than stated)** | The 11 control figures are an executable validator. I verified in scratch that CTRL-J (cadence classes of the shipped set) goes red under four wrong readings of settlement rules: latest-entry cancellation, dropping pre-open entries, treating dead window W5 as live, and chasing the self-successor cycle. See M2. The controls stay green under the allowance, renewal and cancelled-draw readings (TRUTH.md says so; CTRL-J/K never read amounts). The shipped set has 0 `none` entries, so the four damage rules (`zeroed`, `carry_reset`, `stepped_gap`, `index_lap`) have no validator. |
| F repo/history | N | No `.git`, no comments, no TODO/FIXME in `environment/`. |
| G leftovers | N | `grep -rniE "harbor\|QC\|lever\|rubric\|trap\|decoy\|hidden\|grader\|oracle\|stale\|deprecated\|TODO\|FIXME\|reward\|judge\|verif\|test\|held\|fresh\|solution\|answer\|expected"` over `environment/` and `instruction.md` gives only innocent hits (`stale` in `charter-scale.md:105-106` counting convention; "held" as a verb; "test" in "candidate under test" and "trap" nowhere). Exception: instruction line 13 "fresh inputs" and "imported at grading" (L2). |
| H cross-file consistency | Y (redundancy, no contradiction) | The allowance rule is stated four times: `engine-rules.md:44-45`, `:59-60`, `:79-80`, `charter-scale.md:68-79`. The instruction restates rules the docs own (M9). `promoted_reversal_count` hint at `engine-rules.md:101-102` is not true on the shipped set (M10). Instruction line 3 says transforms are in "no particular order of application", yet `calibration.md:15-23` ("the control reads") gives the undo order. |
| I judge/conduct hints doubling as test plan | Y for R1-R5 (intended), N for R7-R9 | Instruction lines 9-11 mirror `judge.toml` R1-R5 almost word for word: "Enumerate the full candidate set of every withheld quantity", "Establish each quantity against its own control figure", "Append each rejected candidate ... at the moment you discard it", "decimal or rational facility", "empty the report directory ... rebuild ... leaving the program itself in place". These are instruction-following criteria and must be visible. R6 "write only under /app/out" is stated. R7, R8, R9 (agent builds its own cap, renewal and cancelled-draw inputs) are not hinted anywhere in the instruction or docs: genuinely hidden. R10 (honest claim) and R11 (code quality) are not hinted. |
| J trajectory use | N/A | The run is on the older bundle. See the survivor note below. |

### Old instruction vs current (diff of `agent/instruction.txt` and `instruction.md`), clearly a note not a finding

Removed since the 20 Oct run (the old run saw these):
1. A whole paragraph asking for the "first divergence between the two cancellation readings" (walk position and tick), "identity depth" with the deepest word, "last promotion" position, and "number of capture entries whose recorded kind byte marks them as taking their payload from an earlier entry". That was a test-plan paragraph (old r7-r13). It is gone.
2. "In the slice shipped here, exactly one value of that further quantity reproduces the published figure." Gone.

Added: "Keep the whole program in that one file; nothing else under /app/out is imported at grading." and "each output document is graded whole on fresh inputs".

Survivors of old-run leaks in the current text:
- Anything in the docs that supplies "two cancellation readings": `engine-rules.md:86-88` still says "earliest ... not the latest one" (M1), and `:101-102` still points at the cancelled-nothing count as the way to learn the order (M10).
- `engine-rules.md:44-45`, `:59-60`, `charter-scale.md:68-79` (the allowance algorithm) were in the docs then and still are.

## Test-to-leak map

46 checks in `tests/test_output.py` (42 positive, 4 negative) plus 11 judge criteria. "Genuinely hidden" means no visible sentence or datum reveals the test's specific input, other than the generic fact that fresh sets exist.

| hidden test | visible sentence / datum that reveals it |
|---|---|
| `format_program_delivered` | instruction line 7 (path) |
| `record_derivation_matches` (deep chain, 5 passes vs 4 shipped) | instruction line 9; `report-schema.md:68-86`; `charter-scale.md:104-112` (settling pass, falsifier definitions); `calibration.md:41-42`. Visible by design. The deep chain itself is hidden (shipped roster shows chain nixie>ogre>pegasus>quasit, 4 passes). |
| `format_writes_only_named_reports` | `report-schema.md:116` "writes every report named above and nothing else" (L3) |
| `instance_scenario_visible`, `instance_perf_report`, `instance_recommendations`, `instance_data_quality` | shipped set + every rule doc; no outcomes shipped |
| `instance_report_serialization` | `example-scenario-report.json` and instruction line 7 "byte for byte" |
| `general_scenario_peak/steady/latency` | `engine-rules.md:67-68`, `calibration.md:24`, `:135-137` |
| 12 `trap_*_inverse` (sealed...warded) | `replay-format.md:61-124` (each bit described) + `calibration.md:75-125` (exact fragment for every step) + all 12 exercised on the shipped captures and checked by CTRL-A..I. Visible, and checkable. |
| `trap_zeroed_payload_inverse` | `calibration.md:66-68` (bad check unpacks to nothing), `:85-87` (lone reserved byte, 24 zero digits). Prose only; no `none` in the shipped decode. |
| `trap_carry_reset_inverse` | `calibration.md:109-111` "(0 and 0 for the first entry and for an entry after a `none`)" |
| `trap_stepped_gap_inverse` | `calibration.md:119-120` "a `none` entry counting as a stored 0" |
| `trap_index_lap_inverse` | `calibration.md:122-123` "The unit index, taken against the length of the list" |
| `general_deep_identity_chain` | `engine-rules.md:23-27`; shipped roster has a chain |
| `general_charter_cap_surplus` | `charter-scale.md:68-79`, `engine-rules.md:44-45`, `:59-60` |
| `general_empty_charter` | `engine-rules.md:57` (M8) |
| `general_window_boundary_shift` | `engine-rules.md:37` ("lies inside a live window"); `tick-schedule.csv` |
| `general_degenerate_window_live` | `engine-rules.md:42`, `:44-45`; `tick-schedule.csv` row W7 |
| `general_dead_window` | `tick-schedule.csv` `live` column; `engine-rules.md:34-37`, `:39-40` (M4) |
| `general_reversal_density` | `engine-rules.md:83-99` (M1, M10) |
| `general_reversal_tiebreak` | `engine-rules.md:94-95`, `charter-scale.md:72-73` |
| `general_population_scale` | none beyond "any capture set drawn from this engine" (instruction line 7) |
| `general_baseline_scale` | `charter-scale.md:46-52` (M7); bench list |
| `general_cadence_partition` | `engine-rules.md:65-68`, `charter-scale.md:81-85` |
| `general_fixpoint_new_unit` | instruction line 5 "unique stable assignment ... solved for" (M9) |
| `general_donor_table_rotation` | `replay-format.md:116-120`, `calibration.md:121-125` |
| `mutation_cadence_modulus_moves_only_classes` | genuinely hidden |
| `mutation_window_split_moves_only_amounts` | `engine-rules.md:44-45` (renewal at each live window's first tick) |
| 4 `negative_*` | genuinely hidden (no hint; instruction "do not look up a published solution" only) |
| R1-R5 | mirrored in instruction lines 9-11 (intended) |
| R6 | instruction line 13 "write only under /app/out" |
| R7 (cap overrun input), R8 (renewal input), R9 (cancelled-draw input) | none - genuinely hidden. The related rule text is visible (`charter-scale.md:68-79`, `engine-rules.md:44-45`) but nothing tells the agent to build and check own inputs. |
| R10, R11 | none - genuinely hidden |

## Findings

No CRITICAL: `tests/`, `solution/`, `TRUTH.md` and `solve.py` are not copied into the agent image. No HIGH is possible (no trajectory for the current text). Every row below is INFERRED from the text and from scratch runs of a copy of the oracle; none were seen used by an agent.

| id | cat | sev | file:line + quote | evidence it helped / INFERRED | proposed fix (NOT applied) | QC rule the fix touches + risk | touches tests/data |
|---|---|---|---|---|---|---|---|
| M1 | C/B | MEDIUM | `engine-rules.md:87-88` "cancels the earliest still uncancelled entry of the same kind recorded by that unit, not the latest one" | INFERRED. Names the rival reading (W1: "never explain the trap"). Maps to `general_reversal_density`, `general_reversal_tiebreak` and the shipped-set instance tests (TRUTH.md one-fact-wrong row: latest-entry reading costs 15 pts). The old instruction paragraph about "the two cancellation readings" was removed, so this sentence now carries the same pointer. | Drop ", not the latest one"; keep "the earliest still uncancelled entry". | W1; IN-16 (unambiguous single reading): "earliest" alone is still one reading. Low risk. | N (docs) |
| M2 | E | MEDIUM | `calibration.md:24` / `:135-137` CTRL-J "the cadence class every surviving unit falls in" | Verified in scratch (`var_latest.py`, `var_preopen_drop.py`, `var_dead_live.py`, `var_cycle_chase.py`): on the shipped set CTRL-J finds no candidate under the latest-entry reading, the pre-open-drop reading, the dead-window-live reading (cycle chase raises a loop). Oracle aurochs tick total 17280 vs 17272 under "latest". So the agent can try alternative readings of identity/window/reversal rules and see red. INFERRED for the effect on an agent, but the mechanism is verified. The L1 control is meant to stay green under the allowance reading only. | By design (L1); a fix would change the control and the generated sets, which is not a one-line change. Option: accept. | L1 / TS control fairness (G3 P2), CL-4 (v5 fix `_settle_one_order` planted divergence). Risk high. | Y |
| M3 | C | MEDIUM | `engine-rules.md:20-21` "The opening tick sizes the charter baseline and takes no part in this question, so an entry whose tick falls before the opening tick still settles under the word it names." | INFERRED. Consequence sentence naming the exact separating case (pre-open entries; W1/W3 "restates the consequence of a definition"). The shipped data makes it ordinary: about a third of decoded sample entries are pre-open, and `var_preopen_drop` fails CTRL-J anyway. Maps to every scenario test and `trap_*` (they all carry pre-open entries). | Delete from "so an entry ..." onward; keep "does not stand past that closing tick". | W1, W9 (literal reading must still pick one rule: "in force for an entry when the entry tick does not stand past that closing tick" already does). Risk low. | N |
| M4 | C | MEDIUM | `engine-rules.md:39-40` "The identity question is asked before the window filter, so an entry that reaches a retired word counts as retired even when no live window admits it." | INFERRED. Consequence sentence that fixes the drop-order (TRUTH one-fact-wrong: "off window drop checked before the retired drop" = 161/172). Maps to `general_dead_window`, `data_quality` instance test. Note `trap_flipped/warded` sum the two drop counts, so only those two are order-neutral. | Reduce to "The identity question is asked before the window filter." | IN-16: that sentence still defines the order. Risk low. | N |
| M5 | C | MEDIUM | `charter-scale.md:78-79` "Reversal matching is complete before any entry draws, so a cancelled entry never draws." and `engine-rules.md:97` "A cancelled entry contributes nothing to any total." | INFERRED. Names the R9 case and the TRUTH row "cancelled entry draws before it is cancelled" (97/172). Redundant: said in two files. Not hinted for self-test. | Keep the first sentence only ("Reversal matching is complete before any entry draws"); drop ", so a cancelled entry never draws". | W1, W10 (one rule, one place). Risk low. | N |
| M6 | C | MEDIUM | `charter-scale.md:75-76` "An entry that draws nothing still settles." | INFERRED. Names the zero-draw separating case (counts into `settled_total`, `tick_total`, cadence). One-sentence consequence; the rule before it, "What an entry draws is its settled amount", plus `engine-rules.md:64-65` ("settled tick total is the sum of the ticks of the entries that settled") already imply it. | Delete the sentence. | W1; AL-4/W9 literal reading must still make the oracle correct: does it? "settled tick total ... entries that settled" vs "settled amount = what it draws" could be read two ways if the sentence goes. Medium risk; keep unless a definition of "settled" is added. | N |
| M7 | C | MEDIUM | `charter-scale.md:50-52` "It does not read any capture, it does not change when a unit retires, and it does not change when a unit is carried to a successor." | INFERRED. A list of negations that names two hidden axes (retirement, succession) of `general_deep_identity_chain`, `general_baseline_scale`, `general_fixpoint_new_unit`, `general_empty_charter`. CTRL-K cannot catch a baseline mistake that alters the total, since it equals the total of opened ticks only if the agent also uses all rows. | Keep "The baseline is a property of the register alone."; delete the two "it does not change" clauses. | W1; IN-16 stays satisfied (property of the register alone). Risk low. | N |
| M8 | C | MEDIUM | `engine-rules.md:57` "A charter with no surviving unit contributes its baseline to the system and draws nothing." | INFERRED. Names the `general_empty_charter` fixture directly. Not stated anywhere else; the stock formula at `charter-scale.md:62-64` already gives it. | Delete the sentence. | W1; IN-16: formula is unambiguous with no flow. Risk low. | N |
| M9 | B/H | MEDIUM | `instruction.md:5` "the word an entry names has to be chased to the identity in force at that entry's tick before anything is counted. Entries outside every live window are set aside. ... a unique stable assignment exists and has to be solved for rather than approached by repeated substitution. Work the whole settlement in exact rational arithmetic; a binary floating-point pipeline will not reproduce the settled charter stocks." | INFERRED. Instruction restates identity, window, coupled-solve and exact-arithmetic rules that the docs own (W10: "instruction states no rule of its own"); names the method and the wrong method (the H7 pattern: amount + method + repetition). Maps to `general_fixpoint_new_unit`, `general_empty_charter`, `trap_drifted/spun` (perf_report stocks). Opus transliterates every sentence. | Cut the three rule sentences to a pointer ("the engine settles them per the notes"); keep exact-arithmetic only if the judge R4 needs it (R4 lives at line 11 anyway). | W10, W1; IN-16 (rule said once, in the docs). Risk medium: R4 is tied to line 11 wording. | N |
| M10 | I/H | MEDIUM | `engine-rules.md:101-102` "Counting the reversals that cancelled nothing is how a run learns whether it read the cancellation order the engine uses." | INFERRED, and **false on the shipped set**: oracle gives `promoted=13` under both earliest and latest readings (scratch run, `settle()` on decoded shipped captures, 217 entries, 44 reversals), while settled differs (23063 vs 23009). A self-check pointer that points at the right axis (cancellation order) with the wrong instrument; it also names `promoted_reversal_count` as a reading test. | Delete the sentence. | W1, QC IN-16/truthfulness (doc statement not true). Risk low. | N |
| M11 | H | MEDIUM | `engine-rules.md:44-45`, `:59-60`, `:79-80`; `charter-scale.md:68-79` (four statements of the allowance rule: renewal "to its full size before any entry at that tick draws", "draws what it can, the part it cannot draw is surplus", the whole draw algorithm "while the allowance left covers it, and otherwise draws what is left, which can be nothing") | INFERRED. The focal L3 lever is spelled out as an algorithm and repeated, including renewal-before-draw (R8) and "which can be nothing" (zero draw). Nothing is shipped that would show it going wrong (no control reads amounts), but a reader transliterates it. | State the allowance once (charter-scale Caps) and have engine-rules point there ("allowances: see Caps"); drop "which can be nothing". | W10, W1; AL-4 risk: today four sentences agree, so merging must keep one reading. Risk medium. | N |
| L1 | D | LOW | `tick-schedule.csv` W5 `0`, W7 `3900,3200,1`; `roster-register.csv` lamia `1500,lamia`; cockatrice `3523,814` | INFERRED. Shipped inputs show the cycle, dead and degenerate cases the docs rule on. Inherent to the task (they are inputs) and no outcome ships. | Accept. | W5 is about shipped outcomes, not inputs. | N |
| L2 | G/B | LOW | `instruction.md:7` "nothing else under /app/out is imported at grading" and `:13` "each output document is graded whole on fresh inputs" | INFERRED. Names a grading mechanism: the program is actually run as a subprocess (`test_output.py:2253` `Popen`), not imported, and `fresh inputs` is generic. Harmless; the first is also slightly wrong. | Reword to "Keep the whole program in that one file." | none | N |
| L3 | H | LOW | `report-schema.md:116` "It writes every report named above and nothing else." | INFERRED. Maps to `format_writes_only_named_reports`; the instruction's "empty the report directory ... leaving the program itself in place" repeats it. | Accept, or drop "and nothing else". | W1. | N |
| L4 | B | LOW | `engine-rules.md:13` "that question is settled before any other"; `replay-format.md:31-32` "so a transform that rewrites a payload or restates a count leaves every block check word untouched" | INFERRED. Mild emphasis / consequence sentence pointing at the block-check trap (CL: block check is a decoy; no hidden test depends on it differently from the doc). | Delete the consequence clause at replay-format.md:31-32. | W1. | N |

## What is clean

- Agent image: no `tests/`, no `solution/`, no TRUTH, no generator, no oracle output; `tests/` only in the separate verifier image (`COPY . /tests/`, `chmod -R go-rwx /tests`). `/app/data` is read-only for uid 1000.
- No `.git`, `__pycache__`, `.DS_Store`, backups, TODO/FIXME, board shas, or words like grader/oracle/rubric/lever/hidden/decoy in `environment/` or `instruction.md`.
- File names, ids, columns and enums are neutral. `calib_*`, `field_*`, `sample_*`, `bench-NN`, `W1..W7`, mythical creature words give nothing away.
- The example report is an empty skeleton in the final serialization (83 B). It shows no settled figure, no amount rendering beyond `0/1`, and no unit.
- No sample, calibration capture or control carries a settled amount. CTRL-A to CTRL-K never read an amount, so the allowance, renewal, surplus and cancelled-draw readings (the focal levers) are not visible as green/red anywhere.
- The bench list does not pin the scale: with baseline total 41225, scales 14, 17, 18 and 19 each have exactly one exact subset (scratch enumeration of the 16 candidates). So the bench list is not a shortcut for `upkeep_target_scale`.
- Judge R7, R8, R9 (the weight-3 conduct criteria on building own cap, renewal and cancelled-draw inputs), R10 and R11 are not hinted in the instruction or docs. Instruction lines 9-11 mirror R1-R5 only, which are instruction-following criteria that have to be visible.
- The four damage rules (`zeroed`, `carry_reset`, `stepped_gap`, `index_lap`) appear only as prose in `calibration.md`; the shipped decode has 0 `none` entries, so no control can validate them.
- Instruction has no mention of caps, allowances, renewal or surplus.

TOP_LEAK: M1 engine-rules.md:87-88 names the rival cancellation reading ("not the latest one"); M2/M10 together point at reversal order as a checkable axis, and CTRL-J on the shipped set validates it
COUNTS: C=0 H=0 M=11 L=4

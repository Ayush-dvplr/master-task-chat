TOOL CHANGES FOR P13 AND S9 (W1-035, draft, 3 Nov 2026). Nothing applied; every change waits for PROCEED. Line numbers are the live files in master_chat_tasks/tools on 3 Nov unless named otherwise.

| # | for | file | function or line | change |
|---|---|---|---|---|
| 1 | P13 | intake.py | main(), :179 to :192 | add --outside SRC, --origin (own_outside, assigned, teammate_agreed), --author, --traj, --slug, --agreement, --assigned-by, --band; dispatch to a new outside(a) |
| 2 | P13 | intake.py | new outside(a) | copy SRC without trajectories/ to master_chat_work/bundles/<slug>/, SRC whole to original_backup/; refuse teammate_agreed without --agreement; print or (with --apply) write the provenance block through status.py provenance |
| 3 | P13 | intake.py | new author_fp(bundle) | sha256 of the task.toml lines whose key starts with author; the values are never copied into a record |
| 4 | P13 | intake.py | tree_sha(), :46 | no change; reused for received_tree_sha |
| 5 | P13 | intake.py | new traj(a) | read trajectories/<model>/pass_summary.json (outside layout) as well as jobs/<slug>/logs/pass-summary.json (:116); call trajectory_readout.py per Run folder; write a scores row with event outside_baseline, valid false for the gate unless bytes_match |
| 6 | P13 | intake.py | :33 FINAL_GATE and :147 | read tests, rubric and final limits from settings.json gate (DR2), not literals |
| 7 | P13 | intake.py | job(), :184 choices | add event outside_baseline |
| 8 | P13 | status.py | main(), :47 | new subcommand "provenance SLUG k=v": writes task.provenance; origin, original_author, source_path, trajectory_path, received_tree_sha, author_fp are write once (refuse a second different value) |
| 9 | P13 | status.py | same | counts_for_ayush=true only with --ayush "<verbatim words>", stored in counts_words and logged to decisions.jsonl |
| 10 | P13 | status.py | table, :81 to :88 | add an origin column (own, own_outside, assigned, teammate_agreed) and a "not counted" mark |
| 11 | P13 | registry_check.py | main(), :57 | check the provenance block: keys present, origin in the three values, counts_for_ayush bool, original_author equal to the value in the first intake decisions row |
| 12 | P13 | drafts/P1/state_card.py | pushed_since(), :112 | skip tasks whose provenance.counts_for_ayush is false |
| 13 | P13 | issue.py | refusals(), :97 | warn (never refuse, R15) on kind build or rebuild for a teammate_agreed task without a stored owner agreement for a design change |
| 14 | P13 | loss.py | report() | accept a trajectory folder; with --levers LEVERS_FOUND.md or DESIGN.md print positive test points lost per lever and the primary lever's lost share |
| 15 | P13 | regression check script (REGRESSION_CHECK step 1, not yet a file) | byte diff step | compare author_fp before and after; any change stops the round |
| 16 | P13 | push check (Step 10, not yet a file) | before packaging | compare author_fp with provenance.received author_fp; print counts_for_ayush; Ayush runs the push |
| 17 | P13 | trajectory_readout.py | none | no change; it already reads an outside Run N folder |
| 18 | S9 | board.py | main(), "new", :146 | add "runner": "" to a new row (field always present on new rows; old rows stay without it and read as unknown) |
| 19 | S9 | board.py | main(), "set", :150 | refuse runner=<value> outside settings.runners.options; accept runner_src, runner_result, qc_fmw |
| 20 | S9 | board.py | save(), :132 to :134 | add a runner column to BOARD.md |
| 21 | S9 | issue.py | main(), :192 to :201 | add --runner with choices from settings.runners.options |
| 22 | S9 | issue.py | main(), :240 | pass runner=<value> runner_src=<step or ayush> to board.py set; default settings.steps[step].runner, else settings.runners.default |
| 23 | S9 | issue.py | new STEP_OF map near :56 | build, harden, rebuild to build; qc; fix; blind; research; probe, loss, ql, run, adhoc to mechanical |
| 24 | S9 | issue.py | :254 handoff print | show the runner in the handoff line |
| 25 | S9 | issue.py | before :242 write | add the ADAPTER Part 4 tool block for the runner (R32 line for oc-gpt-sol-6.1) |
| 26 | S9 | intake.py | session(), :92 to :98 | when a result*.json has "tool" and "model", map them to a runner; print "runner board X, result Y" and RUNNER MISMATCH when they differ; skip files without "tool" (harness result.json) |
| 27 | S9 | intake.py | session(), :103 to :105 | with --apply: set runner_src=result when no mismatch; on a mismatch write runner_result and a note, keep runner |
| 28 | S9 | intake.py | session(), :104 | compare status case blind (Q136 f, already decided; listed here because it is the same line) |
| 29 | S9 | intake.py | session(), qc rows | write qc_fmw=<fail>/<minor>/<warn> on the board row from the result file |
| 30 | S9 | intake.py | job(), :164 row | add lever_loss_pct (from loss.py with the task's lever list) and paid model to the scores row |
| 31 | S9 | auto/auto.py | spawn, :390 to :401 and board_set :723 | set runner and runner_src=auto on the board row from the spawn model |
| 32 | S9 | new tools/runner_report.py | whole file | the draft in tmp/W1-035/runner_report.py, moved to tools/ after PROCEED, settings path pointed at the live settings.json |
| 33 | both | drafts/P1/settings.json | runners | no change needed; runner_report.py and issue.py read options and default from it |

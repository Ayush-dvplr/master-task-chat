S9 RUNNER RECORD (W1-035, draft, 3 Nov 2026). Nothing applied. Source: ANSWERS.md ENTRY 70 and 71, drafts/P1/settings.json "runners" and "steps", tmp/W1-033/ADAPTER.md Part 3, the live board.py, issue.py and intake.py.

PURPOSE
Record which runner did each session, so the four can be compared on the same instructions, and later a model can be picked per step and failures traced (ENTRY 70).

THE FOUR RUNNERS (settings.runners.options)
oc-opus-5.5 (opencode Opus 5.5, default), oc-opus-5 (opencode Opus 5), codex-sol-6.1 (Codex Sol 6.1), oc-gpt-sol-6.1 (opencode GPT Sol 6.1).

1. THE FIELD
board.json row fields today: sha, slug, step, prompt, result, status, pending_id, issued, note, updated, kind (251 of 445 rows), started (2 rows). S9 adds:
  runner       one of the four option keys
  runner_src   how it was set: step (from settings at issue), ayush (Ayush said it), result (read from result.json), auto (auto.py spawn model)
  runner_result  only when result.json names a different runner (the mismatch is kept, never silently overwritten)
Old rows keep no runner; every report shows them as unknown. No back fill: guessing old runners would be an unmeasured claim (R5).

2. SETTING IT AT ISSUE: issue.py --runner
  issue.py SLUG KIND DRAFT OUT [--runner oc-opus-5.5|oc-opus-5|codex-sol-6.1|oc-gpt-sol-6.1]
  Without --runner: settings.steps[<step>].runner when the kind maps to a step, else settings.runners.default. Kind to step map: build, harden, rebuild to build; qc to qc; fix to fix; blind to blind; research to research; probe, loss, ql, run, adhoc to mechanical. (The steps block already says blind oc-opus-5 and research codex-sol-6.1, ENTRY 71 answers 2 and 4.)
  A value outside settings.runners.options is refused.
  issue.py passes runner=<value> and runner_src=step (or ayush when --runner was given) to board.py set, prints the runner in the handoff line, and adds the tool block from ADAPTER Part 4 for that runner (the R32 "strictly do not run subagents" line for oc-gpt-sol-6.1).
  When Ayush says "running: <sha>" with a runner, the master runs board.py set <sha> runner=<value> runner_src=ayush. When he says nothing, the issued value stays; for most steps that is the default oc-opus-5.5, as ENTRY 70 asks (open point 1 for blinds and research).
  auto.py spawn already knows the model it sends (auto.py:63, spawn --model, auto.py:390 to :401); it sets runner and runner_src=auto through its existing board_set (auto.py:723).

3. CHECKING IT AT INTAKE: intake.py SHA
  When a result*.json in OUT carries "tool" and "model" (ADAPTER Part 3 fields), intake maps them to a runner:
    tool opencode, model claude-opus-5-5 or opus 5.5 to oc-opus-5.5
    tool opencode, model claude-opus-5 to oc-opus-5
    tool codex, model containing sol and 6.1 to codex-sol-6.1
    tool opencode, provider openai or model containing gpt and sol to oc-gpt-sol-6.1
  It prints "runner board X, result Y" and "RUNNER MISMATCH" when they differ. With --apply and no mismatch it sets runner_src=result when the board row had only the step default. With a mismatch it writes runner_result=Y and a note, keeps runner, and the master asks Ayush which is right (he ran it). A result.json without "tool" is skipped for this check: harness run folders also hold a result.json (seen in master_chat_work/*/trajectory/claude-opus-5/), and those are not session results.
  Same function, already decided (Q136 f, ENTRY 71): compare the status case blind, so "DONE" from Codex counts as done.
  Also new: for a qc row, intake writes qc_fmw=<fail>/<minor>/<warn> on the board row from the result file (verdict and counts), so runner_report.py no longer depends on the free text note (today only 59 of 114 QC notes parse).

4. COMPARING: runner_report.py (draft in this folder, standard library, read only)
  Reads board.json, registry/tasks.json, registry/scores.jsonl and settings.runners. Per step (board kind) and runner:
    sessions, done, partial, failed, still running
    QC findings per QC session: fails, minors, warns, and the share with no fail
    fix: fails left at the next QC of the same task after each fix session, and fix rounds per QC cycle
    gate runs: tests, rubric, final, gate met share, credited to the runner of the last build, harden, rebuild or fix session before the run (the bytes the run scored)
    lever loss share: the new scores.jsonl field lever_loss_pct (percent of the primary lever's positive test points the paid run lost), written by intake.py --job with loss.py; shown as "no field yet" until then
    wall time: hours from started (else issued) to the last update; an upper bound, since it includes the wait until Ayush opened the session
  Every average carries its count n, and a cell with n under 5 is marked (few). The header states that a fair comparison needs the same step on similar tasks and enough sessions on each side; unknown rows (all history before S9) compare with nothing.
  Filters: --since, --origin own|outside|intake_unclassified (outside bundles from P13 are kept apart, since their starting quality differs).
  Sample run on the real records: RUNNER_REPORT_SAMPLE.txt (all 419 counted rows unknown, as expected).

5. WHAT A FAIR TEST NEEDS (for later, not built)
  The same step and template version on similar tasks; a paired run where possible (two runners on the same frozen copy, as a diagnostic); at least 5 sessions per runner per step before any reading; one week of records before a conclusion (as for DCP, ENTRY 71 answer 7). A per step model choice is Ayush's decision from the report, never automatic.

OPEN POINTS FOR AYUSH
1. When Ayush says nothing: record the step's runner from settings (blind oc-opus-5, research codex-sol-6.1) or always oc-opus-5.5 as ENTRY 70 words it? The draft takes the step's runner, since ENTRY 71 fixed blinds on Opus 5.
2. Model id for Sol 6.1: ADAPTER Part 2 has research on "gpt-6-sol" and scoring on "gpt-6.1-sol"; ENTRY 70 says Sol 6.1 for both Codex and opencode GPT. Which model id does Codex really run?
3. Harness paid runs (claude-opus-5) are not one of the four runners: record them as model in scores.jsonl only (as today), or add a fifth value?
4. Should the master ask "which runner?" when Ayush says "running" without one, or record the default silently as ENTRY 70 says?

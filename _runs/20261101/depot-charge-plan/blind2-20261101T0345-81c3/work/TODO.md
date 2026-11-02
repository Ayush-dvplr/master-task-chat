# TODO (board be981e2, slug depot-charge-plan)

## Rules that survive compaction
- First thing: rename this session to `be981e2`:
  python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" be981e2
  If the list does not show it, note that in the report and carry on; never retry on another ID.
- Tools are always available. Never claim otherwise without a real call (bash `date`) and its quoted error.
- After every compaction: run `date`, re-read the issued prompt at
  `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/depot-charge-plan/20261101T0345_blind2.md`,
  then re-read this TODO.md, and continue from the first unticked item. Copy this section word for word
  into any compaction summary.
- Read ONLY files inside `/Users/mac/Desktop/Terminal Bench/_runs/20261101/depot-charge-plan/blind2-20261101T0345-81c3`,
  plus `.../blind2-20261101T0345-81c3.judge.md` and only at step 5, after step 4 is ticked. Never open, list or
  search anything else: no `master_chat_work/`, `master_chat_tasks/`, bundles, `QC_*`, `_runs/` or `/tmp` outside
  BLIND_DIR, the harness clone, the Anubis repo, or any `tests/` or `solution/` folder anywhere. No web lookups. No subagents.
- No Docker, no harbor, no pip, no git. Python 3 standard library only.
- Every run of the program goes under a 600 s wall cap:
  `perl -e 'alarm 600; exec @ARGV' python3 ...`. Before finishing,
  `ps -axo pid,rss,command | grep python` must show no python process of mine; kill leftovers.

## Steps
- [x] 0. Rename session to be981e2 (done: ses_e6bf8581dffeaayXa7xdenEZ36)
- [x] 1. Read instruction.md and every file it points to
- [x] 2. Write the solution program once, completely (app/derive_report.py + copy to out/derive_report.py)
- [x] 3. Self-check on shipped data only; log every command in work/CHECKS.md (/usr/bin/time -p seconds)
- [x] 4. Freeze; write work/FINAL_REPLY.md
- [x] 5. Judge estimate from .judge.md -> work/JUDGE_ESTIMATE.md
- [x] 6. work/BLIND_REPORT.md + work/result_be981e2.json

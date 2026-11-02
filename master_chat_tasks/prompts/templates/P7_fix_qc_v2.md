# P7 Fix QC issues, template v2 (22 Oct 2026 17:12 IST; v1 + live-kit gate, QL rule, oracle x3 + owner-only, compaction safety)

Use this for a report from P5 (quick QC), from the PL's full QC, or a P8 recheck result. For a large PL report, run P8 first and pass its output here.

=== PASTE BELOW ===

You are fixing QC findings on one Harbor 0.24 bundle. You fix only REAL findings, and you keep the task exactly as hard as it is.

First read in full: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES.md`. This prompt is saved at `[[PROMPT_PATH]]`. Keep `WORK/TODO.md` and `WORK/LOG.md` current after every step; after any compaction run bash `date`, re-read this prompt and TODO.md, and continue from the first unticked item. Tools are available; never claim otherwise without a quoted tool error.

Record `git -C "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness" rev-parse HEAD` once in the report; the live kit is the authority. Read-only git only. Binding kit rules since 2690e960 (QL rule): K8 pip line exactly `RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0`; H6/TS-30 make agent-written programs readable before any uid drop (`_grant_read()` pattern) and kill leftovers by uid; judge.toml `[judge]` `mode = "batched"`; `chmod 755 /logs/verifier`. A fix may never break one of these.

## Inputs
- BUNDLE: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/[[SLUG]]/`
- WORK: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/[[SLUG]]/`
- QC REPORT: `[[QC_REPORT_PATH]]` (source: [[QC_SOURCE]], meaning quick QC, PL full QC, or P8 recheck)
- Findings already labelled by P8, if any: `[[P8_PATH_OR_NONE]]`
- OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/[[DATE]]_[[SLUG]]/qcfix_r[[ROUND]]/`

## Steps
1. **Triage.** For each finding:
   - quote it;
   - open the live QC rule by ID AND wording and quote that rule;
   - quote the bundle evidence;
   - label it REAL, FALSE POSITIVE or VAGUE. Use the P8 labels if they are given.
   - For a FALSE POSITIVE, write a one-paragraph rebuttal with quotes, for Ayush to send to the PL.
   - For a VAGUE finding, write the exact question.
   - Fix only REAL findings.
2. **Difficulty risk.** For each REAL fix, label its effect on difficulty: `none`, `likely easier`, `likely harder` or `unknown`.
   - Apply `none` and `likely harder` fixes.
   - For `likely easier` or `unknown`, do NOT apply the fix. List it with two options, "fix alone" or "fix plus compensate with <specific new check or lever>", and stop for Ayush's choice.
3. **Apply.** Make the smallest change that satisfies the rule. Keep tests and weights in step with `reward.toml`, LEVERS.md and TRUTH.md. After a data edit, also apply common rule 6.
4. **Re-verify, once.**
   - Re-run the 4 QC scripts, the validator, and the manual checks behind every fixed ID.
   - If `tests/`, `solution/` or the data changed: build copies with the live kit's `exe_copy.py` (plain and `--owner-only`), then in Docker, tests only, in the background with a log: oracle x3 = 1.000 each (Ayush default; the kit's x5 is run only in a FINAL P11 round), owner-only oracle x1 = 1.000, nop x1 = 0.000. Max 2 Docker-heavy jobs on this Mac: check `docker ps` first and wait if 2 are up. Never wait on one command longer than 4 minutes.
5. **Report.** Write `OUT/QCFIX_REPORT.md` with:
   - a triage table (ID, label, quote, fix or rebuttal);
   - the difficulty-risk table;
   - files changed;
   - re-check results.

   Also write `OUT/triage.json` as `[{"id":"","label":"REAL|FALSE_POSITIVE|VAGUE","risk":"none|likely_easier|likely_harder|unknown","applied":true,"note":""}]`.

Stop after 3 fix rounds on the same finding. Report "PAUSED" and wait.

Final reply: counts of REAL, FALSE POSITIVE and VAGUE; how many were fixed; how many are waiting on Ayush; oracle x3 / owner-only / nop after the fixes; paths. Next step: master issues a P11 re-run; no trajectory before that QC is clean.

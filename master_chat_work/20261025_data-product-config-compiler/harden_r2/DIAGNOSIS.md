# DIAGNOSIS: data-product-config-compiler, harden round 2 (board 8e4df45)

Probe 2 (25 Oct 07:14, attempt 2, bundle after harden r1 e317de1): tests 120/120 (34/35 checks; only the negative
`negative_hardcoded_sample_answers` did not fire), judge 37/37, overall 100. Probe 1: tests 125/125, judge 25/28,
overall 94.65. Kit HEAD 976c166611e555e2ba20eb8d81bed279cee1ea30 (as expected). Phase 1 only: no BUNDLE edits.

## 1. Phase A: is the score genuine? GENUINE

- Copy vs BUNDLE: `diff -rq` of `.kiro-staged-tasks/data-product-config-compiler` vs BUNDLE shows only
  `.kiro-staged-from` and `task.toml` `allowed_hosts` adding `host.docker.internal` (lines 25, 32): harness staging only.
  BUNDLE files unchanged since r1 (data 00:59, reward.toml 01:18, judge.toml 01:38, tests 01:44 IST 25 Oct).
- `Run 1/result.json`: trial `data-product-config-compiler__6CNLB7v`, `exception_info: null`, agent openhands-sdk 1.55.1
  claude-opus-5, agent 01:30:29-01:42:47Z (12 m 18 s of 7200 s), verifier 01:42:57-01:43:48Z, reward 1.0, $3.80.
- `verifier/test-stdout.txt` is two lines: `_check_restates_shipped(): fresh-release config.json names its own release`
  and `reward: 1.0`. No `Permission denied` / `Errno 13` anywhere; the only Traceback is the agent's own probe
  (NameError, step 10). `wrapper.log`: "INTEGRITY: all 1 trial(s) completed cleanly; scores are trustworthy."
- Judge read the response: reasons in `reward-details.json` quote trajectory specifics, for example R13 "synthetic
  altered data defines o.expired with an earlier open assignment and a later assignment ending before compile date ...
  DP4 orphaned", R15 "weights and caps DP1=1, DP2=2, DP3=3 so DP3 returns large initial excess and DP1/DP2 only become
  over-cap after that excess is redistributed". Those match steps 37-39.

## 2. Root cause

| Cause | Answer | Evidence |
|---|---|---|
| 1 run error or wrong copy | NO | staged copy = BUNDLE except staging lines; no exception, timeout, verifier error or missing file |
| 2 harness or rescoring change | NO | same kit HEAD, same finalize path (rescale 1.0 -> 100, ctrf already normalised, in-verifier judge). There was never a hard tests baseline: probe 1 was tests 100 as well, so "baseline" means the r1 fuzz prediction, not a measured score |
| 3 our QC/fix rounds made it easier | PARTLY | no QC round since r1. The r1 harden edits themselves put each rule in front of the agent as a complete procedure (see cause 4) and shipped the NL-4 separating plants and NL-3 cap rows |
| 4 levers weak by design | YES (PRIMARY) | each rule names its separating case; the habit each lever relied on lived only in the old tool, which the agent deleted (step 16) and rewrote from the contract |

Files changed since the last hard baseline (there is none; listed since r1 start), and what each put in front of the agent:

| File | Change in r1 | Rule, figure or separating example exposed |
|---|---|---|
| environment/data/config_contract.md :38-42 | NL-1 glossary | the rule names the chosen row: "the one with the latest active_from" |
| config_contract.md :63-65 | owners.csv "several rows; no two rows of one owner share an active_from" | announces overlap and that the tie needs no break |
| config_contract.md :87-93 | NL-4 text reading | "one or more of the digits 0 to 9" is a regex; "true or false in any letter case" is `.lower() in` |
| config_contract.md :140-145 | NL-3 cap paragraph | names amount (excess), keeper (keeps its cap and the units it holds), recipients (below cap or no cap), method (largest remainder, Q = units given back, W = their weights), repetition and leftover |
| products.ini, env_dev.toml, env_prod.toml | NL-4 plants regenerated 00:59 | `partitions = "+1"`, `+16`, `retention_days = "+45"`, `replicas = +3`, `alerts_enabled = no/on/1`, `pii_scan = 0/off/1/on`, env `weight = "+6"`: the separating cases are shipped and visible |
| product_overrides.jsonl | 4 `quota_cap` rows | caps visible; they bind in one round only (agent step 28: round 1 gives back 41, round 2 gives back 0) |
| owners.csv | overlapping rows | shipped rows never separate the readings (agent step 33: "owners where interpretations differ: 0") |
| tool.zip | habit code (first covering row, round() quota, lenient coerce) | evaporated: agent deleted all modules at step 16 and wrote its own |
| tests/test_output.py, reward.toml, judge.toml, solution/* | r1 tests and judge | not visible to the agent |

Cause 4 per lever:

| Lever | Rule text and location | Step the agent got it right | What gave it away |
|---|---|---|---|
| NL-1 H3 assignment = latest active_from | config_contract.md :38-42 glossary, :63-65 owners.csv | read step 4 (whole contract); implemented step 18 (`resolve.assignment`, docstring "the latest active_from on or before day"); step 33 coded both readings on shipped data, 0 differ, kept the contract one; step 37 planted `o.expired` (earlier open row, later row ended) | rule names the chosen row in one clause, so transliteration is right; the wrong reading existed only in the old tool, which was not repaired but replaced |
| NL-3 H7 cap re-share | config_contract.md :140-145 | read step 4; written step 19 (`quota.split_quota`, loop with clamp, eligible = below cap or no cap, largest remainder of the given-back units); step 28 Fraction hand check; step 37 chained caps DP1..DP3 | yes, the explicit H7 wording was the giveaway: amount, keeper, recipients, method and Q/W are each named, so the loop is a line-by-line transliteration; the loose habit (water-fill from scratch) has nothing to attach to |
| NL-4 H1 digits 0-9, true/false | config_contract.md :87-93 | step 14, before any code, the agent ran its own `[0-9]+` fullmatch and `lower() in (true,false)` reader over products.ini, selectors.rules and env files and listed 15 shipped lines that fail (`+1`, `+16`, `"+45"`, `no`, `on`, `0`, `1`); steps 15 and 17 wrote `_DIGITS = re.compile(r"[0-9]+")`; step 37 synthetic `partitions = +16`; hidden fullwidth digits fail `[0-9]` by construction | rule is a literal character class and the separating cases are shipped next to it; LEAK_LIBRARY "self-testable rules are not levers" |

PRIMARY CAUSE: 4 (levers weak by design). Contributing: 3 (the r1 edits that wrote each rule as a full procedure and
shipped NL-4 plants). Why the r1 fuzz said 96.6%: it ran the probe-1 program, which was written against the pre-r1
contract (first covering row, no caps, lenient digits were then the stated or unstated spec). It measured a spec change,
not a misreading. Fuzzing an old agent's program is not evidence that a new agent will misread the new text.

## 3. Lever table (reward-details.json + trajectory)

Tests channel (P = 120, every positive check passed; negative -5 not fired):

| Check | Points | Earned | Levers | Verdict |
|---|---|---|---|---|
| status_team / _hard | 3 / 5 | 3 / 5 | NL-1, LV-CC-1 | LEAKED (step 18, 33) |
| date_shift | 5 | 5 | NL-1 | LEAKED |
| settings_int / _hard | 3 / 5 | 3 / 5 | NL-4 | LEAKED (step 14) |
| settings_other / _hard | 3 / 5 | 3 / 5 | NL-4, LV-CC-2 | LEAKED |
| dev_deploy / _hard, prod_deploy / _hard | 3 / 5 each | full | NL-4, NL-1 via team | LEAKED |
| config_quota / _hard, dev_quota / _hard, prod_quota / _hard | 3 / 5 each | full | NL-3, COUPLING | LEAKED (step 19, 28) |
| config/dev/prod_quota_capped | 5 each | full | NL-3 | LEAKED (step 37) |
| quota_rescale | 5 | 5 | NL-3 | LEAKED |
| rejected_overrides / _hard | 3 / 5 | full | LV-CC-2, LV-CC-4 | LEAKED (background, already in probe 1) |
| summary / _hard | 3 / 5 | full | all | LEAKED |
| shuffled_relocated | 5 | 5 | all | LEAKED |
| readonly_inputs | 3 | 3 | conduct | n/a |
| report_run, missing_input, invalid_date, catalog_mismatch, determinism, document_format, tool_zip_layout | 1 each | full | spine | n/a |
| negative_hardcoded_sample_answers | -5 | 0 (not fired) | cheating | n/a |

Judge channel 37/37: R1-R6 recompute w3, R7 altered copy w3, R8 maintainable w3, R9 lists files w1, R10 foreign dir
w3, R13 NL-1 conduct w3, R14 NL-4 conduct w3, R15 NL-3 conduct w3 all met; R11 honesty -3 and R12 grader paths -5 not
fired. The three lever-conduct criteria (R13-R15) were met by the same synthetic corpus (step 37) that proved the
readings: conduct criteria that name the separating case reward exactly what a careful agent already does.

Every counted lever LEAKED; no lever HELD.

## 4. Trajectory autopsy (49 steps, 12 m 18 s; no reasoning text recorded)

| Phase | Steps | Time | What happened |
|---|---|---|---|
| Read | 3-8 | 0-0:20 | `ls`; step 4 `cat config_contract.md` whole (11.9 KB); unzip tool; cat every small data file; step 8 `cat -n` of all old tool modules |
| Think | 8->9 | 1 m 40 s gap | no tool calls |
| Probe data | 9-14 | 1:59-3:08 | products.ini keys, deprecation kinds (0 RETIRE owner events shipped), owners.csv shape, overrides keys (quota_cap 4), step 14 its own text-layer reader over every text layer listing the NL-4 plants |
| Write | 15-22 | 3:33-4:54 | step 16 deletes every old module; writes loaders, resolve, quota, emit, cli from the contract; graded logic never changes after step 22 |
| Self-test | 23-48 | 4:54-12:16 | step 26 independent `/app/check/verify.py` (12.8 KB recompute); 27 shipped verify; 28 Fraction quota hand check; 31 layer trace; 33 both NL-1 readings; 34-36 error paths, catalog mismatch, read-only copy; 37 `/app/check/make_data.py` synthetic corpus planting all three levers; 38-39 synthetic compile + verify; 41-42 9000-product stress; 45-46 run from delivered zip and other dir |

Self-tests covered NL-1 (steps 33, 37), NL-3 (28, 37), NL-4 (14, 37): every hidden family. This is the LEAK_LIBRARY
row "agent self-tests covering every hidden family": a self-test can only be built when the rule names the case.

## 5. Reflex program

Saved at `OUT/agent_program/`: `out/` (the six documents and tool.zip from `/app/out`), `tool/` (README.md, cli.py,
emit.py, loaders.py, quota.py, resolve.py), `check/` (verify.py from step 26, make_data.py from step 37). Reflexes it
shows, all fitted to shipped shapes: deprecation date by `parts[0][:10]` (the contract :33-34 says exactly that today);
hand-parsed env "toml" by `partition('=')`; selectors by `split(" ", 2)`; csv via DictReader. Its quota loop is
identical to the reference (checked line by line against the pilot reference in `OUT/pilot/score_pilot.py`).

## 6. A better pre-probe check: blind program from rule text

Fuzzing an old program measures spec drift. Proposal: before any probe, give a fresh agent (no bundle, no tests) only
the rule paragraphs plus the first lines of the shipped files, ask it to implement the function each lever governs, and
score that function on the hidden separating cases. A lever is credible only if the blind function is wrong on at
least one separating case. This is cheap (one subagent, about 5 minutes) and it reproduces how Opus works: read the
rule, transliterate, test only what the shipped data shows.

Pilot run tonight (`OUT/pilot/`: `SPEC.md` given to a fresh deep-low agent, `agent/pilot.py` its code,
`score_pilot.py` the hidden cases, `pilot_result.txt` the score): 19/19 right.

| Lever | Hidden separating cases | Blind function |
|---|---|---|
| NL-1 assignment = latest active_from | later row ended; later row not yet started; later row started | 3/3 right |
| NL-4 digits 0-9, true/false | `+3`, fullwidth 3, Arabic-Indic 3, `007`, `TRUE`, `yes`, `1`, `off` | 9/9 right |
| NL-3 cap re-share | three cap corpora incl. a cap that binds only after re-share | 3/3 right |
| K1 (candidate) RETIRE dated by UTC date of an RFC 3339 instant, shipped all `Z` | `+05:30` and `-04:00` crossing midnight, fractional seconds, lower-case `t`/`z` | 4/4 right |

Calibration: the check reproduces probe 2 exactly (all three r1 levers right), so had it run before probe 2 it would
have flagged all three as dead. It also kills the strongest candidate I found (K1) before any edit.

## 7. Candidate shapes for Phase 2

Excluded (tonight's evidence across tasks, all read correctly by fresh Opus): H7 re-share, H6 chains, H3 credited or
calendar scope, glossary-only recursive terms. NL-1/NL-3/NL-4 in their current form are dead: each names its case.

Reflexes visible in the probe-2 program were tested for a lever that keeps a stated rule and hides only the instance
(G2 P2, legal-but-unseen encoding):

| Candidate | Shape | Evidence | Verdict |
|---|---|---|---|
| K1 RETIRE dated by the UTC date of its RFC 3339 instant; shipped timestamps all `Z`, hidden offsets cross midnight | G2 P2; the probe-2 program slices `parts[0][:10]` (but the contract :33-34 currently says "the first ten characters", so that slice is the stated rule, not a reflex) | blind pilot 4/4 right: once the rule says "UTC instant", the agent parses offsets | NOT CREDIBLE |
| selectors split on single spaces, env files hand-parsed, csv without BOM | G2 P2 on wire format | each variation is either illegal under the stated formats or would need a new explicit format sentence; G5 anti-pattern: explicit wire formats cost 0 | NOT CREDIBLE |
| repair habit (make-it-match, old tool habits) | G3 P3 | the agent deletes the shipped tool at step 16 and writes its own; repair-only habits never run | NOT CREDIBLE in this task shape |
| strict type beside a normalising neighbour | G4 P1 | already LV-CC-2 (JSON layers strict next to text layers); held in neither probe | DEAD |
| default plus later amending clause in other vocabulary | G1 P1 | needs a new data fact with no natural home here (owner, team, tier, label and weight are each read by one stated rule); any clause I can write names its field, which the G1 summary marks SAFE for the agent | NO CREDIBLE TEXT |

Recommendation: ROUND LIMIT: no credible lever. Every rule in this contract is written as a procedure the agent
transliterates, and the agent rebuilds the tool instead of repairing it, so neither misreading nor repair habits are
reachable without hiding a rule (forbidden). If the master still wants a round 3, the gate should be the blind-program
pilot above: draft the candidate paragraph, run it blind, and edit BUNDLE only for a candidate whose blind function is
wrong on a separating case.

## LEAK_LIBRARY rows

| Lever | How it was written | Leaked at | Planned fix |
|---|---|---|---|
| NL-1 H3 assignment = latest active_from (data-product-config-compiler r1) | glossary clause naming the chosen row "the one with the latest active_from"; habit only in the old tool | step 18 (written), step 33 (both readings coded, 0 differ on shipped data) | retire as counted lever; repair-habit levers die when the agent rewrites the tool |
| NL-3 H7 quota_cap re-share (r1) | one paragraph naming amount, keeper, recipients, method, Q/W, repetition, leftover | step 19 (transliterated loop), step 28 Fraction check, step 37 chained caps | retire as counted lever; an H7 paragraph that names its amount and method is a procedure, not a lever |
| NL-4 H1 digits 0-9 / true-false (r1) | literal character class next to shipped `+N`, `on/off/0/1` plants | step 14 (own reader over shipped text layers before writing code) | retire as counted lever; a rule that is a regex plus shipped separating plants is self-testable |

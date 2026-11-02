# Plan: master chat system for building and hardening Harbor 0.24 tasks
Draft v1, 21 Oct 2026 00:40 IST. Waiting for Ayush's approval. Nothing below is built yet.

## 1. Final folder (`Terminal Bench/master_chat_tasks/`)
The temp folder's contents move here once you approve. The temp folder is deleted only after you say OK.

```
master_chat_tasks/
  README.md              role, read order after compaction, write rules (short)
  GOALS.md               G1-G11 and the end outcome
  state.json             phase, what is running, upstream fingerprints in use, standing rules
  open_questions.json    open + closed questions (single place)
  decisions.jsonl        append-only, one decision per line
  log.jsonl              append-only state changes only
  lessons.jsonl          append-only: surprise -> lesson -> which prompt version it changed
  feedback.jsonl         append-only: Ayush feedback verbatim + my classification
  knowledge/
    KNOWLEDGE.md         distilled facts (generator, QC, research), kept under ~150 lines
    fingerprints/        pl_generator.json, qc.json (sha256 per file + git head)
    reports/             the 6 analysis reports, archived read-only
    intake/              handover digest, ecosystem, QL oracle/nop, PL S9 procedures
  registry/
    tasks.json           one entry per task (shape below)
    scores.jsonl         one line per score event
    levers.json          lever bank (shape below)
    ideas.jsonl          every ChatGPT idea, accepted or rejected, with the reason
  prompts/
    templates/           versioned templates: P1..P10_<name>_v<N>.md + CHANGELOG.md
    issued/<task>/       the filled prompt actually given, one file per step
```
The current `master_chat_tasks/{state.md,decisions.md,failures.md,log.md}` are converted into the JSONL files. Nothing is deleted without your OK.

Working areas (after the build, the temp folder is gone):
| Area | Holds | Read by me? |
|---|---|---|
| `master_chat_tasks/` | curated records only (above) | yes, in the read order |
| `Terminal Bench/master_chat_work/<YYYYMMDD>_<topic>/` | outputs of your sessions: reports, research downloads, baseline tables, QC reports | only the file I need, when I need it; key numbers are copied into `registry/` |
| `/tmp/<task>-<ts>/` | disposable scratch for sessions (copies, test runs) | no; deleted by the session |
| `_work/<slug>/` next to each bundle | builder notes (TODO, PLAN, LOG, datagen, wrong solvers) | only when diagnosing that task |

`master_chat_work/` is never in my read order, so it can grow without filling my context. Old dated folders can be archived or deleted on your OK.

## 2. Record formats
Rule for what is stored: decisions, state changes, failures, lessons, scores, levers, ideas. Not stored: chat summaries, re-statements, raw session output (prompts write reports to their own folders, and I store the path plus the key numbers).

- `tasks.json` entry: `{slug, created_ist, status (idea|building|hardness|qc|oracle|pl_qc|traj1|final8|delivered|parked|dropped), archetype, category, seed, idea_id, levers:[ids], new_levers:[ids], bundle_path, work_path, gen_fingerprint, qc_fingerprint, prompt_versions:{P2:"v1",...}, baselines:{oracle, nop, stub, lazy, per_lever:{}}, qc_rounds:[{ist, verdict, real, false_pos}], sessions:[ids], notes}`
- `scores.jsonl` line: `{ist, slug, event (build_baseline|traj1|after_fix_N|final8_runK), tests, rubric, overall, source_path, lever_points_lost:{lever:pts}, diagnosis, change_made}`
- `levers.json` entry: `{id, family (A-F or new), name, mechanism, first_used_ist, tasks:[slugs], build_effect, real_effect (mean points lost), status (candidate|held|leaked|retired), leak_reason}`
- `ideas.jsonl` line: `{ist, idea_id, prompt_version, setting, levers, verdict (accepted|rejected), reason}`

## 3. Prompt set (each one is a file you paste into a new session)
Delivery rule: every prompt I give is written to an `.md` file and I reply with its path. All heavy work (building, QC, oracle runs, research, big reads) goes to a new session through such a prompt; this chat never does it itself. One-off prompts that fit no template (for example new research) go to `prompts/issued/_adhoc/<YYYYMMDDTHHMM>_<name>.md`.
| # | Prompt | When | Output |
|---|---|---|---|
| P1 | ChatGPT idea prompt (dynamic) | new task(s) | 3-5 mechanism-card ideas. Carries the lever bank, held/leaked levers, used settings, and recent lever mixes to avoid |
| P2 | Build | idea accepted | bundle built from the generator scaffold plus `_work/` notes |
| P3 | Hardness check | after build | lazy and per-lever wrong solvers, baseline table, shortcut hunt; verdict PASS or REBUILD with reasons |
| P4 | Rebuild / strengthen | P3 says weak | targeted changes, then P3 again |
| P5 | Quick QC | after P3 passes | 4 scripts plus the major manual points from the live QC, quoted evidence |
| P6 | Oracle / nop / stub | after P5 | QL procedure: oracle x3 = 1.0, nop = 0.0, stub if possible |
| P7 | Fix QC issues | QC report (mine or PL's) | fix only REAL findings, keep difficulty, re-run the affected checks |
| P8 | FAIL recheck | before P7 on a big QC report | separate session labels each FAIL REAL / FALSE POSITIVE / UNSURE |
| P9 | Harden from results | score above gate (or "make it harder") | diagnosis from score, pass_summary or job folder; new levers; judge criteria built from the trajectory's mistakes (still true for a correct run) |
| P10 | Upstream diff | "generator/QC updated" or fingerprint differs | changed files, changed check IDs with their wording, what each changes for authoring; I then update the templates and KNOWLEDGE |

Rules built into every prompt: live QC path (never a copy), the allowed repos and read-only git, the 4-minute background rule with logs under `/tmp/opencode-logs/<task>-<ts>/`, scratch under `/tmp`, nothing kept inside the bundle folder, no edits to the generator or QC, measured claims only, and a fixed "Done when" plus a short final reply for me to check.

## 4. How each scenario is handled
| Scenario | What I do |
|---|---|
| Compaction | Read README -> GOALS -> state.json -> open_questions -> KNOWLEDGE -> last 10 lines of each JSONL, then re-check live files and git heads before acting |
| "Make N tasks" | Show the recent lever mixes, issue P1 (new version if lessons changed), gate ideas (uniqueness against my registry, levers A+B plus several new ones, QC risk), then P2..P6 per task |
| Builder or QC finishes | Check its files against the prompt's "Done when", record it in registry and scores, give the next prompt |
| PL QC report | P8 if large, then P7; record real and false-positive counts (false positives become QC lessons) |
| Score or trajectory | Compare against the baseline table, find which lever leaked, update the lever bank, issue P9 |
| Generator or QC updated | Compare the fingerprint with the remote head (read-only), issue P10, update templates; old tasks are flagged for a recheck only if a changed check touches them |
| Your feedback | Save it verbatim in feedback.jsonl; if it changes a rule, it goes to decisions and the template version is bumped |
| Conflict between authorities | Report it to you, never pick one |
| Git needed | Give you the command |

## 5. Self-improvement loop
After every score event: update the lever bank, write one lesson if something surprised me, and bump the template version if a lesson changes a prompt (logged in CHANGELOG.md). If 3 tasks leak the same way, change the template pattern, not the weights. Every month, or before generator v2: export the lever bank, lessons and QC false positives as input for building your own 0.24 generator.

## 6. Build order once approved
1. Create the final folder and convert the existing records (no deletions).
2. Write templates P1, P2, P3, P5, P6 first (needed for the first task), then P7, P8, P9, P10.
3. Seed `levers.json` with A-F plus the research levers (status candidate), and `tasks.json` with district-heat (parked) as the first entry.
4. Ask before deleting the temp folder.

## 7. Still open (do not block the build)
Q2 new archetypes (PL/QL), Q18 TRUTH.md conflict (PL), Q4 prompt delivery format, Q5 builder chat names, Q6 where bundles live.

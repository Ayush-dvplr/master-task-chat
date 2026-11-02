VERDICT: A new master chat can bootstrap from a generated state snapshot, but current state sources need reconciliation and conflict warnings first.

# Scope and method
Read-only research on 30 Oct 2026. Paths below are relative to `/Users/mac/Desktop/Terminal Bench/` unless absolute. The opencode DB was opened with SQLite `mode=ro`; no live stores were edited. Reproducible queries: `master_chat_work/20261030_upgrade2/S1_memory/scripts/analyze_memory.py` and `scripts/db_context_metrics.py`. `STORES.csv` inventories 22 stores/views and their writers/readers. Dates are IST where source records say IST; DB compaction timestamps were converted from Unix milliseconds to UTC.

## 1. Where state lives; current disagreements

**Finding.** Task status is in `master_chat_tasks/registry/tasks.json`; session state in `board.json`; open obligations in `pending.db`; rules/decisions in `state.json`, `README.md`, `decisions.jsonl`, `feedback.jsonl`, and knowledge/template files. Run evidence also lives in worker OUT folders, QC copies/reports and harness jobs. Chat summaries live in the opencode DB. `README.md:3-18,66-82` names the read/write pattern; `STORES.csv` gives paths, contents, writers, readers, freshness. The store writers are based on `README.md:22-35,66-82` and tool docstrings (`tools/status.py:6-11`, `tools/intake.py:16`, `tools/issue.py:13-24`, `tools/decide.py:2-9`); where those documents say “master,” this means the master operating the listed tool.

**Measured 28-30 Oct.** `scripts/analyze_memory.py`: 34 registry tasks, 352 board rows, 457 pending items, 589 decision rows. Decisions dated 28/29/30 Oct: 41/89/90. Board rows updated those days: 29/31/28 (88 total); pending items last updated those days: 34/15/13 (read-only SQL `substr(updated_ist,1,10)`); pending history events: 83/15/27 (same SQL on `history.ist`). The registry reports `updated_ist=2026-10-30T21:03+05:30` (`registry/tasks.json:2`). These are counts of different entities, so equality is not expected.

**Five concrete mismatches now:**

| # | Sources | Evidence |
|---|---|---|
| 1 | Board `7d4de68` done; linked pending `S358` running | `board.json:3554` row, SQL `select id,status,updated_ist from items where id='S358'` -> `running`, `2026-10-28 04:58`. |
| 2 | Board `b0aca9b` done; linked pending `S372` open | `board.json:3736`; same SQL -> `open`, `2026-10-28 15:53`. |
| 3 | Board `ac12c0b` done; linked pending `S373` open | `board.json:3749`; same SQL -> `open`, `2026-10-28 15:53`. |
| 4 | Board `a4f790c` superseded; linked pending `S374` open | `board.json:3762`; `scripts/analyze_memory.py` output `('a4f790c', ..., 'superseded', 'S374', 'open')`. |
| 5 | `state.json` still says cap 35, while explicit later decision removes it | `master_chat_tasks/state.json:29` vs `decisions.jsonl:112` and `feedback.jsonl:10`. |

Across board rows updated 28-30 Oct, 50 had a present pending ID; 21 had different statuses: 18 done/open, one done/running, one superseded/open, one superseded/dropped (`scripts/analyze_memory.py` plus read-only SQL result). This is a cross-store disagreement count, not 21 distinct task failures. The sole currently running board row, Nikhil `72ebb9d`, has empty pending ID (`board.json:4427`); pending instead reports three other running items, S358/S394/S395 (SQL `select id,title from items where status='running'`). Those pending items may represent instructions rather than live workers, so status semantics need a type-aware check.

Further rule drift: nested `state.json:31,89` still says old tests<100/rubric<100/final<70; top-level `state.json:126` says tests<85/rubric<85/final<40. `README.md:30-35` Pipeline paragraph still gives the older gate. `decisions.jsonl:112` allows genuine QC minors/warns while older `state.json:29` says zero findings. The 27 Oct feedback says two exact-byte runs for sentinel (`feedback.jsonl:19`); later `state.json:34` and current pipeline choose one run. These should be shown as dated changes, not silently merged.

**Recommendation.** Generate a short state view from registry, board, pending, latest decisions and feedback, with a conflict block rather than silently selecting one value. Cross-store reconcile by ID after `issue.py`/`intake.py` events; S3 should decide transaction boundaries. Expected gain (INFERRED): fewer stale status claims and less repeated manual reconstruction. Risk: a generator could bless stale records or treat pending instructions as worker statuses. Verify against these five examples and assert all emitted facts include source and timestamp; require type-aware status rules.

## 2. Compaction and re-discovery

**Finding.** `/Users/mac/.local/state/oc-bridge/tui/master.json` points to session `ses_ea5ff5f97ffe6WB1VzP4StPOw6`; DB `session.title` is `MASTER chat (task creation and hardening)`. Read-only DB query found 7,396 messages, 24,697 parts, six `part.data.type=compaction` markers, and six following text summaries (`scripts/analyze_memory.py`, `scripts/db_context_metrics.py`). `session.summary_additions/deletions=0` is a separate file-diff field and should not be used as the compaction count. Summary word counts were 2,264, 2,827, 3,659, 2,522, 2,561, 2,259, totaling 16,092 words (script output; split on whitespace).

**Three sampled summaries and later re-reads:**

| Compaction part | What the following summary held / gap | What later turns re-opened |
|---|---|---|
| `prt_15af176ae001FcOmMWYAkm5Hgh` (20 Oct UTC) | 2,264-word objective/rules summary | Within the next 300 parts, tool inputs reopened `master_chat_tasks/README.md` once and `knowledge/KNOWLEDGE.md` three times, both also read in the preceding 300 parts; also opened GOALS and state. `db_context_metrics.py` `RE_READS` and `FIRST_READS`. |
| `prt_15e3e2d270015QRVdBkZM3M3na` (21 Oct UTC) | 2,827-word summary | First source reads after compaction: README, GOALS, state.json, KNOWLEDGE.md, as shown by `db_context_metrics.py` `FIRST_READS`. |
| `prt_162f70e740017XgTMk1wpZYde4` (22 Oct UTC) | 2,522-word summary; following reasoning says a 10:30-14:48 interval was underdocumented (DB part `prt_162f758ab001oSK8i6S48KhhD0`) | Next 300 parts re-read live `Input_Bundle_QC/Final_checklist.md` three times, despite one read in the preceding 300; also Starter.md twice and README once (`db_context_metrics.py`). |

What was **proven**: role/rules/config/QC facts had to be loaded again from files, and one summary flagged an underdocumented interval. What exact facts vanished from model memory cannot be established from these logs alone; claiming irreversible loss would be UNVERIFIED. The chat record is recoverable in the DB, but a new chat has no concise, generated current-state entry point.

**Recommendation.** Persist a <= 12 KiB generated `STATE.md` plus a 10-line compaction checkpoint naming active sha, source timestamps, exact next action, conflicts and evidence links. Resume from those before targeted reads. Expected gain (INFERRED): avoids four broad startup file reads and reduces repeated summary prose. Risk: stale snapshots. Verify timestamp against source mtimes and run reconciliation; a stale snapshot must display `STALE` and defer to source records.

## 3. Decision quality, 23-30 Oct

**Finding.** Mistakes cluster around conflicting instructions, missing artifact checks, handoff checks and operational guards. The table includes Ayush's corrections and the master's own admissions, not every negative task outcome.

| Root cause | Observed mistake / evidence | Catching check |
|---|---|---|
| Contradictory go conditions | Cold-chain go froze `judge.toml` while requiring predicted final <=35 (`prompts/issued/cold-chain-backbone-quote/20261030T1200_go_cap60.md:6-8`); measured prediction was 43.1, admitted in `decisions.jsonl:555`. | Prompt feasibility check: allowed edit surface + measured scoring model can meet each bar before go. |
| Contradictory run instructions | Schema QC prompt says oracle count 3 at `.../20261030T0245_qc.md:9,78-79`, but appended note says Step 10 runs each once at `:103`; decision records oracle x1 in that QC (`decisions.jsonl:518`). | Prompt lint: one canonical oracle count and loop bound, reject later override that conflicts. |
| Ambiguous fix scope | REQUEST.md:C reports Nikhil “byte-identical” vs data-fix conflict. Inspected first fix prompt says shipped data stays identical “unless a direction below says otherwise” and explicitly confines trigger additions to hidden extracts (`.../20261030T1745_fix.md:29,53`). Actual conflicting downstream instruction was **UNVERIFIED** in this inspected prompt. | Diff-aware prompt lint listing each allowed path and whether shipped bytes may change. |
| Stale artifact/version | Master suggested reusing older sentinel gate runs after QC fixes; Ayush corrected it (`feedback.jsonl:18-19`). | Exact tree SHA join: counted run staged bytes = current frozen bundle. |
| Fix side effects | Master's sentinel fix prompt produced TS-13 check bundling and JD-15 route-weight findings (`feedback.jsonl:20`). | Re-run touched check IDs through kit TS-13/JD-15 rules and compare points/check. |
| Stale policy | Master repeatedly reintroduced a 35 test/criterion cap (`feedback.jsonl:10`); `state.json:29` retains it. | Rules linter against explicit latest decisions; generated state marks superseded lines. |
| Parsing/data classification | Auto paid-run cap was parsed as 0, then was set to 99 (`decisions.jsonl:509`; current parser `auto/auto.py:498-500`). Trajectory readout misclassified timeout/OOM before fix (`decisions.jsonl:451,453`; current `trajectory_readout.py:70-88`). | Parse numeric fields as whole values with a small regression case; classify exit/message evidence before score attribution. |
| Handoff slip | Repeated missing/wrong links and premature “running” (`feedback.jsonl:8-13,23`). | One-link issued-file handoff validator plus board-status confirmation from Ayush. |
| Process safety | Host solver children consumed ~185 GB swap and froze Mac (`feedback.jsonl:21`). | Solver command guard: Docker memory/CPU/wall timeout, process-group cleanup, orphan scan. |
| Stale process identity | Upgrade plan called PID 15335 stale, but it was the live master parent; master caught this before killing (`decisions.jsonl:414`). | Check PID command, parent, session ID and live bridge state before any process action. |

**Recommendation.** Add pre-issue checks for prompt constraints, exact file/tree identity, status and handoff format; keep executable regression cases for parsers/classifiers. Do not automate substantive policy resolution. Expected gain (INFERRED): fewer contradictory prompts, false run reuse and handoff corrections. Risk: stricter checks can block valid per-task exceptions. Verify with the listed historical cases and explicit exception rows; compare false-block rate before rollout.

## 4. Fresh-chat bootstrap design

**Finding.** There is no single current-state file: `README.md:9-18` prescribes a multi-file read; `state.json:_scope` says config only. `DRAFT_STATE.md` and `DRAFT_BOOTSTRAP_PROMPT.md` are drafts in OUT, not installed. Bootstrap is 49 lines, 760 whitespace-delimited words (`wc -l -w`), under the ~250-line limit.

**Recommendation.** Add one generated `master_chat_tasks/STATE.md` built by proposed `tools/generate_state.py` (not implemented in this research session) from `registry/tasks.json`, `board.json`, `pending.db` read-only, `decisions.jsonl`, `feedback.jsonl`, and `state.json`; include identity/authority, source map, timestamped counts, active tasks/sha, open obligations, per-task exceptions, conflict flags, and resume recipe. Budget <=2,000 words and <=12 KiB, with pointers to full sources. The draft is 44 lines/639 words. Add a stable `BOOTSTRAP_PROMPT.md` with identity, decision powers, standing feedback rules, path map, and exact resume workflow. Expected gain (INFERRED): one short entry point for a new chat, fewer state omissions. Risk: the snapshot looks authoritative despite drift. Verify by comparing its generated active tasks/counts to direct tool queries and by simulating a blank chat on a completed historical handoff; block actions when source timestamps disagree.

## 5. Token/time efficiency

**Measured.** `scripts/db_context_metrics.py` scanned all 5,607 tool parts of the identified master session (20-30 Oct). Tool `state.output` text totaled 13,131,382 characters, with 305 outputs over 10,000 characters. A targeted command-name matcher found 251 calls mentioning selected rule/config files (README, GOALS, state, decisions, feedback, KNOWLEDGE/INDEX, QC Starter/Final checklist), with 380,514 output characters (2.9% of the measured tool-output characters). It counted 128 commands mentioning decisions.jsonl, 44 README, 34 KNOWLEDGE.md; some commands may merely mention rather than fully read a file. The six summaries alone contained 16,092 words. These are **characters and whitespace words**, not billed tokens or measured wall time. The matcher omits other large rule files; 2.9% is not the total context share attributable to rules.

**Recommendation.** Use generated state and short checkpoints for startup; run `status.py <slug>`, `board.py show <sha>`, SQL status counts, `rg` and bounded `sed` instead of full dumps; write long reports to disk and return path, verdict, counts and 3-5 evidence lines. Cache a rule digest plus source hash for each active worker; re-read changed files or cited sections only, while keeping live kit checks at QC time. Expected gain (INFERRED, not benchmarked): remove several 2-4k-word compaction summaries and some repeat full-file reads; cap routine tool responses under ~2,000 characters. Risk: a terse digest omits a newly relevant clause or a file changes without re-read. Verify on a week of mirrored decisions: source-hash invalidation, audit randomly sampled omitted sections, compare quality/QC outcomes and actual input tokens plus wall time. Stop if quality worsens.

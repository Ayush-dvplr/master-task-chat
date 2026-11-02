# PLAN schema-migration-plan-repair

Phase 0 only until Ayush says "go". Design in DESIGN.md, summary in DESIGN_SUMMARY.md.
After "go": apply master changes to DESIGN.md first, then phases 1 to 9 of P2_build.md.
Package name in the repo: `migrakit`. Archive name: `repo.zip` (validator §1.12).
Scratch: /tmp/schema-migration-plan-repair-<step>-<ts>/. Logs: /tmp/opencode-logs/schema-migration-plan-repair-<step>-<ts>/.

## Rebuild round 1 (22 Oct)

Prompt: master_chat_tasks/prompts/issued/schema-migration-plan-repair/P4_rebuild_r1.md. Round notes 20261022 bind (A to E). Harness HEAD f3765e67.

Fixes, one line each:
1. Layout: environment/data/repo.zip -> environment/repo/ (package tree) + environment/ci/ (contract, graph, policies, register, feed, log, manifest, taxonomy, order); Dockerfile `COPY --chown=1000:1000 repo /app/repo`, `COPY ci /app/ci`; K1, K2, K19, instruction, solve.py, tests embedding, TRUTH sha256 list follow. Verifier stays environment_mode separate, so tests still grade the extracted /app/out/patched-repo.zip (0644/0755) and `_untrusted_command` grants read on any /app path before setpriv (template `_grant_read`, round notes C).
2. Recheck REAL rows: CL-2 four checks rebuilt so the shipped code fails them; JD-8 R7 to R13 dropped; AL-27 id-beats-alias, SET-then-UNSET in log order, token-before-planning placed in hidden worlds; Step 11 K7 and K11 added to isolated checks, K12, K15, K17, K18, N7 covered by whole-record and summary comparison; TS-17 every comparison via json.dumps(sort_keys=True); TS-24 Popen in a new session, killpg SIGKILL on return and timeout, then SIGKILL every process owned by nobody, scratch folders 0o1777; DS-27 plain lever text, no QC tool names, "Not yet measured."; IN-12 category "Software Engineering"; DS-22 floor recomputed; JD-5 (R14) left as is and listed.
3. P3: P6, X6, X7, Q1 rebuilt and checked against the shipped code; module claims compare ast with docstrings stripped (solve.py the same); new levers: correction pinned at the canonical schema, holder that fails planning keeps the identity, empty partner token line; visible graph and feed regenerated so right and reflex readings agree on them (constraints in DESIGN.md Round 1 changes).
4. Hardness: instruction drops the rule count and the restated-behaviours ask, asks for four computed figures; 19 hidden worlds (w5 each, 3 to 6 levers each, whole records and summary compared) carry about 70% of positive weight, isolated checks about 30%, shipped-data-only checks under 5%; omission rule: N7 says a partner with its own [tokens] line uses exactly that line, so an empty line means no tokens (shipped `tokens_for` falls back with `or`); decoy default: shipped `null_counts_as` and repo README say an empty null_counts_as column means absent, N2 and N3 say it falls back to [presence] explicit_null (present), and the shipped feed carries a few records on that boundary; judge rebuilt per B.12.
5. tests/test.sh keeps chown root and chmod 755; tests/Dockerfile pins litellm==1.105.0; judge.toml [judge] mode = "batched" (judge_qc G2, d9f94333).

Wrong reading each new or rebuilt check fails:
- world checks (19): every miss among their levers. STATE: prerequisites read on the received record, or visited set on schema id. TIE: fewest steps, last edge, or discovery order. SCALE: path enumeration (over the time limit). NULL: explicit null treated as absent. POLICY: empty null_counts_as column read as absent (decoy), fill mode read from the ini only. TOKENS: partner line merged with the default, empty line falling back to the default, tokens replaced after planning. CORR: corrections applied up front, no recheck before each edge, a correction pinned at the canonical schema never applied, failed counted as migrated, log order not kept. REPLAY: fingerprint after tokens or migration, raw partner string as identity, file order instead of received_seq, holder kept only when planning succeeds. FEED: one merge hop, no loop detection, run aborting on a non-JSON line, alias tried before id. REPORT: by_category keyed by status, partners sorted by id. CLI: no `python -m migrakit`, relative paths resolved against the package.
- plan_tie_first_edge_decides: the winning plan has more edges than the losing one at equal cost (fewest-steps and discovery-order readings fail).
- exec_correction_first_arrival_only: the plan revisits the pinned schema and the edge after the second arrival needs the field the correction removed (every-arrival and up-front readings fail).
- exec_correction_at_source_enables_step1: a second correction pinned at a later schema must wait for that arrival (up-front reading fails).
- pipe_rejection_codes: adds a merge-loop line (E_ALIAS_CYCLE) and a state-unreachable line (E_UNREACHABLE); one-hop and received-record planning fail.
- signature_keeps_explicit_null: also E_UNKNOWN_SCHEMA from state_signature and no mutation of arguments (K7, K11).

# PLAN for this auto run (written by the master from Ayush's words; wins over AUTO_POLICY.md)

Until: 08:00 IST (27 Oct)  [Ayush 27 Oct 01:18: start 02:00, end 08:00, 3 sessions, 2 harness]
Ayush's words (verbatim):
> lets setup the task for the auto mode
> add hardness session after probe if needed , use amx levers to improve
> add 2 hardness for Tariff and sentinel
> end time 8:30 2. run the round

## Bundles in this run (4)
pilotage-dues-reconstruction (44635de), fuel-card-settlement-consolidation (60e9db0), tariff-engine-audit-repair (15b380e), sentinel-policy-recompute (4a82a12).

## Do, in this order
1. Adopt saved sessions 44635de and 60e9db0 (finished, idle). Send each its blind-path message:
   - 44635de: @prompts/issued/pilotage-dues-reconstruction/20261026T2311_blindpath.md
   - 60e9db0: @prompts/issued/fuel-card-settlement-consolidation/20261026T2311_blindpath.md
2. Spawn 15b380e (prompts/issued/tariff-engine-audit-repair/20261026T2328_harden.md) and 4a82a12 (prompts/issued/sentinel-policy-recompute/20261026T2328_harden.md). On DIAGNOSIS READY: review against the prompt's master notes (unique fit + derived state, no more plain stated quiet rules, blind round-1 program must lose 10-30%), send go.
3. For every bundle on DESIGN READY / DIAGNOSIS READY: review, send go. On DESIGN BLIND EXACT: stop that task, Needs Ayush.
4. On BUILD READY (or harden DONE): issue ONE P13 v2 blind read, score it in Docker tests-only (recipe: copy bundle, drop judge.toml, test_output weight x2, network public, solution = blind out/app(/repo/tool) + solve.sh copying into /app; `export OPENAI_API_KEY=unused; yes | harbor run --agent oracle`).
   - Blind loses >= 5% of tests -> sync to Tasks_INPUT, `auto.py harness <bundle>` for one probe.
   - Blind ~100 -> hardening round (Ayush: "run the round") with max levers, override "AUTO override per Ayush 26 Oct 23:27: run the round".
5. Probe: tests < 100 AND final < 70 -> second probe; two valid runs -> QC (P11); QC pass/minors -> pl_ready, stop. QC fail -> one fix, QC again.
   Probe tests 100 or final > 70 -> hardening round (Ayush: "add hardness session after probe if needed, use max levers"), then blind read, then probe.
6. Max levers for every hardening round (LEVER_RULES_v3): S3 unique fit with stated no-fit/multi-fit verdict + UNIQUENESS.md; derived state from earlier records; T4 rare hidden combinations; T3 whole-doc ownership; T2 breadth >= 30 rules / 10 files / 5 formats; quiet branches only as carriers; probe-band judge only with self-check witness. Never plain stated quiet rules alone (round 1 proved they leak).

## Do not
- No push, publish, commit. pl_ready is the end.
- No new builds beyond these 4 bundles.
- No third redesign (pilotage, fuel-card).
- No edits to templates, kit, LEVER_RULES, policy; proposed changes go in REPORT.md.
- No parking (park only on Ayush's word). No deletes.
- At most 2 hardening rounds per bundle in this run; after that, Needs Ayush.

## Timed steps (the watcher delivers each at its time)
- at 07:30: no new spawns; let running steps finish; write REPORT.md.

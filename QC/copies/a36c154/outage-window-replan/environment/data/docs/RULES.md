# Rule register for the outage season replan

Each topic below is governed by one document. Where two documents disagree on a topic, the document this register names for that topic governs.

| Topic | Governing document |
|---|---|
| Assets, their region and crew type | `docs/intake.md` (data in `assets.jsonl`) |
| Season bounds and request records | `docs/intake.md` (data in `requests.json`) |
| Record checks and rejection reasons | `docs/intake.md` |
| Published plan | `docs/intake.md` (data in `published_plan.json`) |
| Control-room events and ignored lines | `docs/intake.md` (data in `control_room.log`) |
| Customer weights | `docs/replan_contract.md` (data in `customers.csv`, `risk_policy.toml`) |
| Load factors | `docs/replan_contract.md` (data in `load_forecast.tsv`, `risk_policy.toml`) |
| Crew capacity | `docs/replan_contract.md` (data in `crew_roster.jsonl`) |
| Blackout days | `docs/replan_contract.md` (data in `region_calendar.json`) |
| Incompatible pairs and precedence | `docs/replan_contract.md` (data in `network_constraints.json`) |
| Feasible season, risk-days and the objective order | `docs/replan_contract.md` |
| Moved outages and deferral reasons | `docs/replan_contract.md` |
| Output documents, keys, value types and ordering | `docs/output_schema.md` |

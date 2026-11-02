# Stage r14 - feedback and publication

Fed by: r13, r05, r10.
Feeds: nothing.

Feed the derived state back, then publish.

- `gating_rules.toml` binds an action to a state key and a required
  value under RR8.
- A surviving instance whose action is gated is withdrawn under
  `GATE_CLOSED` when the key was written by the first pass at a
  trigger strictly before this instance's own trigger and the value
  written is not the required one. A key no surviving instance wrote
  closes no gate.
- Withdrawing an instance can leave another instance without a hard
  prerequisite at or before its trigger; that instance is withdrawn
  under `PREREQ_WITHDRAWN`. Repeat until nothing changes.
- An instance withheld in r05 under `SUPPRESSED` is readmitted when
  its action is gated, the key was written before its trigger with
  the required value, and its demand fits what is left of its window
  and device pool after the survivors have drawn. A window and
  device that carried no demand in r10 still has a pool: its ceiling
  less the reserve, with no mandatory draw. Every discretionary
  survivor of r14, a kept fallback proposal included, draws its
  demand from its pool exactly once; a mandatory survivor draws
  nothing here. Readmission takes
  the withheld instances in instance id order, each readmitted
  instance drawing from the pool before the next is considered, and
  is recorded under `READMITTED`.
- This is one pass. Nothing withdrawn or readmitted here is
  reconsidered.
- Publish the remaining documents: `final_action_order.json`,
  `suppression_ledger.csv`, `next_state_snapshot.json`,
  `per_context_manifest.json`, `per_device_manifest.csv`,
  `daily_automation_manifest.json`,
  `resource_utilization_report.csv`, `terminal_action_report.md`,
  `audit_ledger.jsonl`, `run_manifest.txt` and `summary.json`.

# LEVERS: match-replay-desync-audit (Harden P9 v2 r1)

Chosen set: L1 + L3 + L4. Not a superset of any banned set (cohort, vendor, district-heat, emberforge,
schema, sentinel). Two of the three come from L1-L3.

## L3 stateful stream: running charter allowance

- Rule text: `environment/data/charter-scale.md:70-79` (cap = baseline times units the register opens under
  the charter; each charter holds an allowance the size of its cap; settled entries serving the charter draw
  on it one at a time in walk order; whole amount while covered, else what is left, which can be nothing;
  what an entry draws is its settled amount; the rest is surplus into the residual; an entry that draws
  nothing still settles; matching completes before any draw, so a cancelled entry never draws).
  `environment/data/engine-rules.md:59-60` (a settled entry draws on the allowance of the charter it serves).
  Walk order `engine-rules.md:94-95`.
- Reflex readings: per-entry cap (the pre-harden rule and the real agent's program); draw at walk time then
  refund on cancel (single pass); draw on the opening charter instead of the canonical one.
- Hidden cases: every non-shipped corpus scales entry amounts by `HELD_OUT_HEFT = 40`, so allowances bind
  (probe: 5 to 57 short draws per corpus, every reflex variant changes unit amounts and settled totals).
  Shipped data: amounts unchanged; zero short draws, every reflex variant byte-equal on shipped reports (W5).
- Checks a wrong reading fails: 3 general_scenario_*, 12 trap_*_inverse, 12 of 13 general_* (all but
  general_baseline_scale, recommendations is lever independent), mutation_window_split_moves_only_amounts.
  Each is a whole-document compare (G1), so one misread cascades through scenario_visible, every class
  document, perf_report and data_quality.
- Judge conduct: R7 (own input overrunning one allowance), R9 (own input with a reversal cancelling an entry
  that would draw).

## L4 multi-document composition: renewal at live-window openings

- Pieces: renewal sentence `engine-rules.md:44-45` (first tick of every live window renews each allowance
  before any entry at that tick draws; degenerate window renews nothing); allowance size
  `charter-scale.md:70-72` with inputs from `roster-register.csv` (opening ticks, units opened per charter);
  window bounds and liveness `tick-schedule.csv`; walk order `engine-rules.md:94-95`. Four files, one plain
  sentence each, none beside the data it governs.
- Reflex readings: one allowance for the whole walk; renewal at every window (dead windows too); renewal at
  window close; size from surviving units rather than units the register opens.
- Hidden cases: heavy corpora bind inside several windows; `split` tweak (mutation test) inserts a live
  window opening on the first short-draw tick, so only the amount family moves.
- Checks: same whole-document set as L3 plus mutation_window_split_moves_only_amounts.
- Judge conduct: R8 (own input where an allowance is spent before a live window opens and an entry at or
  after that first tick draws).

## L1 green control

- Truthful control descriptions: `calibration.md:13` table column "the control reads"; CTRL-A..I read decode
  stages, CTRL-J reads the cadence class of every surviving unit (tick side), CTRL-K the upkeep target.
  Header seal counts entries; reconciliation identity (`engine-rules.md:79-81`) holds under any draw rule.
- Reflex reading: "every control reproduces and the residual reconciles, so settlement is right". All of
  them stay green under every L3/L4 misread because zero-draw entries still settle (ticks still count).
- Graded values above that layer: unit amount_total, kind_totals, class amount_total, charter stocks (via
  settled kind-one flows), settled_total, conservation_residual.
- Checks: same whole-document set; mutation_cadence_modulus_moves_only_classes proves the control-side
  family moves alone when only cadence_modulus changes.

## Interaction

L3 decides how much each entry draws, L4 decides when the pool refills, L1 hides both from every self-check
the shipped material offers. A solver that fixes one but not the other still fails every hidden whole
document. Reflex replay (real agent program and minimally adapted copy) earns 20/160 = 0.125 locally (P12 v3 r2, grammar published; was 18/158 = 0.114 in P12 r1). Cost table: COST_TABLE.md.

## P12 v3 r6 effect (c45716e)

| change | L1 | L3 | L4 |
|---|---|---|---|
| F1 decoded-field clause (report-schema.md:13-15, engine-rules.md:79-80, 97) | unchanged: residual identity still holds under any draw rule | unchanged | unchanged |
| F2 decoy negative | unchanged | unchanged | unchanged |
| F3 G5 exact-match sentence | unchanged | unchanged | unchanged |
| N1-N7 instruction deletions | unchanged: discoveries still made from the shipped notes | unchanged | unchanged |

Trap survival: every single-lever variant earns exactly what it earned before (WORK/trap/run_before_v3r6.log vs run_after_v3r6.log).

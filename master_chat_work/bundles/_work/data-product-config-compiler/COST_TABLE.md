# COST_TABLE: data-product-config-compiler (G10), Harden round 1

Measured 25 Oct 2026 01:20 IST by `WORK/cost_table.py` on the real `tests/test_output.py`
(35 checks, positive weight P = 120). Each wrong reading is an edit on the repaired oracle tool
(`WORK/score.py`), delivered as tool.zip and graded by every check. Overall = 0.5 x tests share
+ 0.5 x rubric 0.90.

| lever | wrong reading | predicted alone lost | measured alone lost | predicted all-but-this overall | measured all-but-this overall | predicted one-fact-wrong lost | measured one-fact-wrong lost |
|---|---|---|---|---|---|---|---|
| NL-1 | team on D from the first owners.csv row covering D, in file order (H3; the shipped tool and probe program) | 35.8% | 31.7% (38/120) | 77.1 | 79.2 | ~4% | 4.2% (latest start among covering rows only: date_shift) |
| NL-3 | caps re-applied by water-filling the whole remaining quota from scratch each round (H7 re-entry) | 31.7% | 31.7% (38/120) | 79.2 | 79.2 | small | 27.5% (at most two rounds) |
| NL-4 | text integers and booleans read leniently: `int()` accepts `+4` and non-ASCII digits, any non-true word is false (H1) | 35.8% | 59.2% (71/120) | 77.1 | 65.4 | partial | 20.8% (`str.isdigit` accepts non-ASCII digits) |

Every counted lever alone costs >= 25% of positive test weight (lowest 31.7%). The G10
all-but-this < 70 row holds only for NL-4 (65.4); NL-1 and NL-3 sit at 79.2, which follows the
master's 25-40% per-lever target; the combination is what holds the score down.

Other rows: oracle 100% (overall 95.0); all three wrong 20.0% tests (overall 55.0); only NL-1
right lost 67.5% (61.3), only NL-3 right lost 71.7% (59.2), only NL-4 right lost 60.8% (64.6).
Background rules kept from the build (not counted): LV-CC-1 alone 65.0%, LV-CC-2 83.3%,
LV-CC-4 69.2%.

Differential fuzz on the probe agent program (OUT/fuzz/cf_out_r3.jsonl, 320 valid corpora):
program differs on 96.6%; reference reflex variants differ NL-1 88.0%, NL-3 81.8%, NL-4 100%.

## One-fact-wrong edits
- NL-1: the latest start is taken among rows covering D only, so an owner whose latest row ended
  before D keeps the older team. Main hidden tier plants only covering later rows, so only the
  shifted tier (date_shift) fails.
- NL-3: the re-share stops after two rounds. Fails the quota rows where a cap binds only in round
  three or later (config/dev quota hard, summary, rescale, capped config/prod, readonly).
- NL-4: `str.isdigit` instead of ASCII digits; `+4` is passed over correctly but fullwidth digits
  are read. Fails the dev/prod rows that carry the hidden env plants.

CL-4: NL-1 plants keep the old and new team at the same weight, so a wrong team moves team,
settings and deploy rows but not the quota denominator; one wrong fact costs about one fact.

## Lessons for the master
- A lever whose plants avoid the shared denominator lands at 25-35% alone | no change: COUPLING stays on NL-3 only by design.

# Final reply — hangar-check-replan (sha e8e9c82)

## What I built

`derive_report.py` (stdlib only, Python 3), placed at `app/derive_report.py` and copied to `out/derive_report.py`. Interface exactly as the instruction states:

```
python3 derive_report.py --data <data folder> --out <output folder>
```

with the documented defaults (`/app/environment/data/`, `/app/out/`). It reads nothing outside the data folder and writes nothing outside the out folder; a missing or unreadable input makes it exit non-zero with a stderr line naming that file.

Pipeline:

1. **Input layer.** A small TOML reader for `fleet_limits.toml`; CSV readers that keep the physical line number of every request row (header = line 1); a JSONL calendar reader that ignores rows outside the season; a JSON reader for `check_types.json`; and a WordprocessingML reader built on `zipfile` + `ElementTree` for the two `.docx` files. The Word reader resolves the main document part through the package `officeDocument` relationship, drops `w:del`/`w:moveFrom` content, keeps `w:ins`/`w:moveTo`, and resolves `mc:AlternateContent` by taking the first `mc:Choice` whose `Requires` prefixes all resolve to the main `w` namespace (falling back to `mc:Fallback`), with namespace scope tracked per element. Tables are located by the text of their first header cell.
2. **Screening.** Only rows whose `season` matches `fleet_limits.season` and whose `status` is `OPEN` are considered. Rejections apply in the documented precedence `duplicate_request → unknown_base → unknown_check_type → unknown_tail → retired_tail → bad_date → bad_duration → no_published_start`, first reason wins; duplicates are judged against every earlier row read, and the earlier row is the one kept.
3. **Calendars.** Per base: calendar `CLOSED` days plus every day of each closure row of the disruption notice are closed days; `NO_START` days block only a start. Precomputed per window length: which start days give a clean window, and the next valid start at or after any day.
4. **Planning.** The whole lexicographic objective — first term, second term, third term, then the start-day list and the finish-day list in `request_id` order — is folded into a single large integer with a radix per level that exceeds any possible sum of the levels below it. That keeps the objective additive per check, so a dynamic program over (set of checks placed on the line, finish day of the last one, overtime shifts used) with Pareto pruning on those three numbers finds the exact optimum per base line for every feasible overtime total. For a given earliest day only two candidate starts can ever be optimal — the first legal one, and the published start when it is later and legal (the only reason to wait is to save one point on the third term) — which keeps the search small. The four base lines are then combined by a min-plus convolution over the single fleet overtime pool, and the best decisions are recovered from backpointers. Checks the plan leaves out are deferred, with reason `no_slot` when no compression at all fits on an otherwise empty line of their base and `plan_trade` otherwise.
5. **Settlement and reports.** The four `allowance_shifts` grants are summed into one fleet allowance and spent after the plan is fixed, one scheduled check at a time, widebody then narrowbody then regional, earlier `due_date` first, smaller `request_id` to break a tie. Settlement never influences which plan is chosen; the second term counts the gross `overtime_cost`. The five output files are then written straight from the decisions, with every base and both segments always present even when they hold no open request.

Outputs written: `out/check_plan.json`, `out/regions/region_{north,south,west,east}.json`, `out/segments/segment_{commercial,public}.json`, `out/plan_summary.json`, `out/data_quality.json`.

## What I checked

One run on the shipped data (`--data environment/data --out out`): exit 0, no stderr, **0.10 s** wall clock against the 60 s limit. All eight output files exist with the documented keys.

An independent self-check (`work/selfcheck.py`, 0.11 s) re-derived the inputs from scratch and verified, per check and in aggregate: exact field set of every plan row; window length equals duration minus compressed days; start on or after the effective available day (notice override applied, clamped to season start); start never on a closed or no-start day; no closed day anywhere inside a window; no two checks of a base overlap; every finish inside the season; recomputed `overdue_days`, `overtime_shifts`, `compress_days` limit and `moved` flag; deferred rows zeroed with a valid reason; fleet overtime within the pool; the allowance spent greedily in the documented order; the four per-check cost identities; the three plan terms recomputed from the rows; every region and segment aggregate and its agreement with `plan_summary.json`; and the `data_quality.json` list and counts against a separate screening pass. Result: **PASS, no problems.** No crash occurred, so nothing was fixed afterwards.

## Key figures (season 2027A, 2027-03-01 … 2027-06-28)

- 29 in-season open rows → **21 planned**, **8 rejected** (exactly one per reason, lines 32, 716, 855, 2853, 3321, 3380, 3628, 4243).
- **20 scheduled, 1 deferred** — `Q68307` (North, narrowbody D check, 16 days, available 2027-06-19) cannot finish by season end even fully compressed, so it is deferred with reason `no_slot`.
- Plan terms: **first 528, second 5290, third 11** (11 checks moved off their published start, the deferral included).
- Overtime: **64 of the 64 shift pool used** — the pool is binding; by base North 28, East 14, West 12, South 10.
- Settlement: allowance granted **74**, used **64**, left **10**; gross overtime cost **960**, allowance credit **960**, **settled overtime cost 0** — the fleet allowance covers all overtime of this plan.

# A_ceab1cf6 — budget-envelope `task-ctl` CLI repair (Debugging)

Recorded (pass_summary.json / report.json): overall 65.47, tests 50.0 (38/76 positive weight), rubric 80.95.

## Verdict: GENUINE (36 of 38 lost points are wrong values; 2 points are format/replay gates)

## Artefact screen
- result.json `exception_info` null; agent 06:05:40-06:18:11Z (12.5 min) of a 7200 s budget; no timeout.
- verifier/test-stdout.txt holds only `reward: 0.6548`; no traceback, no Permission denied.
- All 23 artifacts present in `artifacts/app/out/` (ls), incl. tool.zip; held-corpus derive c1 and c3 PASSED, so the delivered tool runs as `nobody` under the harness (`tests/test_output.py:851` `_run`, setpriv, 60 s).
- No negative fired (hardcoded_answers -5, nested_or_dynamic -3, network -3 all "failed" = not triggered).

## Failed checks (38 pts)
| check | w | cause | kind |
|---|---|---|---|
| profile_dev_matches | 5 | agent dev avg/max/vbv 1400/1925/8247 vs expected 1425/1959/8392 (`tests/test_output.py:135-148`) | wrong VALUE (lever A) |
| profile_prod_matches | 5 | 2700/3712/19614 vs 2725/3747/19799 | wrong VALUE (lever A) |
| profile_delta_report | 3 | deltas computed from the wrong profiles | wrong VALUE (lever A cascade) |
| held profiles c1/c2/c3 | 15 | same scale order on held corpora (TRUTH.md:36 'scale order (c1 dev)') | wrong VALUE (lever A; c2 also lever B) |
| bitrate_ladder_is_correct | 1 | carries dev/prod rows (`:1222-1233`); agent csv dev 1400 | wrong VALUE (lever A cascade) |
| ladder_solution_is_correct | 1 | embeds both profiles (`:1236-1244`) | wrong VALUE (lever A cascade) |
| ladder_ordering_is_correct | 1 | dev/prod avg+max (`:1254-1268`) | wrong VALUE (lever A cascade) |
| held_c2 derive | 5 | width 1745 must become 1746 (TRUTH.md:36); agent rounds half-even to 1744 | wrong VALUE (lever B) |
| report_matches_contract | 1 | replay gate, see below | GATE (stricter than contract) |
| derivation_provenance_is_correct | 1 | file named in attribute, test reads element text | GATE (format unstated) |

### Lever A — profile scale applied to the finished average (31 pts)
- Agent tool `cli.py:503` (agent tool.zip) `scaled = round_half_even(config["avg_bitrate_kbps"] * int(delta["avg_scale_permille"]), 1000)` — scales the already clamped and quantised main avg (2350).
- Reference scales the pre-clamp average, then clamps, then quantises (TRUTH.md:11 defect 5: 'Profiles are scaled after granularity quantisation instead of scaling the pre-clamp average first, then clamping, then quantising.').
- Only rule location: `instruction.md:5` '... applying each profile's average-scale, priority, cycle-span, and reserve deltas in the documented order, which applies the scale before granularity.' No data file states the profile order (grep for pre-clamp/scale/before/avg_pre in data found only `avg_formula.edn2:2` defining avg_pre; `output_contract.md:92-103` gives shapes only).
- Agent believed it complied: final message (trajectory step #44) '... now from env_overrides.json, scale→clamp→granularity order'. It did apply scale→clamp→granularity, but to the finished main value, not avg_pre. The sentence does not name which average is scaled → two readings (INFERRED IN-16 exposure).
- Shipped data separates the readings (1400 vs 1425), but no shipped worked answer exists for profiles (sample_config_*.json are 'context only - do not copy'), so the agent had nothing to compare against.

### Lever B — width evening rule in a data rule element (5 pts)
- `environment/data/width_even.html2:107` `<rule step="after-width-rounding" when="width % 2 == 1" apply="width + 1" status="CANONICAL"/>`.
- Agent `cli.py:372` `width = quantize_nearest(width_pre, 2) if band_width_even(band) else width_pre` (half-even nearest), and `band_width_even` `:149-157` reads only `<w>` rows, never the `<rule>`.
- Shipped band width is already even (TRUTH.md:19 'On the shipped corpus alone, defects 1, 2, 3 and 8 change no graded value'), so only held c2 separates. Agent read the file at step #11 with `head -c 1800`; line 107 lies beyond that (INFERRED).

### Gates (2 pts)
- report_matches_contract: `_replay_transcript` `tests/test_output.py:1038-1081` replays only init/set/validate (`_REPLAYED` :1027) and requires the replay to rebuild `config.json` byte for byte (:1076-1077). Agent transcript: init → `/app/work/seed.json`, set on seed.json, validate on `/app/out/config.json` (config built by `derive`, not replayed). Contract `output_contract.md:54-57` asks only that the transcript 'includes the init, set, validate, and export-report subcommands, and every returncode is 0'; instruction.md:5 'a truthful command transcript'. The rebuild requirement is not written → test stricter than contract (TS-19 shape).
- derivation_provenance: test `:1373` reads `child.text`; agent wrote `<source field="avg_bitrate_kbps" file="avg_formula.edn2"/>`. Contract `:157-158` 'source children name the data file each field was read from' — text vs attribute not stated (silent format).

## Why tests = 50 (not <30, no exact-reason duty), single gate?
No single gate zeroes many tests; the biggest block (31) is one wrong value cascading through every artifact that embeds profiles.

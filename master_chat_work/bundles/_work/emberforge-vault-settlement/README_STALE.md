# Stale build scripts (harden round 2, 22 Oct 2026)

Round 2 edited the bundle directly. These scripts in this folder still emit the round 1 format (calibration slice, `calibration_controls.json`, `example_workshop_report.json`, isolated lever seasons) and must not be run against the bundle:

- `gen_tests_tail.py`, `select_draws.py`, `seasons_r1.json`, `score_p3.py`, `underiv.py`, `check_exact.py`, `count_plans_lower_bound.py`, `TRUTH.src.md`.

Still valid: `embed_rulebooks.py` (generic: re-embeds every `environment/data/*.md` into `RULEBOOK_TEXTS`). The source of truth for `environment/data/` is `tests/test_output.py` itself: `python3 tests/test_output.py <dir>` (with rewardkit importable) writes the visible season, and round 2 checked that its output equals `environment/data/` byte for byte.

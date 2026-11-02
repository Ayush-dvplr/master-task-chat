# S3 Running Ladder Baseline

Resolved matches are processed left to right within each frozen tier-server
stratum in ascending `match_key` order against a single running baseline that
starts at the season profile `base_p`. The effective probability is
`p_eff = clamp(0.85 * p_raw + 0.15 * previous_baseline)` and the new baseline
becomes `p_eff`. No match resolves in isolation. `p_raw` is clamped to
[0.000001, 0.999999] before use.

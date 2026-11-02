# emberforge-vault-settlement P13 blind r1 (1cd546e) score

Bundle state: harden lp1 r1 (e215748), no changes since. Blind data == bundle data.
Scored offline in tests/Dockerfile image, judge removed, /app/data + /app/out baked into image.

tests: 18.75 / 54 positive (34.7%), reward 0.1736 (tests share only). No negative fired.
Gate: PASS (tests < 100) -> QC rerun, then trajectory.

Lost: every whole_* record on 4 unseen seasons except allocation (0.75); live_window_refusals
(UNCREDITED_SALVAGE, L6 window lever); structure_program_takes_directories.
Kept: unit_charge_season_total, cap_release_closures, both mutations, canonical serialisation, reruns.

Caveat: structure_program_takes_directories errored in this offline setup (grader rename of
/app/data -> EXDEV/EBUSY), so that 1 point is a setup artifact, not a verdict. With it: 19.75/54.

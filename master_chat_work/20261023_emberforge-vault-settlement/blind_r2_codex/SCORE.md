# emberforge-vault-settlement P13 blind r2 (0c22dae), Codex 6 Sol high

Bundle tree d56ffd6edaeb (harden lp1 r1), data identical to blind dir. Same offline method as blind r1.
tests: 18.75 / 54 (34.7%), reward 0.1736, no negative fired. Gate: PASS.
Identical check-by-check to blind r1 (Opus 5.5): every whole_* record wrong on 4 unseen seasons except
allocation 0.75; live_window_refusals (L6) failed; unit charge, cap closures, both mutations passed.
Method check: oracle solution scores 53/54 in this setup; the only lost point is
structure_program_takes_directories (offline /app/data rename EXDEV artifact), so blind losses are real.
Safety: Codex Full Access; 9 tool calls, all paths inside the blind dir, no network/git/docker/pip;
bundle trees unchanged vs 15:13 baseline (only _work/district TODO/LOG changed, by 8cd7597).

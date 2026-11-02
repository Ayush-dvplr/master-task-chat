# TODO harden r3 c510591 (prompt master_chat_tasks/prompts/issued/flood-repair-portfolio/20261101T1752_harden.md)
R=/Users/mac/Desktop/Terminal Bench/_runs/20261101/flood-repair-portfolio/harden3-20261101T1755
OUT=/Users/mac/Desktop/Terminal Bench/master_chat_work/20261101_flood-repair-portfolio/harden_r3
W=WORK/h3_a3 ; older r2 TODO/LOG copied to TODO_harden_cb8dada.md / LOG_harden_cb8dada.md

## Phase 0
- [x] rename (opencode ses_e68eeba3dffeJSsY5Ua6xIdeml), read rules, fingerprints OK, kit HEAD 5574d77e, tree 931f8f817d76
- [x] read bundle docs instruction, contract, generator bookgen.py, solve.py
- [x] read judge.toml + test layout
- [x] read a3 program derive_report.py vs solve.py; list candidate DIFF points (none documented; only unstated corners: dup register keys first/last wins, whitespace-only lines, BOM, ':' INI, non-ascii bytes)
- [x] fuzz harness h3_a3/fuzz3.py; targeted run done (0 DIFF)
- [x] gen-branch fuzz 300 seeds x profiles random,faults,ties,large,fixed (wait START=yes)
- [x] planted-effect check for targeted cases (ref output differs from base)
- [x] OUT/TRIP.md
## Phase 1
- [ ] prototype hidden books (proto/), kill table in Docker
- [ ] judge rebuild draft; grade a1/a3 low/mid/high
- [ ] instruction time-budget sentence
- [ ] OUT/DESIGN.md -> DESIGN READY / NO CORE; stop

## Outcome
- [x] NO CORE (0 DIFF); Phase 1 build items skipped per prompt; DESIGN.md = NO CORE note; report + result json written

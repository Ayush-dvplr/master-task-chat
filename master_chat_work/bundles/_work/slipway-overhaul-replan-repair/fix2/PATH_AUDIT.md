# Verifier path audit (b20fdca, tests/test_output.py after fix)
Verifier runs as root; engine runs as uid 65534 (`_demote`), one at a time under `_RUN_LOCK`, own session, killed by `_stop_untrusted`.
mkdtemp creates 0700 root dirs with O_EXCL random names; root umask 022 makes files 0644.

| path (creator, line) | holds | owner / mode | run user read | run user write | change |
|---|---|---|---|---|---|
| /tmp/slwopt-private-* (`_private_corpus` :5031) | private round papers every reference is built from | root 0700, kept | no | no | none (already private) |
| /tmp/slwopt-expected-* (`_reference` :5061, `_held_reference` :5232) | 25 expected documents of a round | root 0700, removed in `finally` before return | no | no | was `_scratch("reference")`/`_scratch("held-reference")` 0777, files 0644, never removed |
| /tmp/slwopt-corpus-*, slwopt-held-* (`_public_copy` :5040) | public round the engine reads (graded input) | root, filled at 0700 then `_seal` 0755/0644 | yes (by design) | no | was `_scratch` 0777 while filled (writable window) |
| /tmp/slwopt-engine-* (`_engine_root` :5139) | extracted delivered engine | root, filled at 0700 then `_seal` 0755/0644 | yes (must import) | no | was `_scratch` 0777 while filled |
| /tmp/slwopt-shipped-* (`test_delivered_shipped_suite_unedited` :5340) | shipped test_visible.py compared against delivered | root 0700, removed after read | no | no | was `_scratch` 0777, never removed |
| /tmp/slwopt-renamed-*/papers_under_another_name (:5761) | round under another name (graded input) | root, `_seal(parent)` 0755/0644 | yes (by design) | no | parent was 0777 (entry could be renamed/replaced) |
| /tmp/slwopt-<tag>-*/destination (`_drive` :5172) | engine output | parent root 0777 (engine must create destination) | yes | yes | output now read inside `_RUN_LOCK` after `_stop_untrusted`, so no later run can rewrite it before root reads it |
| /tmp/slwopt-<tag>-home-* (`_drive` :5173) | HOME/TMPDIR/cwd of the run | root 0777 | yes | yes | none (holds nothing graded) |
| /tmp/slwopt-ambient-* (:5772) | cwd bait for the training-corpus detector; data/ sealed 0755/0644 | root 0777 | yes | yes (parent) | none: bait for a negative detector; tampering can only make that detector stay silent, which an honest engine also does |
| /tmp/slwopt-withdrawn-* (`_write_withdrawn` :3716) | withdrawn publication while writing a corpus | root 0700, removed | no | no | none |
| /logs/verifier (test.sh:7) | reward.json | root 755 | yes | no | none |
| /tests (test.sh:8) | verifier code | root, go-rwx | no | no | none |
| /app/out (OUTPUT_ROOT) | agent deliverables | agent | n/a | n/a | none (agent's own output) |

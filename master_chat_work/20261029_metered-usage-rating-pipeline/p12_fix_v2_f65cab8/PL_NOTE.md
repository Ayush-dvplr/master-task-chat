# PL note: metered-usage-rating-pipeline, fix v2 (f65cab8)

False positives: none. The one finding (G05-1, list order of missing files) was real: a program that prints a line for every missing file passes all 413 pre-existing points and fails only the two new checks.

Fix: two new hidden checks. One removes three reference files at once, one removes two collector files at once. Each wants only the earliest file in the contract list named, and no line for the later ones. Weight 3 each; test points now 419.

Carried count warning kept: 112 checks is above the count hint, but there is no cap (Ayush decision). Carried encoding rebuttal: collector_south.txt is Latin-1 by contract, so the binary-skip warning is a tool limit. Earlier decisions on the handler criterion and malformed-input forms are unchanged; see KEPT.md.

Unsure: none.

Note: the five collector names are in alphabetical order in the contract, so a checker that walks files by name cannot be caught on collectors alone; the reference-file check catches it.

Verification (tests-only): oracle 1.000 three times, owner-only 1.000, nop 0.000; PRECHECK CLEAN; trap losses unchanged. BUNDLE and the authorized Tasks_INPUT copy match at tree 396efb9b4952. Ready for the master's P11 v3 recheck; no paid model run was made here.

## Lessons for the master

- Record the count warning without merging independent checks | no change: the playbook already says there is no count cap

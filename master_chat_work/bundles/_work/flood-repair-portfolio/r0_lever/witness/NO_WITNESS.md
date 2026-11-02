# No Paid-Program Difference
Status: NO CORE. No paid-program differing input was found in the measured H1-H3 books.
All nine documents match the independent verifier ledger and solution output in every book.
Paid rows: results.json entries paid_a4/H1, paid_a4/H2, paid_a4/H3; each difference=null and 25/25.
The saved inputs are ../books/H1, ../books/H2 and ../books/H3; metadata is ../H1.meta.json through ../H3.meta.json.
No smallest differing witness exists among these measurements, so no paid/oracle differing lines can honestly be cited.
Source explanation: paid derive_report.py:376-377 returns None at the combination cutoff; :353-354 calls branch_and_bound.
Its :693-697 returns an incumbent only on internal Timeout; the cutoff alone does not imply a greedy answer.
The independent oracle is BUNDLE/tests/test_output.py:1179-1277; selected ids are checked at :1512-1519.
The required three saved differences and 44/108 lost points are absent; no timeout substitution or redesign was attempted.

## Lessons for the master
A changed algorithmic branch is not a wrong-output witness | no change: R0 already requires measured differences.

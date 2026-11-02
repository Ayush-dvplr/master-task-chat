# PL note: district-heat-flex-procurement, QL round 1

Fixed (9 of 11 findings): the tie check now runs on an extract that really has a tie; the "reply with a short report" sentence is gone; the hidden extracts now use their own units and code names, leave out an adder option, drop profile rows, share one allowance across two regions of an event, and hit the exact "equal" edges for allowances and grant claims; the judge's credit-and-cap item is two items; the import penalty now fires only on modules outside the Python standard library.

Kept:
- F9, 66 test checks (warn above 35): each check grades a different property or a different extract. Merging would remove cases that separate right from wrong programs. Same as the earlier ruling (option A, 27 Oct); the check list did not change since the last QC.
- F11 (out of scope, suggestion), the agent program is started without a cleaned environment: a suggestion, not a rule. The checker already copies the workspace, applies a time limit, kills on timeout and reads outputs from files (TS-28, all four defences in place).

False positives: F9 (above) is the only one; it repeats a finding already ruled on, on bytes that did not change.

Questions (UNSURE): none.

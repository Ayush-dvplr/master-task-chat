# PL note: depot-charge-plan, fix round 1 (efdb667)

Status: paused. After we wrote the meter rule out in full (as QC asked in DS-21) and gave one shipped depot a shifted meter, a careful program that tries all 96 shifts and plans with an exact min-cost flow scores 191 of 191 test points. The task's hard part is now reachable by a plain search. We are asking whether to park the task or make one more design change.

False positives: none.

Kept warnings:
- TS-23 (45 checks, kit says at most 35 is a warn): kept with the count. Every check reads a different corpus or document; merging would only hide points. Kit 03_Tests_QC.md:62.
- JD-16 (R16 /app/data writes could be a test): kept R16. The verifier never receives /app/data (task.toml artifacts list only /app/out files; the verifier runs separately), and the kit gives scope over undeclared paths to the judge (04_Judge_QC.md:93 item 4).
- Oracle run x3 instead of x5: acknowledged by Ayush.

Unsure questions: none.

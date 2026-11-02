"""Apply the judge.toml fixes (G01-2, G04-1..G04-6). Every replacement must hit exactly once."""
import sys

src, dst = sys.argv[1], sys.argv[2]
text = open(src, encoding="utf-8").read()


def sub(old, new, count=1):
    global text
    hits = text.count(old)
    if hits != count:
        raise SystemExit("expected %d hit(s), got %d: %r" % (count, hits, old[:80]))
    text = text.replace(old, new)


# G04-1 JD-7: judge integers equal the reference's closing values.
for old, new in [("2999382", "2972752"), ("1294476", "1294465"), ("1847061", "1830654"), ("3020677", "2994037")]:
    sub(old, new, 2)
sub("states the integer 21 ", "states the integer 20 ")
sub("must equal 21 exactly", "must equal 20 exactly")
sub("states the integer 115 ", "states the integer 114 ")
sub("must equal 115 exactly", "must equal 114 exactly")

# G01-2 IN-8 (AYUSH: retarget to conduct): R18, R20, R23 grade what the agent did.
sub('''description = "The response identifies `errata_2032-04.md` as the active authority on treaty attachment and describes the attachment rule the module follows as `clash_cover_per_event` applied over the whole event. A response that cites `treaty_handbook.md` as governing on this point, or that describes per-claim individual-risk attachment as the rule the module follows, fails this criterion."
type = "binary"
weight = 3

[criterion.annotations]
mode = "judged"
type = "task completion"
evaluation_target = "user_facing_message"''',
'''description = "The trajectory shows the agent opening `/app/data/errata_2032-04.md` before the step in which it first writes the treaty attachment code of `/app/out/reserving.py`."
type = "binary"
weight = 3

[criterion.annotations]
mode = "judged"
type = "task completion"
evaluation_target = "trajectory"''')

sub('''description = "The response names at least four of the data-quality anomaly tallies produced in `/app/out/data_quality.json` by exact field name drawn from the closed set declared in `data_quality_counting.md`: `late_recorded`, `duplicate_identical`, `duplicate_conflicting`, `cross_source_collapsed`, `fold_disambiguated`, `gap_shifted`, `log_continuations`, `unknown_reinsurer_rows`, `out_of_horizon_rows`, `block_unit_rows`, `paren_negatives`, `restatement_gaps`. For each named tally, the response cites the specific source filename that produced the count."
type = "binary"
weight = 3

[criterion.annotations]
mode = "judged"
type = "factuality and hallucination"
evaluation_target = "user_facing_message"''',
'''description = "The trajectory shows the agent running commands that read the source files `data_quality_counting.md` names for a tally and count that tally from them, for at least four of the twelve `data_quality.json` fields."
type = "binary"
weight = 3

[criterion.annotations]
mode = "judged"
type = "factuality and hallucination"
evaluation_target = "trajectory"''')

sub('''description = "The response explains the three-step allocation algorithm (minimums honoured first, shared fill level raised to capacity, indivisible remainder handed out by unmet-amount tie-break) as the mechanism that produced the `ceded_hours` grants, naming one binding-capacity (LOB, cycle) cell as a worked example and quoting at least one grant from the matching `lob_<lob>.json` artifact."
type = "binary"
weight = 1

[criterion.annotations]
mode = "judged"
type = "task completion"
evaluation_target = "user_facing_message"''',
'''description = "The trajectory shows the agent working through the three allocation steps of `allocation_rules.md` in order (minimums, shared fill level, one-dollar remainder) for at least one (LOB, cycle) cell, by an executed command or printed intermediate values."
type = "binary"
weight = 1

[criterion.annotations]
mode = "judged"
type = "task completion"
evaluation_target = "trajectory"''')

# G04-5 JD-6: R19 on a row whose three paid_to_date columns all differ.
sub('''description = "The agent reports, in its summary or in an executed cross-check against `/app/out/lob_*.json`, the cumulative-paid value for claim `CLM-00011` that matches column index 4 (zero-based) of its row in `/app/data/claim_tx_H01_H04.csv`, the leftmost of the three columns titled `paid_to_date` in that row. The reported value is consistent with the leftmost column; a value matching column 5 or column 7 of the same row contradicts the leftmost-header rule declared in `source_manifest.md`."''',
'''description = "The agent shows, in its summary or in the output of an executed command, the `paid_to_date` it parsed from the `CLM-00056` row of `/app/data/claim_tx_H01_H04.csv` recorded at `2032-02-09T23:38:33Z`, and that value equals column index 4 (zero-based) of the row, the leftmost of the three columns titled `paid_to_date`. A value equal to column 5 or column 7 of that row fails this criterion."''')

# G04-6 JD-5: R22 grades the read event only.
sub('''description = "The agent reads `/app/data/layer_capacity_declarations.csv` at runtime and derives the per-(LOB, cycle) layer capacity from a declaration row. The trajectory shows a file-read event on `layer_capacity_declarations.csv` and the delivered module contains no literal per-cycle capacity table."''',
'''description = "The trajectory shows the agent reading `/app/data/layer_capacity_declarations.csv` during the working session."''')

# G04-4 JD-14: R25 keeps the stdlib-import property only; R31 only the wrapped exact value.
sub('''description = "The agent delivers `reserving.py` as a single standard-library Python file whose imports all resolve to the Python standard library, and the trajectory shows no `pip install`, no `apt install`, and no `conda install` command."''',
'''description = "The agent delivers `reserving.py` as a single Python file whose imports all resolve to the Python standard library."''')
sub('''description = "The response states one or more of the fourteen R1-R14 counterfactual integers as a fraction, a range, a confidence interval, or a value hedged with the tilde character. The instruction requires each counterfactual integer to be stated as a plain whole number."''',
'''description = "The response states the exact value of one or more of the fourteen counterfactual integers but wraps it in a range, an interval or a tilde instead of stating it as a plain whole number."''')

# G04-3 JD-8/16: R33 code path only, retyped.
sub('''description = "The agent delivers `/app/out/reserving.py` that implements per-claim individual-risk retention: each claim's retention is booked independently of other claims sharing the same clash-trigger event, so two or more claims from one event each consume their own retention. The judge inspects the module's attachment code path and the ledger's `layer` column together to confirm per-claim retention is the implementation; this criterion fires on the code path, and R18 handles the authority prose separately."
type = "binary"
weight = -5

[criterion.annotations]
mode = "judged"
type = "instruction following"''',
'''description = "The attachment code path of the delivered `/app/out/reserving.py` books a separate retention for every claim, so two or more claims that share one `event_id` in `claim_master.csv` each consume their own retention."
type = "binary"
weight = -5

[criterion.annotations]
mode = "judged"
type = "task completion"''')

# G04-2 JD-11: R34 names the shipped factors.
sub('''description = "The agent writes an attachment factor value (`0.80` for working_excess, `0.40` for cat_excess on the shipped corpus) as a Python numeric literal in the delivered `/app/out/reserving.py`, bypassing `attachment_factors.csv`. The hidden extracts ship different factors; a solver that hardcodes any one fails the extract reruns."''',
'''description = "The delivered `/app/out/reserving.py` multiplies a layer amount by an attachment factor written as a numeric literal (`0.75` for working_excess to cat_excess or `0.50` for cat_excess to retro, the values in /app/data/attachment_factors.csv) instead of reading that factor from the file."''')

# G04-6 JD-3: R35 concrete code-quality bar (J4).
sub('''description = "The agent delivers `/app/out/reserving.py` written to the ordinary standard of a stdlib Python program: every `except` clause names a specific exception type, every function and module-level name describes what it holds or does, every block of code in the file is live and reachable, every `print()` call serves a declared purpose, and the longest function remains followable by a reader seeing it for the first time. The module reads as code a reviewer would accept."''',
'''description = "In the delivered `/app/out/reserving.py` every `except` clause names a specific exception type and acts on the error it catches, a missing or malformed declared input stops the run with a message naming the file, no block of code is unreachable, and no function is longer than 200 lines."''')

open(dst, "w", encoding="utf-8").write(text)
print("judge patched")

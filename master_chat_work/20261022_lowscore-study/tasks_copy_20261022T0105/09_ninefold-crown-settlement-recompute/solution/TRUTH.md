# TRUTH.md - ninefold-crown-settlement-recompute

## Defect

Nothing under `environment/data` is broken and nothing is redacted. What is
withheld is the derivation: the agent holds 58 working papers of one Ninefold
Crown card event and has to rebuild the settlement the hall software got wrong,
then deliver 31 byte exact documents and the program that produces them. The
papers record what the hall did, and the hall was wrong: it ordered the pairing
pool on recorded match points alone, ignored the membership standing register
and the expulsion notices, placed a status change that landed exactly on a round
boundary in the round that closed, widened the score band by one, and let a
share of boards through in breach of the pairing constraints. The settlement is
recomputed from that evidence, never copied from it.

1. **(focal)** The round loop is a single chain. Stage P07 pairs a round on the
   running points stage P09 of the previous round left behind, stage P08 screens
   the recorded boards of the round against the admission levels stage P07 just
   produced, and the voids stage P08 declares change the running points stage
   P07 of the next round orders and bands on. A solver that settles all nine
   rounds of pairing first, or that screens the boards against the recorded
   pairing rather than the authoritative one, gets a different void set and a
   different everything after it. Defeats `shipped_core_exact` and every
   program family check.
2. **(focal)** The tolerance of a recorded board is the lower of the two
   admission levels its entrants earned, with the bye holder, an unpaired
   entrant and an entrant not eligible in the round each given the level
   `pairing_precedence_policy.toml` states. A board that repeats an opponent is
   voided when either of its two entrants was admitted at a level below the
   repeat opponent rung and stands when both were admitted at that rung or
   above. The same breach is therefore lawful on one board and unlawful on
   another, which is only visible to a solver that derived the pairing. Defeats
   `shipped_core_exact` and the three `*_core_exact` program checks.
3. **(focal)** A voided board still creates an encounter. The two entrants did
   sit down together, so the pair enters the opponent history and both the prior
   opponent constraint of P07 and the `repeat_opponent` check of P08 see it, yet
   the opponent contributes nothing to the strength population of P12. The two
   halves pull in opposite directions and a solver that treats a void as a
   non event, or as an ordinary board, gets one of them wrong. Defeats
   `shipped_core_exact`, `shipped_pairing_exact` and their program
   counterparts.
4. **(focal)** The strength arithmetic rounds twice. The opponent rate is
   rounded to a whole thousandth, and the rounded rate is what the aggregate
   consumes; the aggregate is then rounded again. Both roundings are half to
   even. A pipeline that carries exact fractions to the end agrees on most
   entrants and disagrees on the ones the standings turn on. Defeats
   `shipped_core_exact` and the standings and prize checks downstream of it.
5. **(focal)** The office papers are read, not remembered. The workbook, the
   memorandum and the directive carry values found nowhere else, and each of
   the three unseen verification events carries its own memorandum constants,
   directive key positions, division ranks and crown_grade conversion. A program
   that holds the shipped values instead of reading the papers it is pointed at
   reproduces the shipped event and fails every unseen one. The unseen events
   also move policy values the shipped event keeps canonical: point values,
   tolerances, the ladder rung order, the share table, the default ratings and
   an applicable status name. Defeats every program family check.
6. **(drift)** An experienced reader takes the majority of completed games as the
   result of a board. The evidence levels are ranked by
   `source_priority_register.csv` and the completed game count is the third of
   five: an adjudicated result on the governing sheet and a recorded concession
   both outrank it, and a board with no evidence at all resolves to a double
   loss rather than a draw. Defeats `shipped_core_exact`.
7. **(drift)** The seat order looks like a column to copy.
   `seat_assignment_register.csv` publishes a `declared_seed` and the settlement
   derives its own order from the normalised rating instead, so the two agree for
   only 9 of the 158 entrants that carry one and the disagreement moves the bye
   order and the pairing order. Defeats `shipped_core_exact`.
8. **(trap)** The five void reasons carry their own precedence, printed by the
   directive, and it is not the rung order of the pairing ladder. A board that
   breaches two checks records the reason the directive ranks first. Defeats
   `shipped_core_exact`.
9. **(trap)** A status change whose tick lands exactly on a round boundary
   belongs to the later of the two rounds, because round intervals are start
   inclusive and end exclusive. Seven changes in the shipped event land there.
   Defeats `shipped_core_exact`.
10. **(trap)** A rating quotation carrying the absent marker is an absence, and
    the entrant takes the division default of the admission matrix. Read as a
    zero it drops the entrant to the bottom of the derived seat order and moves
    every key that seat order feeds. Defeats `shipped_core_exact`.
11. **(trap)** The eligibility rule of P10 reaches the game, match and round
    classes only. A tournament notice reaches the event total even when the
    round it names is one the entrant was barred in, as PL-BR-0109 is in round
    9 of the shipped event. Defeats `shipped_core_exact` and the standings and
    prize checks downstream of it.
12. **(trap)** A bar set by a lapsed standing ends in the first round a later
    `restored` row governs, while an expulsion bar never ends and outranks a
    lapsed standing in the same round. PL-BR-0133 is seated again from round 8
    of the shipped event, and the contested verification event expels an
    entrant in the round its standing lapsed. Defeats `shipped_core_exact` and
    `contested_core_exact`.

The reference implementation is `solution/solve.py`, Python 3 standard library
only, exact rational arithmetic throughout. Grading runs on two channels that
`tests/reward.toml` combines: `tests/test_output.py`, 34 deterministic rewardkit
checks over the delivered bytes and the delivered program, and
`tests/judge.toml`, 35 criteria an LLM judge reads from the trajectory, the
closing message and the delivered program. The reference implementation shares
no code with the verifier's own pipeline, so the two agreeing on four events is
evidence that the specifications determine the answer.

Out of bounds: replaying stored answers is caught by
`negative_hardcoded_sample_answers`, which re-mints the shipped event under
another event identity and player identifier prefix and fires when the program
no longer reproduces it; holding this event identifier or reference as a value
inside the program is caught by `negative_names_shipped_event`; writing the same
bytes whatever directory the
program is pointed at is caught by `negative_program_ignores_its_input`; a
program whose two runs disagree is caught by `negative_nondeterministic_output`;
behaviour that changes with the directory name is caught by
`negative_filename_dependent_behaviour`; touching the input directory or writing
an undeclared file is caught by `negative_program_dirties_its_directories`; and
planting a module that would shadow a verifier import is caught by
`negative_rebinds_verifier_dependencies`.

## Load-bearing work

Thirty two artifacts are declared. Thirty one are settlement documents and the
thirty second is the program.

The spine, one published observable per stage plus the manifest:
`normalised_entries.jsonl`, `participation_ledger.csv`,
`round_match_candidates.csv`, `match_result_ledger.csv`,
`round_eligibility_ledger.csv`, `bye_ledger.csv`,
`authoritative_pairing_ledger.csv`, `void_adjudication_ledger.csv`,
`round_score_ledger.csv`, `penalty_application_ledger.psv`,
`opponent_history_ledger.csv`, `opponent_strength_ledger.csv`,
`standings_ledger.csv`, `settlement_manifest.json`.

The pairing family: `pairing_fallback_ledger.csv`,
`repeat_opponent_audit.tsv`, `unpaired_ledger.tsv`,
`pairing_constraint_report.json`.

The standings family: `game_differential_ledger.psv`,
`tiebreak_resolution_ledger.csv`, `final_ranking.json`,
`player_audit_trace.jsonl`.

The prize documents: `prize_allocation_ledger.csv`, `prize_tie_split.tsv`, and
one report per division in force at `division_report_dv_arbor.json`,
`division_report_dv_brine.json`, `division_report_dv_cinder.json` and
`division_report_dv_dune.json`. The publication documents:
`standings_by_division.xml`, `settlement_control_totals.conf` and
`event_settlement_summary.md`.

The program is `crownsettle.py`.

Content contract per deliverable. Every delimited document writes the header the
schema reference lists, in that column order and that row order, with one
trailing line feed and no carriage return. Every JSON document is written at an
indent of one space with the key order the schema reference lists, and every
JSON lines document writes compact objects with a comma and colon separator.
`normalised_entries.jsonl` carries the derived seat number, the milli rating,
the rating source and the folded identifiers of each entrant.
`participation_ledger.csv` carries one row per entrant and round with the
governing change code and its sequence. `authoritative_pairing_ledger.csv`
carries the admission level of every board and the running points its two
entrants opened the round on. `void_adjudication_ledger.csv` carries the reason,
the violation level, the tolerance and the base points each side was credited.
`round_score_ledger.csv` carries the base points after the match penalty, the
modifier code, the modified points, the round points after the round penalty and
the game differential after the game penalty. `opponent_strength_ledger.csv`
carries the population size, the summed rate and the two rounded values.
`standings_ledger.csv` carries the five ordering values, the penalty units and
the eligibility flag. `settlement_manifest.json` carries the core digest over
the six core documents, the publication digest over every other document, and
one entry per document with its digest and byte length, all in the artifact
contract order of the P14 specification. The empty division writes its report
with zero counts and the absent marker as its top entrant, and
`unpaired_ledger.tsv` and `prize_tie_split.tsv` are written as a header alone on
an event that reaches neither branch.

The program contract adds the interface: `--data <directory>` and
`--out <directory>` in either order, the output directory created when absent, a non zero exit and no
document when a required paper is missing, the input directory left untouched,
identical bytes on a second run and under another directory name, and nothing
about the event held inside the program.

Out of bounds by design: nothing outside the working papers settles anything
here, which `open_this_first.txt` and the instruction state, the unseen events
grade and judged criterion R33 penalises for the three papers that govern
nothing; no package is installed; no binary floating point enters any
derivation; and no value of this event is held inside the delivered program.
Each of these is written in a paper the agent can read, so none of them grades a
rule the agent was never told. Where the agent puts its own scratch work is
deliberately ungraded.

## Verification

`tests/test.sh` clears any stale reward file, locks `/logs/verifier` to root,
restricts `/tests` and hands over to rewardkit, which scores
`tests/test_output.py` and `tests/judge.toml` and writes `reward.json`.
`tests/reward.toml` gives each channel half of the reward: the test channel's
weighted sum is multiplied by 0.5 / 85 and the judged channel's by 0.5 / 72.

The test channel owns its corpus. It regenerates the shipped event and three
further events the agent never sees, one contested, one wide and one thin,
recomputes each settlement with its own pipeline, and grades the delivered bytes
against it. The delivered program runs as an unprivileged user in its own
process group, with no variable of the verifier environment, and the group is
killed before the check returns, including when a run outlives its timeout.

The contested event carries the fixtures the generator's draws never produce:
the reinstate change code and the voided entry status the sentinel note names,
a board whose adjudicated result and concession disagree, a board with two
filed result sheets whose later one adjudicates a result the games do not give,
an expulsion in the round an entrant's standing lapsed, a lapsed and a restored
standing row naming one round, one entrant who takes game, match and round
notices in one round whose modifier is not the identity, two of them of the
game class, a cross division board on which the band widening of the division
of `player_a` decides the void reason, and a board between two entrants not
eligible in the round. The thin event carries boards that pair the bye holder
and an unpaired entrant with an entrant not eligible in the round. Each one
decides a graded byte of its event, so the precedence it exercises is graded
rather than only stated.

Each unseen event also moves policy values the program contract says must be
read rather than held. The contested event credits one point for a loss and
gives an entrant not eligible in the round a tolerance of two. The wide event
credits four points for a win and two for a draw, prints its own share table
and default ratings, and names its equal revision status `provisional`. The
thin event sets aside the prior opponent test before the score band, gives the
bye holder a tolerance of one and an unpaired entrant a tolerance of two, and
prints its own default ratings.

Test channel totals: 34 checks, 27 positive summing to 85 and 7 negative summing
to minus 23.

Positive checks:

- `all_artifacts_exist` (1)
- `core_documents_parse` (1)
- `shipped_core_exact` (3)
- `shipped_pairing_exact` (3)
- `shipped_standings_exact` (3)
- `shipped_prize_exact` (3)
- `shipped_publication_exact` (3)
- `shipped_manifest_consistent` (1)
- `contested_core_exact`, `wide_core_exact`, `thin_core_exact` (5 each)
- `contested_pairing_exact`, `wide_pairing_exact`, `thin_pairing_exact` (5 each)
- `contested_standings_exact`, `wide_standings_exact`, `thin_standings_exact`
  (5 each)
- `contested_prize_exact`, `wide_prize_exact`, `thin_prize_exact` (3 each)
- `contested_publication_exact`, `wide_publication_exact`,
  `thin_publication_exact` (3 each)
- `contested_manifest_consistent`, `wide_manifest_consistent`,
  `thin_manifest_consistent` (1 each)
- `program_refuses_missing_paper` (1), credited only once the same program
  settled the complete contested corpus cleanly

Negative checks:

- `negative_hardcoded_sample_answers` (-5)
- `negative_names_shipped_event` (-3)
- `negative_program_ignores_its_input` (-3)
- `negative_nondeterministic_output` (-3)
- `negative_filename_dependent_behaviour` (-3)
- `negative_program_dirties_its_directories` (-3)
- `negative_rebinds_verifier_dependencies` (-3)

Every family check compares its own documents and nothing else. A slip confined
to the closing stages costs only the families its documents sit in; a stage of
the entry, participation or round loop stages read the wrong way moves every
round after it, as the overview states, and so every family downstream of it.
The manifest is never
compared byte for byte against the reference: because it digests every other
document, it is graded on whether it is the manifest the digest contract makes
of the documents delivered beside it, so a wrong document elsewhere costs its
own family and leaves the manifest check standing. The settlement documents are
graded in two halves, the prize documents and the publication documents, so a
slip in the free text summary does not cost the prize split.

The cheat detectors that could fire on one decision are carved into disjoint
conditions, so no single action costs more than one penalty.
`negative_hardcoded_sample_answers` owns the replayer and stands down when a
mechanical defect of the program already explains its failure. It fires only
when the shipped delivery is byte exact and the program does not reproduce the
shipped event re-minted under another event identity and player identifier
prefix, which every reading of the rules settles exactly as it settles the
shipped event, so a solver that misread a rule the shipped event does not show
is never branded a replayer. `negative_names_shipped_event` and
`negative_program_ignores_its_input` stand down when the replayer condition
holds. `negative_filename_dependent_behaviour`
stands down when the program already disagrees with itself, which
`negative_nondeterministic_output` owns, and both of those compare the declared
documents alone, so an undeclared file never reaches them.
`negative_program_dirties_its_directories` stands down when the program planted
a shadowing module, which `negative_rebinds_verifier_dependencies` owns, and
when the determinism or filename detector already fired, since a changed input
directory can be the reason a program disagrees with itself; it never fires
because a declared document is missing, which the family checks already price.

The judged channel is `tests/judge.toml`, 35 criteria: eight constraints on
instruction following, four on tool use, fifteen on agent behaviour, six on
factuality and two on task completion. Twenty five are judged from the
trajectory, six from the closing message and four, R3, R27, R32 and R35, from
the delivered program. Thirty are positive and total 72, five are negative and
total minus 13. No criterion grades the correctness of a produced file, which
is the test channel's job: the closing message criteria R6, R7, R8, R31 and R34
grade that the message reports what the trajectory shows the agent last read off
its delivered documents or the directive, not whether those documents are
right, because the judge sees the trajectory and no delivered file. No single act costs more than one penalty across the
two channels. A program that picks the workbook sheet by name or position is
charged by R32 alone, because the shipped event re-minted under another
identity keeps its sheet names and positions, so the replayer check does not
fire on it.

## Root cause

**The round is the unit of state, not the event.** Swiss style pairing is a
recurrence: the pool of round `r` is ordered on the closed points of round
`r` minus one. Every attempt to vectorise the nine rounds into one pass loses
the recurrence, and the specification says so out loud in the overview.

**Evidence is ranked, not counted.** A result sheet, a concession, a completed
game count and a declared count are four different kinds of evidence and the
register ranks them. Counting games is the reading of somebody who never opened
`source_priority_register.csv`.

**Lawfulness is relative to what was available.** The appeal doctrine voids a
recorded board only where the regulations would have offered its entrants a
stricter pairing, which is why the tolerance is read off the authoritative
pairing and why the whole ladder has to be implemented before a single board can
be screened.

**A set aside board is still a fact.** The panel can strike a result without
striking the sitting, so one encounter carries two different truths and the two
are consumed by different stages.

**Rounding placement is part of the arithmetic.** Half to even at the rate and
again at the aggregate is a different function from half to even once at the end,
and the difference lands exactly on the entrants a tiebreak has to separate.

**Red lines.** No graded value depends on anything outside `instruction.md` and
`environment/data`. The reference solver reads only its input directory and its
declared outputs, and takes every constant, threshold, rung, key order and
tolerance from the papers.

## Solution shape

1. Read `division_topology.xml` for the event identifier, the event reference,
   the round count and the divisions in force.
2. Read the policy papers, the schema reference and the serialisation contract,
   then read the three office papers: select the live workbook sheet by matching
   its `sheet_reference` cell against the event reference and take only
   operative parameter rows; take only operative clauses of the memorandum whose
   reference is this event; take only operative key rows and division rank rows
   of the directive.
3. P01: build the identifier closure, resolving chains and breaking a cycle at
   its lowest member; group the applicable roster rows by resolved identifier;
   take the highest revision and, on a tie, the highest entry sequence; prefer a
   filed rating return over the roster quotation; convert through the named unit
   register entry; substitute the division default for an absent quotation;
   derive the seat order from the normalised rating.
4. P02: place every journal tick on the round grid with the later round taking a
   boundary, apply drops, reentries and reinstatements as persistent and
   absences as round scoped, then let a lapsed standing and an expulsion notice
   bar the entrant.
5. P03 and P04: pick the governing pairing row per round and table, resolve its
   identifiers, then resolve each board through the five ranked evidence levels
   and record the completed game counts and their difference.
6. For each round in order: settle eligibility; award a bye per odd division
   under the cap, the override and the bye order keys; order the pool on the
   pairing order keys and pair it with the first admissible partner, setting
   aside the memorandum's rungs one at a time and leaving an entrant unpaired
   when no rung serves; screen each recorded board of the round against the
   tolerance its entrants earned, with the policy's levels for the bye holder,
   an unpaired entrant and an ineligible one, and record the first voiding
   reason in the directive order; score each eligible entrant through base
   points, the game penalty, the match penalty, the round modifier and the round
   penalty, in that order; record the encounters; then close the round.
7. P10: settle the tournament class against the closed total and floor it.
8. P12: round each opponent rate, aggregate the rounded rates over the strength
   population, round again, then debit for penalty units and floor.
9. P13 and P14: order the standings on the directive keys in the tiebreak rules
   directions, form prize groups to the stated depth, split each group amount
   with its remainder cents, send an ineligible share to the residue, and write
   every document, the two digests last.

## Ordered plan

1. Read `open_this_first.txt`, then the overview, then the lineage map, before
   opening a register and before writing the program. Earns R1 and R29.
2. Open the workbook as a zip archive, extract the text of the memorandum and
   walk the directive tables, recording the live sheet cell, the operative
   clause numbers and the operative key families. Earns R11, R12 and R13.
3. Work P01 and evidence one entrant of the division the topology leaves out
   of force and its absence from the delivery, the governing filing under a
   higher withdrawn revision, the alias closure and the crown_grade conversion.
   Earns R14, R20, R21 and R23.
4. Work P02 and evidence a status change whose tick lands on a round boundary.
   Earns R22.
5. Work P04 and evidence a board where the ranked levels overturn the completed
   game count. Earns R24.
6. Work the round loop in order, one round at a time, and evidence the tolerance
   of one recorded board, the bye cap override and the effective band. Earns R2,
   R15, R19 and R28.
7. Work P11 and evidence one voided board with the counts_for_strength value of
   its history rows, and one entrant whose strength population leaves out an
   opponent it met. Earns R16 and R17.
8. Work P12 and evidence both roundings, the opponent rate and the aggregate.
   Earns R18.
9. Work P09 and P10 and evidence a round penalty shortfall. Earns R25.
10. Work P14 and evidence the prize group of an ineligible entrant whose group
    carries basis points. Earns R26.
11. Read the sentinel note and implement the two unreached branches from their
    specifications. Earns R4.
12. Deliver the program to its contract, standard library only, holding nothing
    about this event, with names a reader can follow, exact arithmetic and the
    live sheet chosen by its key cell, and run it once over a copy of the papers
    outside `/app/data`. Earns R9 and R27, and avoids R3, R32 and R35.
13. Close with the report the instruction asks for, every figure read off the
    delivered documents: the live sheet key with its sheet name and the pool,
    the count voided under each of the five reasons, every unpaired entrant with
    its round, the division and round of the cap override, and the five ordering
    keys in their printed positions. Earns R5, R6, R7, R8, R31 and R34.
14. Give one notice the appeal journal disposes of with the notice_status it was
    applied on, take no figure from the three papers that govern nothing, and
    look up no outside solution. Earns R30, and avoids R10 and R33.

## Pitfalls

- Pairing all rounds from the recorded results and screening afterwards. Fails
  `shipped_core_exact` and every program family check.
- Screening a recorded board against a fixed tolerance rather than the levels
  its entrants earned. Fails `shipped_core_exact`.
- Taking the completed game majority as the result. Fails `shipped_core_exact`.
- Striking a voided board out of the opponent history, or carrying a voided
  opponent into the strength population. Fails `shipped_core_exact`.
- Carrying exact rates into the aggregate and rounding at the end. Fails
  `shipped_core_exact`.
- Recording the void reason in the rung order of the ladder. Fails
  `shipped_core_exact`.
- Placing a boundary tick in the round that closed. Fails `shipped_core_exact`.
- Reading an absent rating quotation as a zero, or copying the declared seed as
  the seat order. Fails `shipped_core_exact`.
- Letting a round penalty drive the round below its floor, or carrying the round
  modifier onto the game differential. Fails `shipped_core_exact`.
- Paying the share of an ineligible member. Fails `shipped_prize_exact`.
- Dropping a tournament notice because the round it names found the entrant
  barred, or keeping a lapsed bar after a later restored standing. Fails
  `shipped_core_exact` and the families downstream of it.
- Holding the shipped memorandum constants, directive key positions, division
  ranks, unit conversion, point values, tolerances, rung order, share table,
  default ratings or status lists inside the program. Fails the program family
  checks of every unseen event that moves the value held.
- Replaying stored answers. Fires `negative_hardcoded_sample_answers`.
- Taking a parameter from a workbook sheet whose key cell names another event.
  Fails `shipped_core_exact` and every program family check.
- Writing the manifest from anything other than the documents beside it. Fails
  the manifest consistency checks.
- Leaving `unpaired_ledger.tsv` or `prize_tie_split.tsv` out because the event
  reaches neither branch. Fails `all_artifacts_exist`.

## Provenance

Bundle `ninefold-crown-settlement-recompute`, task `terminal-bench/ninefold-crown-settlement-recompute`.
Digests of the files this document describes, over the bytes that shipped:

- `solution/solve.py` sha256 `2c485567c94cb211650e7994eb457daf034b845154e91257c04ebcbeab31cbc6`
- `solution/solve.sh` sha256 `07e02a49a596218d8ee01442e521a3d4009c0ac2f348652ab503155a69eb80f2`
- `tests/test_output.py` sha256 `4464645cb9c17f440f285c93d48547f2209ca4cdd6fe4fb2a8c329626a7ccbb5`
- `tests/judge.toml` sha256 `f0043f629c3645d8ae12e3d19eccd6e3640bd54c077ad4c0daaebf0b61671d44`
- `tests/reward.toml` sha256 `e1c01d13ee9b3e66e6d69489b88cb19299a11303cac3d3aa6c3fec8a4c5f77a9`
- `tests/test.sh` sha256 `d96ac9fe1bc6b60d4f7152215a170d3d133b591252a938f0930007aa26554eb5`

"""Write BUNDLE/solution/TRUTH.md; every count, weight and digest is computed here."""
import hashlib
import re
import sys
import tomllib
from pathlib import Path

B = Path(__file__).resolve().parents[3] / "depot-charge-plan"
SOL, TESTS, DATA = B / "solution", B / "tests", B / "environment" / "data"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def lines(p):
    return len(p.read_text().splitlines())


src = (TESTS / "test_output.py").read_text()
crit = [(n, int(w)) for n, w in re.findall(r"^criteria\.(\w+)\(weight=(-?\d+)\)", src, re.M)]
pos = [(n, w) for n, w in crit if w > 0]
neg = [(n, w) for n, w in crit if w < 0]
P_t, N_t = sum(w for _, w in pos), sum(w for _, w in neg)
judge = tomllib.loads((TESTS / "judge.toml").read_text())
jc = judge["criterion"]
P_j = sum(c["weight"] for c in jc if c["weight"] > 0)
N_j = sum(c["weight"] for c in jc if c["weight"] < 0)
hidden_w5 = sum(w for n, w in pos if n.startswith("fresh_") and w == 5)
fresh = sum(w for n, w in pos if n.startswith(("fresh_", "reordered_", "relocated_", "default_", "missing_", "malformed_")))
data_files = sorted(p for p in DATA.rglob("*") if p.is_file())
data_lines = sum(lines(p) for p in data_files)
solve_lines = lines(SOL / "solve.py")

parts = []
add = parts.append
SOLVE_SRC = (SOL / "solve.py").read_text().splitlines()
DOC_SRC = (DATA / "docs" / "charging_rules.md").read_text().splitlines()


def at(name):
    """solve.py:<line> of the def or class called name."""
    for i, ln in enumerate(SOLVE_SRC, 1):
        if re.match(r"\s*(def|class) %s\b" % re.escape(name), ln):
            return "solve.py:%d" % i
    raise SystemExit("no def " + name)


def rule(n):
    for i, ln in enumerate(DOC_SRC, 1):
        if ln.startswith("%d. " % n):
            return "charging_rules.md:%d" % i
    raise SystemExit("no rule %d" % n)


add("# TRUTH.md - depot-charge-plan\n")
add("## Defect\n")
add(f"""There is no broken program to repair. `/app/data` holds {len(data_files)} files
({data_lines} lines) describing one evening at a city bus operator: a fleet register, a
duty roster, next-day trips, bus types, four depots with charging cabinets, a grid feeder
shared by all four depots, service classes and contracts, a tariff with dated versions, a
settled meter history, the published plan and a disruption notice. The rule register is
`/app/data/docs/charging_rules.md` (rules 1 to 22). The deliverable is
`/app/out/derive_report.py`, a program that builds the one day plan the rules define and
writes nine JSON reports, and that is run again on fresh data folders in the same layout.

The shipped folder is a weak instance: the cabinets never bind, the feeder binds only in
the derated window of the disruption notice (so the plan there differs from the published
plan), three depot meters apply the tariff as written and the East meter reads it shifted by 28
slots, which its settlements pin uniquely. The fresh folders are not degenerate, and three
rules decide them:

- (focal) Meter convention, {rule(12)}: each depot's meter applies the tariff with its own
  fixed convention, the one under which every `settlements.csv` row of that depot is billed
  exactly its cents by the version in force on its settled date. The convention is a
  whole-slot shift of the tariff (0 to 95, wrapping past midnight); on fresh folders it is a
  different non-zero shift per depot, and the settlements allow exactly one. A program that prices slots with the tariff as written plans every fresh
  folder at the wrong prices.
- (focal) Shared limits, {rule(10)} and {rule(11)}: per slot, a depot draws at most its
  cabinets in service times the cabinet kWh, and all four depots together draw at most
  the feeder limit (derated slots from the disruption notice replace it). Planning each
  bus or each depot on its own breaks a limit or loses energy.
- (focal) Order of goals and tie-break, {rule(15)} and {rule(16)}: least class-weighted
  unmet energy, then least cost, then least moved energy, and among plans still equal the
  one whose kWh list in slot then bus id order is greater at the first difference. On
  fresh folders many plans tie on all three goals; only the stated tie-break picks one.
- (drift) The shipped folder shows the three only weakly: one meter is shifted, the feeder
  binds in one derated window and the tie-break never decides, so a program checked only
  against the shipped reports looks finished.
- (trap) The published plan looks like a starting point to repair. It only enters the
  third goal (moved energy, {rule(14)}); copying or patching it is not the optimum once
  the limits bind.
""")
add("## Load-bearing work\n")
add(f"""1. Read the plan day: `grid.ini` gives the plan date, the first slot (12:00), 15-minute
   slots and 96 slots; spans "from X to Y" cover slots starting at or after X and before Y
   ({rule(2)}).
2. Accept roster rows in the stated rejection order ({rule(4)}): unknown_vehicle,
   retired_vehicle, duplicate_roster_row, bad_window; window and depot from the accepted
   row ({rule(5)}); type rate and reserve from `bus_types.json` ({rule(6)}).
3. Need = trips of the day after the plan date + extra trips for that date in the notice +
   reserve - arrival charge, floored at 0 ({rule(7)}); class through `contracts.json`,
   unlisted or blank = commercial ({rule(8)}); weights from `service_classes.ini`.
4. Fit each depot's meter convention to `settlements.csv` under the tariff version in force
   on each settled date and price the plan day with the current version through it
   ({rule(12)}; `{at('fit_meters')}`).
5. Build the plan for all four depots together under the per-bus rate, cabinet and feeder
   limits and the lexicographic order, then settle ties by the stated list order
   (`{at('make_plan')}`, `{at('settle_ties')}`).
6. Write the reports in the exact schemas of rules 17 to 21 (`{at('write_reports')}`).
7. Stop with a non-zero exit and a message naming the file when a declared input is
   missing or unreadable ({rule(22)}; `{at('main')}`).
""")
add("## Verification\n")
add(f"""Grader entrypoint: `tests/test.sh`, which runs
`rewardkit /tests --workspace /app --output /logs/verifier/reward.json`. rewardkit scores
the test channel from the `@criterion` checks in `tests/test_output.py`, each weighted by
its `criteria.<name>(weight=W)` registration, and the judged channel from
`tests/judge.toml`, read against `/logs/agent/trajectory.json`. `tests/reward.toml`
divides each channel's weighted sum by its positive total and gives each half of the
reward.

The test channel declares {len(pos)} positive checks (positive weight total {P_t}) and
{len(neg)} negative checks (total {N_t}). The fresh folders are generated inside
`tests/test_output.py` from seeds that live only there (three regular folders h1 to h3 and
one larger folder h4, plus one folder placed several folders deep and one placed at
`/app/data` for a run of the bare command with no flags, plus nine folders u1 to u9 whose
disruption notice lists, for one block of slots, a feeder limit above `feeder_kwh_per_slot`
that the joint plan reaches) and the delivered program is run on
each as an unprivileged user from a foreign working directory with the stated command and
a 120 second limit. Every document
is compared whole with the reference; the message names the first differing path. The
generated tier of {hidden_w5} weight (weight 5 checks) is {hidden_w5 * 100 / P_t:.1f}% of
the positive weight; all checks that run the program on generated or altered folders hold
{fresh * 100 / P_t:.1f}%.

Positive checks ({len(pos)}):

""" + "\n".join(f"- `{n}` (weight {w})" for n, w in pos) + f"""

Negative checks ({len(neg)}):

""" + "\n".join(f"- `{n}` (weight {w})" for n, w in neg) + f"""

Judged channel: {len(jc)} criteria, positive weight {P_j}, negative weight {N_j}:

""" + "\n".join(f"- `{c['name']}` (weight {c['weight']})" for c in jc) + """

Oracle: `solution/solve.sh` copies `solve.py` to `/app/out/derive_report.py`, runs it on
`/app/data` and then runs its embedded self-check stage, which prints `check <id> ok` and one
witness line for each of its thirteen self-checks. Expected test-channel score: 1.000 for the
oracle, 0.000 for a no-op run.
""")
add("## Root cause\n")
add(f"""The rules are stated once each in the rule register; the difficulty is that the shipped
folder exercises the three deciding rules only weakly. A careful first program that
tries a few readings of the meter instead of every whole-slot shift ({rule(12)}), plans
buses in turn (the shipped limits bind only in one derated window) or takes the first optimal plan it finds
(the shipped optimum is unique) can match most shipped reports and still fails every
fresh document of the plan family. The coupling quantity is the
feeder load per slot of the joint optimum: it is carried into every depot file, both
segment files and the summary, so one wrong reading moves rows in every plan document.
""")
add("## Solution shape\n")
add(f"""`solution/solve.py` ({solve_lines} lines, standard library only):

- reading with named-file errors: `{at('InputError')}`, `{at('Folder')}`, `{at('guarded')}`;
- plan day and spans: `{at('Clock')}`, `{at('read_grid')}`, `{at('span')}`, `{at('read_notice')}`;
- tariff versions and meter fit: `{at('read_tariffs')}`, `{at('tariff_on')}`, `{at('fit_meters')}`;
- buses, need, class, published plan and rejections: `{at('read_buses')}`;
- cabinet capacity per depot and slot: `{at('read_depots')}`;
- the joint plan: `{at('Network')}` (capacitated network with successive shortest paths),
  `{at('make_plan')}` (unmet energy priced above any cost, cost above moved energy) and
  `{at('settle_ties')}` (fixes slot then bus id positions in order, raising each as far as an
  equal-objective change allows);
- reports: `{at('totals')}`, `{at('write_reports')}`; entry point `{at('main')}`.

The heredoc inside `solution/solve.sh` is the oracle's self-check stage (missing and malformed input, a
three-bus witness on a small feeder, a lowered-feeder copy, an altered copy, a relocated
copy, recomputation of the summary and the region limits, meter uniqueness, a roster depot
other than the home depot, a tariff version ending on the plan date, two overlapping cabinet
outages and an arrival between slot starts).
""")
add("## Ordered plan\n")
add("""1. Read `charging_rules.md` in full, then every data file it names.
2. Parse the plan day, spans, notice, tariff versions and settlements; fit one meter
   convention per depot and fail loudly if none or several fit.
3. Accept roster rows in the stated order and derive need, class, weight and the
   published kWh per slot.
4. Build one plan for all four depots with the per-bus, cabinet and feeder limits, by the
   stated order of goals, then apply the tie-break.
5. Write the nine reports; run once on `/app/data`.
6. Build small folders where the feeder, a cabinet and a tie actually decide, and a copy
   whose settlements only fit a shifted meter; check the plan against a hand result.
""")
add("## Pitfalls\n")
add(f"""- (trap) Pricing slots with the tariff as written because three shipped depots' settlements
  agree with it ({rule(12)}).
- (trap) Planning one bus or one depot at a time; on fresh folders the shared feeder
  ({rule(11)}) and the cabinets ({rule(10)}) bind in many slots.
- (trap) Returning the first optimal plan found; the tie-break ({rule(15)}) decides on
  every fresh folder.
- (trap) Taking the lower of `feeder_kwh_per_slot` and a derated limit; rule 11 replaces the
  base by the listed limit ({rule(11)}), and on u1 to u9 the listed limit is above the base.
- (drift) Testing only against the shipped reports, where the limits and the tie-break never decide.
- Naming the wrong reason for a roster row that meets two rejection conditions at once
  ({rule(4)} names the order), counting extra trips of other dates, keeping published rows
  outside the window, or
  ordering `data_quality.json` by anything but file then line ({rule(7)}, {rule(13)},
  {rule(21)}).
""")
add("## Provenance\n")
add(f"""```yaml
uuid: null  # task.toml carries no canary_guid or uuid field
instance_id: depot-charge-plan
task_name: terminal-bench/depot-charge-plan
fix_patch_sha256: {sha(SOL / 'solve.sh')}
solve_py_sha256: {sha(SOL / 'solve.py')}
test_output_py_sha256: {sha(TESTS / 'test_output.py')}
judge_toml_sha256: {sha(TESTS / 'judge.toml')}
reward_toml_sha256: {sha(TESTS / 'reward.toml')}
language: python
golden_score_measured: null  # not measured for this instance
golden_score_channel_a_pct: null
golden_score_channel_b_pct: null
golden_score_runs: 0
golden_score_trial_id: null  # no calibration trial has been run yet
golden_score_verified_by: >
  Not yet measured on a harness trial. Local runs of the oracle score 1.000 and a
  no-op run scores 0.000 on the test channel in tests/test_output.py only; the
  judged channel has no oracle score.
caveat: >
  The test channel carries {len(pos)} positive checks worth {P_t} weight and
  {len(neg)} negative checks worth {N_t} weight. The judged channel carries
  {len(jc)} criteria worth {P_j} positive and {N_j} negative points.
  tests/reward.toml divides each channel's weighted sum by its positive total
  and gives each half of the reward.
```
""")
(SOL / "TRUTH.md").write_text("\n".join(parts))
print("TRUTH.md", len("\n".join(parts).splitlines()), "lines; P_t", P_t, "N_t", N_t, "P_j", P_j, "hidden_w5", hidden_w5)

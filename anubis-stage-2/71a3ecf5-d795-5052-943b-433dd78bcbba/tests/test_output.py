"""Verifier for the HAS-7 71a3ecf5-d795-5052-943b-433dd78bcbba task.

Expected artifacts are derived here, independently of the delivered program,
straight from the shipped extract. Additional seeded extracts in the same schema
are built inside the verifier so the delivered program is exercised on data it
has never seen; no expected answer is stored in the bundle.

Test polarity for negative-weight tests: the assertion HOLDS when the cheat is
present. An honest run makes the assertion fail, so the negative weight is not
added.
"""
# pyright: reportUndefinedVariable=false, reportUnhashable=false

from __future__ import annotations

import configparser
import json
import math
import os
import re
import signal

from rewardkit import criteria, criterion
import subprocess
import sys
import tempfile
import threading
import tomllib
import unicodedata
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

SAMPLE_SEED = 20260914
SHIPPED_UNITS = 840
CHALLENGE_SEED = 8812734501
SECOND_SEED = 4410992277
EVAL_SEED = 7305519962
SHUFFLE_SEED = 6677201133

OUT = Path("/app/out")
PROGRAM = OUT / "derive_survey.py"
UNIT_SCALE = 1_000_000
PERIOD = "2026-H1"
WAVE = 3
GRAND = 331_500
FRAME_WIDTHS = [12, 4, 12, 26, 12, 4, 24, 18]
SHEET_WIDTHS = [24, 6, 16, 14, 14, 12, 8]
TABLES = ("activity_by_region", "tenure_by_wquintile",
          "hours_by_sector", "band_transition")

AREAS = ["NR", "ST", "WE", "EA", "CE"]
AREA_NAMES = {"NR": "Northreach", "ST": "Southmarch", "WE": "Westf\u00f6ld",
              "EA": "Eastmoor", "CE": "Centralis"}
HOLDINGS = ["owned", "mortgaged", "rented_private", "rented_social"]
STATUSES = ["employed_ft", "employed_pt", "self_employed", "inactive", "seeking"]
INDUSTRIES = ["agri", "manuf", "construct", "retail", "services", "public"]
# Sectors the cell registry lists in this order; "mining" is a registry level
# no household reports, so its row of the hours table is always empty.
REGISTRY_SECTORS = ["agri", "manuf", "mining", "construct", "retail", "services", "public"]
GRADES = ["B1", "B2", "B3", "B4"]
GRADE_EDGES = [(0, 15), (16, 29), (30, 44), (45, 999)]
TOUCH = ["c1", "c2", "c3"]
# Attempt ranges of the contact bands, over the attempt records of waves 1 and 2.
TOUCH_RANGES = {"c1": (0, 7), "c2": (8, 9), "c3": (10, 999)}
ROUNDINGS = ("margin", "iteration")
OUTCOMES = {
    "superseded": (90, True, False, True),
    "complete": (80, True, True, False),
    "partial": (70, True, True, False),
    "refusal": (60, True, False, False),
    "noncontact": (50, True, False, False),
    "vacant": (45, False, False, False),
    "ineligible": (40, False, False, False),
    "outofscope": (35, False, False, False),
}
REPAIR_CODES = ["M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8"]
ARTIFACTS = [
    "frame_audit.json", "control_totals.json", "response_status.json",
    "design_weights.csv", "control_margins.tsv", "adjustment_cells.json",
    "adjusted_weights.csv", "raking_trace.json", "final_weights.csv",
    "weight_diagnostics.json", "replicate_design.json", "replicate_summary.csv",
    "estimates_activity_by_region.csv", "estimates_tenure_by_wquintile.csv",
    "estimates_hours_by_sector.csv", "estimates_band_transition.csv",
    "variance_components.json", "cv_screening.json", "primary_suppression.json",
    "secondary_suppression.json", "disclosure_audit.tsv", "closure_report.json",
]
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
DIMENSIONS = ("activity", "band", "region_tenure")

# Settings each extract is built under. The shipped round uses SHIPPED_SETTINGS;
# every unseen extract overrides some of them, so constants lifted from the
# shipped round do not carry over.
# "order" and "rounding" are withheld from the rule files and recovered from the
# pilot record; "nfd_names" and "clock_twins" switch two trap families on or off
# so the hidden extracts carry a different trap mix from the shipped one.
SHIPPED_SETTINGS = {"order": ("band", "region_tenure", "activity"), "rounding": "iteration",
                    "max_collapse_rounds": 4, "max_iterations": 13, "max_cascade_rounds": 12,
                    "trim_trigger_deff_bp": 10500, "nfd_names": True, "clock_twins": True}
CHALLENGE_SETTINGS = {"order": ("activity", "band", "region_tenure"), "rounding": "margin",
                      "max_collapse_rounds": 1, "max_iterations": 60, "max_cascade_rounds": 1,
                      "trim_trigger_deff_bp": 10300, "nfd_names": False, "clock_twins": True}
SECOND_SETTINGS = {"order": ("region_tenure", "activity", "band"), "rounding": "iteration",
                   "max_collapse_rounds": 4, "max_iterations": 4, "max_cascade_rounds": 12,
                   "trim_trigger_deff_bp": 10600, "nfd_names": True, "clock_twins": False}
THIRD_SETTINGS = {"order": ("band", "activity", "region_tenure"), "rounding": "margin",
                  "max_collapse_rounds": 2, "max_iterations": 30, "max_cascade_rounds": 3,
                  "trim_trigger_deff_bp": 10450, "nfd_names": False, "clock_twins": False}


class Stream:
    """Deterministic xorshift64 star generator."""

    __slots__ = ("value",)

    def __init__(self, seed):
        self.value = (seed & 0xFFFFFFFFFFFFFFFF) or 0xA0761D6478BD642F

    def step(self):
        v = self.value
        v ^= (v >> 12) & 0xFFFFFFFFFFFFFFFF
        v ^= (v << 25) & 0xFFFFFFFFFFFFFFFF
        v ^= (v >> 27) & 0xFFFFFFFFFFFFFFFF
        self.value = v & 0xFFFFFFFFFFFFFFFF
        return (self.value * 0x2545F4914F6CDD1D) & 0xFFFFFFFFFFFFFFFF

    def span(self, low, high):
        return low + self.step() % (high - low + 1)

    def one_of(self, items):
        return items[self.step() % len(items)]

    def odds(self, hits, total):
        return self.step() % total < hits


def grade_of(hours):
    for name, (low, high) in zip(GRADES, GRADE_EDGES):
        if low <= hours <= high:
            return name
    return GRADES[-1]


def spell(unit, style):
    area, serial = unit[3:5], unit[6:]
    if style == 1:
        return "rh_%s_%s" % (area.lower(), serial)
    if style == 2:
        return "RH.%s.%s" % (area, serial.lstrip("0"))
    if style == 3:
        return "  RH-%s-%s  " % (area, serial.lstrip("0"))
    if style == 4:
        return "rh-%s-%s" % (area.lower(), serial)
    if style == 5:
        return "RH-%s-%s" % (area, serial.lstrip("0") or "0")
    return unit


def _pad(cells, widths):
    return "".join(str(c).ljust(n)[:n] for c, n in zip(cells, widths))


def _top_up(rows, floor, maker):
    """Append out of scope rows until a record file reaches `floor` lines."""
    index = 0
    while len(rows) < floor:
        rows.append(maker(index))
        index += 1


def _put(path, text):
    path.write_text(text, encoding="utf-8", newline="\n")


# ======================================================= synthetic extract
# The written standard and the field dictionary the instruction names. They
# are copied into every extract this module builds, so a program that reads
# them at run time, as the instruction invites, finds them on unseen data too.
HAS7_STANDARD = r'''# HAS-7 Household Activity Statistics Standard, revision 7

This standard defines how a Regional Household Activity Survey extract is turned
into weighted estimates and into a disclosure controlled publication set. It is
the complete rule set. Anything this document does not state is not part of the
standard. Its sections are grouped by subsystem; the order of the sections is
not the order in which the rules are applied.

## 1. Scope and reference points

The survey reference period is `2026-H1`. The reference wave is wave `3`. Waves
`1` and `2` are prior waves and are used only where a rule names them.

Every figure this standard defines is derived from the extract alone. The field
index `HAS-7-field-dictionary.psv` lists every file of the extract and every
field each file carries.

## 2. Identifiers, text and arithmetic

A unit identifier in canonical form is `RH-<REGION>-<SERIAL>` where `<REGION>` is
two upper case letters and `<SERIAL>` is exactly six digits with leading zeros.
Identifiers appear in the extract in other spellings: lower case, with `_` or `.`
in place of `-`, with surrounding whitespace, and with the serial written without
its leading zeros. All of these denote the same unit and fold onto the canonical
form. Identifiers, codes and names are compared after Unicode normalisation form
NFC. Every file the standard defines is written UTF-8 with no byte order mark
and with `\n` line endings.

Weights, control totals and estimates are carried as whole numbers of
micro-units. One micro-unit is one millionth of one person, so a weight of one
person is the integer `1000000`. Rates and shares are carried as whole numbers of
basis points, so one hundred percent is the integer `10000`.

Division rounds to the nearest whole number with halves away from zero. Where a
rule applies division more than once the rounding happens at every division the
rule names, not once at the end. The raking section is the one exception: it
fixes its own rounding point.

## 3. Reading the corpus

Wherever a file carries an `active` column, an `active` field or an `active`
property, a row whose active marker is not `Y`, `yes` or `true` is out of scope
and takes no part in any figure.

Where a register defines a `sort_rank`, that rank fixes the order in which its
levels appear in any artifact that lists them.

## 4. Benchmarks and control totals

Benchmark files publish a series per dimension. Only rows whose
`reference_period` equals the survey reference period are in scope.

For each dimension and level the control total is the offer with the greatest
`rank`; where that ties, the one with the greatest `published_date`; where that
also ties, the one with the greatest `source_id`.

A benchmark value is written in the unit its file declares and is converted to
persons through the conversion register before it is used.

The three dimensions are `region_tenure`, whose level key is the region code and
the tenure joined by `|`; `activity`, whose level key is the activity code; and
`band`, whose level key is the band code.

Worked example, on levels no report carries: offers for one level of rank 2
dated `2026-03-01` from `BEN-Q`, rank 2 dated `2026-03-01` from `BEN-R` and rank 1
dated `2026-08-01` from `BEN-S`. Rank leaves the first two, the date ties, and
`BEN-R` is the greater source, so its value is the control total.

## 5. Closure

The following must hold and each is reported with the evidence behind it.

Raking converged. The final weight total is within the raking tolerance of the
control grand total. Trimming left the sum of all final weights equal to the sum
of all raked weights. For every table, the published total plus the suppressed
total equals the table total, so the conservation residual over the four tables
is zero.

The post trim margin deviation is the greatest absolute difference, over every
level of every margin, between the final weight sum of the level and its control
total. It is reported and it is not required to be zero.

## 6. Contact history and dispositions

Contact attempts for a unit and a wave arrive across several files. The final
disposition for that unit and wave is the attempt with the greatest
`severity_rank`; where that ties, the attempt at the latest instant; where that
also ties, the attempt with the greatest `attempt_no`.

Timestamps arrive with an offset and may carry fractional seconds. The canonical
instant is UTC with the fractional part truncated, never rounded.

An instant is written as `YYYY-MM-DDTHH:MM:SSZ`, with the `Z` suffix and no
offset and no fractional part.

A contact log line that carries a `correction` field in place of an `outcome`
field is a correction, not an attempt. It names a unit, a wave and an attempt
number, and its correction is `void` or `reinstate`. For each unit, wave and
attempt number, the in scope correction at the latest instant gives the net
state; where two share an instant, the reinstatement gives it. An attempt whose
net state is void takes no part in resolving the disposition, in whichever
contact file it appears, and it still counts as an attempt record. An attempt no
correction names stands.

Worked example, on a unit no report carries: attempts 1 `refusal` and 2
`complete` at wave 3. A void of attempt 2 at `10:00Z` followed by a reinstatement
at `11:00Z` leaves attempt 2 standing, so the unit settles on `complete`. A
second void at `12:00Z` voids it again, and the unit settles on `refusal`.

A disposition carries three flags from the precedence register: whether the unit
is eligible, whether it responded, and whether it is superseded. A superseded
unit takes no part in estimation and still appears in the response status record;
where its disposition is flagged eligible it stays in the eligible set and in its
adjustment cell as a unit that did not respond.

A unit is eligible at the reference wave when its resolved disposition is
eligible and its `dwelling_units` is not zero. A unit is responding when it is
eligible, its resolved disposition is responding, it is not superseded, and an
interview record for the reference wave exists.

## 7. Design weights

Let `N` be the population units of a stratum and `n` the number of resolved frame
units in that stratum. The design weight of a unit in that stratum is `N` divided
by `n`, in micro-units.

Where the subsample register marks a unit as subsampled, its design weight is
divided by the subsample factor the subsample register declares, expressed as a
share.

## 8. Disclosure screening and suppression

A cell is suppressed as a primary suppression when its count is below the minimum
publishable count, or its coefficient of variation is above the maximum
publishable coefficient of variation, or its dominance is above the dominance
limit. Every reason that applies is recorded.

A published table must not let a suppressed value be recovered by subtraction. So
where a row of a table or a column of a table holds exactly one suppressed cell,
one further cell of that same row or column is suppressed. The cell chosen is the
one with the smallest count; where that ties, the one whose cell key sorts
first. Rows are considered in their registry order before columns, and the whole
pass repeats until no row and no column holds exactly one suppressed cell, or
until the cascade round limit is reached.

The reported number of cascade rounds counts every pass made over a table,
including the final pass that suppressed nothing, and it is reported for each
table separately.

The screening rank of a cell orders every cell of every table by coefficient of
variation descending, then by table name ascending, then by cell key ascending,
and numbers them from one.

## 9. Estimates

Four tables are published. Their row and column levels, and the order of those
levels, come from the cell registry.

```
activity_by_region     rows activity at the reference wave   columns region
tenure_by_wquintile    rows tenure                           columns weight quintile
hours_by_sector        rows sector at the reference wave     columns band at the reference wave
band_transition        rows band at wave one                 columns band at the reference wave
```

The weight quintile of a unit follows from ordering the responding units by final
weight ascending and, where that ties, by canonical identifier ascending. A unit
at position `i` of `n`, counting from zero, sits in quintile `1 + (5 * i) // n`.
The quintile is a property of the full sample and is the same in every replicate.

A cell carries the sum of the final weights of the responding units that fall in
it, the count of those units, the greatest single final weight among them, and
the jackknife standard error.

The jackknife variance of a cell is the sum, over every replicate, of `k` minus
one, multiplied by the square of the difference between the cell total under that
replicate and the cell total under the full sample, divided by `k`, where `k` is
the size of the replicate's group and the division keeps only the whole part. The
standard error is the square root of that variance rounded to the nearest whole
micro-unit.

The coefficient of variation of a cell is its standard error over its total, in
basis points. Its dominance is the greatest single final weight in it over its
total, in basis points. A cell with a total of zero carries zero for both.

## 10. Frame resolution

The frame arrives as three registers: `frame__register-a.csv`,
`frame__register-b.tsv` and `frame__register-c.fwf`. `frame__register-d.jsonl`
is a reissue copy: none of its records is a frame record, and it lends the frame
only the one fact this section names below. A frame record is identified by the
pair `(region_code, serial)` after the repairs in this section. The `record_id` is not
part of the identity.

Where more than one record shares an identity, one record survives. The surviving
record is the one with the greatest `vintage_rank`; where that ties, the one with
the greatest `edit_timestamp`; where that also ties, the one with the greatest
`record_id` compared as text. Every record that does not survive is discarded and
its `record_id` is recorded.

The following malformations are repaired rather than rejected. A repaired record
stays in the frame and each repair is counted once per record it is applied to.
M1, M2, M3 and M7 are counted on every register record inside the frame, losing
copies included; M4, M5 and M6 are counted once per resolved unit from the
address register.

```
M1  serial carries leading or trailing whitespace   strip the whitespace
M2  serial is shorter than six digits               pad on the left with zeros
M3  region_code is not upper case                   upper case it
M4  dwelling_units is absent                        treat the unit as carrying one
M5  parent_unit names the unit itself               record the unit, drop the link
M6  parent_unit names a unit absent from the frame  record the unit, drop the link
M7  stratum is written as a name                    map it through the stratum register
M8  identity duplicate                              keep the survivor, record the rest
```

A record whose stratum is neither a known code nor a known name is outside the
frame and contributes nothing, its repairs included.

An absent `dwelling_units` is not the same as a `dwelling_units` of zero. Absent
means unknown and the unit carries one dwelling. Zero means the dwelling is
vacant and the unit is never eligible.

A stratum name is the region name and the stratum group joined by one space, for
example `Northreach urban`.

Where the surviving record leaves `psu_code` blank, the unit's primary sampling
unit is the `psu_code` of the reissue copy that names the unit. That is the only
fact the reissue copy carries into the frame.

## 11. Interviews, hours and bands

Interview records arrive across twelve files covering three waves. A record
carries an activity code, a sector code and hours worked.

The band of a unit at a wave follows from its hours through the band register,
whose edges are inclusive at both ends. Where hours are absent the band carries
forward. For the reference wave it is the band of the unit's wave two interview
hours; where that interview is absent or carries no hours, the `prior_band` of
the unit's in scope row in the wave two prior band file; where that is absent,
the `prior_band` of its row in the wave one prior band file; and where neither
exists, the band of zero hours. A wave two interview that carries hours governs
over the wave two prior band file. A wave one band whose interview carries no hours is the
`prior_band` of the unit's in scope row in the wave one prior band file, and
where that file holds no such row it is the band of zero hours. A unit with no
interview record at a wave has no band at that wave and falls in no cell that
the band at that wave classifies.

## 12. Nonresponse adjustment

An adjustment cell is keyed by the stratum code, the tenure class and the contact
band. The contact band of a unit is the band of the contact band register whose
attempt range, inclusive at both ends, holds the number of attempt records the
contact files carry for the unit at waves one and two together, repeated records
included. The `Contact-Band` field of the address register records the band at
sampling and takes no part in any figure. Its parent cell is keyed by the stratum code and the tenure class. Its
grandparent cell is keyed by the stratum code alone.

A cell holds every eligible unit assigned to it. Its response rate is the design
weight of its responding units over the design weight of its eligible units.

A cell passes when its response rate is at or above the minimum response rate and
its responding count is at or above the minimum cell count. A cell that does not
pass moves every one of its units to the next key up. That test repeats for at
most the stated number of collapse rounds, and a unit never moves past the
grandparent key.

The reported number of collapse rounds counts every pass the test made,
including the final pass that found nothing left to move.

The adjustment factor of a cell is the eligible design weight of the cell over
the responding design weight of the cell. A cell with no responding weight
carries a factor of zero.

The adjusted weight of a responding unit is its design weight multiplied by the
factor of the cell it ended in, that is the design weight times
`adjustment_factor_uw` over `1000000`, rounded once.

## 13. Raking

The adjusted weights are raked onto the control totals.

One iteration applies every margin once. Applying a margin visits each of its
levels and multiplies the weight of every unit in that level by the control total
of the level over the current weight sum of the level. A level with no units and
a level with no control total are both skipped. Weights are whole micro-units
between iterations. Inside an iteration the round rounds at one of two points:
either every weight is rounded to the nearest whole micro-unit each time a margin
rescales it, or the weights are carried exactly through the margins of the
iteration and rounded once when the iteration ends. Halves round away from zero
at either point.

At the end of an iteration the deviation is the greatest absolute difference,
over every level of every margin that carries a control total, between the
rounded weight sum of the level and its control total. Raking stops when that deviation is at or below the tolerance, and
that iteration count is the iterations used. Raking also stops at the maximum
iteration count, in which case the weights of the last completed iteration stand
and the run is recorded as not converged.

The margins are applied in one fixed order, the same in every iteration and in
every replicate. The rule files state neither that order nor the rounding point.
The pilot record holds a pilot population with its adjusted weights, its own
control totals and the figures the pilot round published after raking: the
number of iterations it used and the raked total of every level of every margin.
The pilot round was raked under every rule of this section with the tolerance,
the maximum iteration count, the margin order and the rounding point of the
round. Of the twelve combinations of the six orders of the three margins and the
two rounding points, exactly one reproduces every published pilot figure, and
it gives the margin order and the rounding point of the round.

## 14. Replicate design

Variance is estimated by dropping one primary sampling unit at a time.

A stratum holding fewer than two primary sampling units cannot support this, so
it merges into the stratum its `collapse_partner` names and the two are treated
as one replication group, which carries the code of the stratum the merge leads
into. A replication group is otherwise one stratum and carries its code.

A group of size `k` produces `k` replicates, one per primary sampling unit in it.
In the replicate that drops a primary sampling unit, every unit in that primary
sampling unit carries a design weight of zero, every other unit of that group
carries its design weight multiplied by `k` over `k` minus one, and every unit
outside the group carries its design weight unchanged.

A unit carrying a replicate design weight of zero takes no part in that
replicate. It is absent from that replicate's adjustment cells, so it counts
toward neither the cell's responding count nor either of its weight sums; it is
absent from the raking; and it is absent from the trimming, so it does not enter
the stratum median or the stratum design effect and is never itself trimmed. It
contributes nothing to any estimate under that replicate.

A replicate weight is what the design weights of that replicate become after the
nonresponse adjustment, raking and trimming sections are applied again to them.
The adjustment cells are formed again from the replicate design weights, the
raking runs again, and the trimming runs again. A replicate is not the full
sample weight rescaled.

## 15. Trimming

After raking, each stratum has a ceiling: the trim ratio applied to the median
raked weight of its responding units. The median of an even number of values is
the lower of the two central values.

Trimming applies to a stratum only when the design effect of its raked weights is
above the trim trigger. That design effect is `10000` times the stratum's
responding count times the sum of the squared raked weights of its responding
units, over the square of their sum, rounded once. A stratum at or below the
trigger keeps its raked weights, and its ceiling is still computed and reported.

Worked example, on a stratum no report carries: raked weights `2000000`,
`2000000` and `5000000` give `10000 * 3 * 33000000000000 / 81000000000000`, which
is `12222` basis points.

In a stratum that trimming applies to, a unit above the ceiling is set to the
ceiling. The weight removed from the stratum is handed back to the units of that
stratum that were at or below the ceiling, in proportion to their weight: each
share is the removed weight times the unit's weight over the sum of their
weights, rounded to the nearest micro-unit with halves away from zero. Where the
shares do not add up to the removed weight, the difference, which may be
negative, goes to the unit with the greatest weight after its share, and where
that ties, to the one with the smallest canonical identifier. The hand-back is a
single pass.

The total weight of a stratum is the same before and after trimming. The weight
sums of the raked margins are not, because a margin crosses strata, and the
deviation that leaves is reported rather than corrected.

## 16. Artifacts

Every artifact is written into the output directory. JSON artifacts are written
with keys sorted, an indent of two spaces and a trailing newline. Delimited
artifacts carry the header row this section gives, in this column order, with one
trailing newline and no quoting. Integers are written with no decimal point and
no thousands separator. Booleans in delimited artifacts are written `Y` and `N`.

```
frame_audit.json          repair_counts, self_referencing_units,
                          dangling_parent_units, discarded_record_ids,
                          resolved_unit_count, subsample_factor_bp
control_totals.json       reference_period, grand_total_uw, dimensions,
                          level_counts
response_status.json      reference_wave, disposition_counts, eligible_count,
                          responding_count, superseded_units, units
design_weights.csv        unit_id,stratum,psu_code,subsampled,design_weight_uw
control_margins.tsv       dimension,level_key,control_total_uw,chosen_rank,
                          chosen_source
adjustment_cells.json     collapse_rounds, cell_count, cells, depth_counts
adjusted_weights.csv      unit_id,cell_key,adjustment_factor_uw,
                          adjusted_weight_uw
raking_trace.json         margin_order, tolerance_uw, max_iterations,
                          iterations_used, converged, final_max_deviation_uw,
                          per_iteration
final_weights.csv         unit_id,stratum,raked_weight_uw,trimmed,
                          final_weight_uw
weight_diagnostics.json   responding_count, final_weight_total_uw,
                          design_effect_bp, median_weight_uw, maximum_weight_uw,
                          minimum_weight_uw, trimmed_count, trimmed_units,
                          stratum_totals_uw, stratum_ceilings_uw
replicate_design.json     replicate_count, group_count, groups, merged_groups
replicate_summary.csv     replicate_id,group,dropped_psu,group_size,
                          iterations_used,converged,trimmed_count,final_total_uw
estimates_<table>.csv     cell_key,row_level,column_level,point_estimate_uw,
                          unweighted_count,standard_error_uw,cv_bp,dominance_bp
variance_components.json  replicate_count, tables
cv_screening.json         min_publish_count, max_publish_cv_bp, dominance_bp,
                          tables
primary_suppression.json  tables, counts, total
secondary_suppression.json tables, cascade_rounds, counts, total
disclosure_audit.tsv      screening_rank,table_name,cell_key,status,reason,
                          point_estimate_uw,unweighted_count,cv_bp
closure_report.json       post_trim_margin_deviation_uw, final_weight_total_uw,
                          control_grand_total_uw, conservation_residual_uw,
                          final_total_gap_uw, responding_count, replicate_count,
                          primary_suppression_total, secondary_suppression_total,
                          tables, checks, all_checks_pass
```

Row order is `unit_id` ascending in the three weight artifacts, `replicate_id`
ascending in the replicate summary, registry order of the row level and then of
the column level in the four estimate tables, and screening rank ascending and
then table name and then cell key in the disclosure audit. In
`control_margins.tsv` the rows run by dimension name ascending and then by level
key ascending.

A cell key is the row level and the column level joined by `|`. A replicate
identifier is the group and the dropped primary sampling unit joined by `::`.

In `frame_audit.json` the three unit lists and the discarded record list are
sorted ascending. In `weight_diagnostics.json` `trimmed_units` is sorted
ascending. In `cv_screening.json` each table holds its cells in screening rank
order; everywhere else a list of cells runs in cell key order.

In `adjustment_cells.json` each cell carries `cell_key`, `depth`,
`eligible_weight_uw`, `responding_weight_uw`, `responding_count`,
`response_rate_bp` and `adjustment_factor_uw`, where `depth` is the number of
`|` separators in the key. `depth_counts` maps the depths `0`, `1` and `2`,
written as text, to how many cells carry them.

The control grand total is the sum of the `region_tenure` control totals, and
`final_total_gap_uw` is the final weight total less that grand total.

In `control_totals.json` `dimensions` maps each dimension name to an object from
level key to control total in micro-units, and `level_counts` maps each dimension
name to its number of levels.

In `frame_audit.json` `repair_counts` is keyed by the upper case repair class
code, `M1` through `M8`, and carries a count for every one of the eight whether
or not it fired.

In `raking_trace.json` `margin_order` lists the three dimension names in the
order the round applied them, and `per_iteration` is a list holding one object
per iteration, each carrying `iteration` and `max_deviation_uw`, in iteration
order.

In `replicate_design.json` `groups` maps each replication group to an object
carrying `psus`, the sorted primary sampling units of the group, `size`, how
many of them there are, and `strata`, the sorted stratum codes the group holds.
`merged_groups` carries only those groups that hold more than one stratum, and
maps each to the same sorted list of stratum codes.

In `secondary_suppression.json` `cascade_rounds` maps each table name to the
number of passes that table took.

`design_weights.csv` carries one row for every resolved unit in the frame.
`adjusted_weights.csv` and `final_weights.csv` carry one row for every
responding unit, which is the smaller set.

In `weight_diagnostics.json` `design_effect_bp` is `10000` times the responding
count times the sum of the squared final weights, over the square of the final
weight total, rounded once; it is `0` when the final weight total is zero.
`stratum_ceilings_uw` maps every stratum with a responding unit to its ceiling,
whether or not trimming applied to it.

In `response_status.json` `disposition_counts` maps each disposition that some
unit resolved to at the reference wave to the number of units that resolved to
it, and `superseded_units` lists, sorted ascending, every unit whose resolved
disposition at the reference wave is flagged superseded. `units` maps every
canonical unit identifier that has a
resolved disposition at the reference wave to `disposition`, `attempt_no`,
`resolved_utc` and `attempts`. `attempts` counts every attempt record for that
unit and wave across all the contact files, so a record that repeats an attempt
already carried by another file counts again.

In `cv_screening.json` each cell carries `cell_key`, `screening_rank`, `cv_bp`,
`dominance_bp`, `unweighted_count` and `reasons`, where `reasons` lists `count`,
`cv` and `dominance` in that order for each that applies.

In `primary_suppression.json` each entry carries `cell_key` and `reasons`. In
`secondary_suppression.json` each entry carries `cell_key`, `axis`, `axis_level`
and `round`, where `axis` is `row` or `column`.

In `variance_components.json` each table carries `summed_cell_variance_uw2` and
`by_group`, which maps each replication group to the part of that sum its
replicates contributed.

In `closure_report.json` `tables` maps each table to `total_uw`, `published_uw`,
`suppressed_uw`, `residual_uw` and `coverage_gap_uw`, where the coverage gap is
the final weight total less the table total. `checks` lists, in this order,
`raking_converged`, `final_total_within_tolerance`, `trimming_preserves_total`
and `suppression_conservation`, each carrying `name`, `expected`, `observed` and
`verdict`, where the observed value is `1` when the condition holds and `0` when
it does not and the verdict is `pass` or `fail`. `all_checks_pass` is true only
when all four pass.

In `disclosure_audit.tsv` the status is `published` or `suppressed` and the
reason is `primary`, `secondary` or `none`.
'''

HAS7_DICTIONARY = r'''file_name|field_name|field_type|format|description
HAS-7-field-dictionary.psv|-|psv|psv|this file
HAS-7-standard.md|-|prose|prose|the standard itself
bench__activity-v1.csv|reference_period|text|csv|only the survey reference period is in scope
bench__activity-v1.csv|dimension|text|csv|the control dimension the row belongs to
bench__activity-v1.csv|level_key|text|csv|level key of the dimension
bench__activity-v1.csv|rank|text|csv|highest rank wins for that dimension and level
bench__activity-v1.csv|value|text|csv|written in the unit the file declares
bench__activity-v1.csv|unit|text|csv|measurement unit, converted through bench__unit-conversions.csv
bench__activity-v1.csv|source_id|text|csv|third level of the control chain
bench__activity-v1.csv|published_date|text|csv|second level of the control chain
bench__activity-v2.json|dimension|text|json|the control dimension the row belongs to
bench__activity-v2.json|published_date|text|json|second level of the control chain
bench__activity-v2.json|schema|text|json|schema marker
bench__activity-v2.json|series|text|json|carries no rule of its own
bench__activity-v2.json|source_id|text|json|third level of the control chain
bench__activity-v2.json|unit|text|json|measurement unit, converted through bench__unit-conversions.csv
bench__activity-v2.json|key|text|json|level key of the dimension
bench__activity-v2.json|rank|text|json|highest rank wins for that dimension and level
bench__activity-v2.json|reference_period|text|json|only the survey reference period is in scope
bench__activity-v2.json|value|text|json|written in the unit the file declares
bench__band-v1.properties|schema|text|properties|schema marker
bench__band-v1.properties|dimension|text|properties|the control dimension the row belongs to
bench__band-v1.properties|source_id|text|properties|third level of the control chain
bench__band-v1.properties|published_date|text|properties|second level of the control chain
bench__band-v1.properties|unit|text|properties|measurement unit, converted through bench__unit-conversions.csv
bench__band-v1.properties|reference_period|text|properties|only the survey reference period is in scope
bench__band-v1.properties|key|text|properties|level key of the dimension
bench__band-v1.properties|rank|text|properties|highest rank wins for that dimension and level
bench__band-v1.properties|value|text|properties|written in the unit the file declares
bench__band-v2.toml|schema|text|toml|schema marker
bench__band-v2.toml|dimension|text|toml|the control dimension the row belongs to
bench__band-v2.toml|source_id|text|toml|third level of the control chain
bench__band-v2.toml|published_date|text|toml|second level of the control chain
bench__band-v2.toml|unit|text|toml|measurement unit, converted through bench__unit-conversions.csv
bench__band-v2.toml|reference_period|text|toml|only the survey reference period is in scope
bench__band-v2.toml|key|text|toml|level key of the dimension
bench__band-v2.toml|rank|text|toml|highest rank wins for that dimension and level
bench__band-v2.toml|value|text|toml|written in the unit the file declares
bench__region-tenure-v1.json|dimension|text|json|the control dimension the row belongs to
bench__region-tenure-v1.json|published_date|text|json|second level of the control chain
bench__region-tenure-v1.json|schema|text|json|schema marker
bench__region-tenure-v1.json|series|text|json|carries no rule of its own
bench__region-tenure-v1.json|source_id|text|json|third level of the control chain
bench__region-tenure-v1.json|unit|text|json|measurement unit, converted through bench__unit-conversions.csv
bench__region-tenure-v1.json|key|text|json|level key of the dimension
bench__region-tenure-v1.json|rank|text|json|highest rank wins for that dimension and level
bench__region-tenure-v1.json|reference_period|text|json|only the survey reference period is in scope
bench__region-tenure-v1.json|value|text|json|written in the unit the file declares
bench__region-tenure-v2.toml|schema|text|toml|schema marker
bench__region-tenure-v2.toml|dimension|text|toml|the control dimension the row belongs to
bench__region-tenure-v2.toml|source_id|text|toml|third level of the control chain
bench__region-tenure-v2.toml|published_date|text|toml|second level of the control chain
bench__region-tenure-v2.toml|unit|text|toml|measurement unit, converted through bench__unit-conversions.csv
bench__region-tenure-v2.toml|reference_period|text|toml|only the survey reference period is in scope
bench__region-tenure-v2.toml|key|text|toml|level key of the dimension
bench__region-tenure-v2.toml|rank|text|toml|highest rank wins for that dimension and level
bench__region-tenure-v2.toml|value|text|toml|written in the unit the file declares
bench__region-tenure-v3.ini|schema|text|ini|schema marker
bench__region-tenure-v3.ini|dimension|text|ini|the control dimension the row belongs to
bench__region-tenure-v3.ini|source_id|text|ini|third level of the control chain
bench__region-tenure-v3.ini|published_date|text|ini|second level of the control chain
bench__region-tenure-v3.ini|unit|text|ini|measurement unit, converted through bench__unit-conversions.csv
bench__region-tenure-v3.ini|reference_period|text|ini|only the survey reference period is in scope
bench__region-tenure-v3.ini|key|text|ini|level key of the dimension
bench__region-tenure-v3.ini|rank|text|ini|highest rank wins for that dimension and level
bench__region-tenure-v3.ini|value|text|ini|written in the unit the file declares
bench__unit-conversions.csv|unit_name|text|csv|benchmark unit
bench__unit-conversions.csv|persons_per_unit|text|csv|conversion factor
bench__unit-conversions.csv|active|flag|csv|row scope marker
bench__unit-conversions.csv|notes|text|csv|quoted, may contain a comma
calib__pilot-round.json|schema|text|json|schema marker
calib__pilot-round.json|reference_period|text|json|period of the pilot round
calib__pilot-round.json|controls_uw|integer|json|pilot control totals per dimension and level
calib__pilot-round.json|units|text|json|the pilot population
calib__pilot-round.json|pilot_id|text|json|pilot unit identifier
calib__pilot-round.json|activity|text|json|activity level of the pilot unit
calib__pilot-round.json|band|text|json|band level of the pilot unit
calib__pilot-round.json|region_tenure|text|json|region and tenure level of the pilot unit
calib__pilot-round.json|adjusted_weight_uw|integer|json|pilot weight before raking
calib__pilot-round.json|active|flag|json|row scope marker
calib__pilot-round.json|published|text|json|the figures the pilot round published after raking
calib__pilot-round.json|iterations_used|integer|json|iterations the pilot raking used
calib__pilot-round.json|raked_totals_uw|integer|json|raked pilot total of every level of every margin
contact__log-w1.rfc5424|timestamp|timestamp|rfc5424|carries no rule of its own
contact__log-w1.rfc5424|unit|text|rfc5424|unit identifier in any shipped spelling
contact__log-w1.rfc5424|attempt|integer|rfc5424|third level of the disposition chain
contact__log-w1.rfc5424|outcome|text|rfc5424|disposition code
contact__log-w1.rfc5424|wave|integer|rfc5424|one, two or three
contact__log-w2.logfmt|ts|timestamp|logfmt|carries an offset and fractional seconds
contact__log-w2.logfmt|unit|text|logfmt|unit identifier in any shipped spelling
contact__log-w2.logfmt|attempt|integer|logfmt|third level of the disposition chain
contact__log-w2.logfmt|outcome|text|logfmt|disposition code
contact__log-w2.logfmt|wave|integer|logfmt|one, two or three
contact__log-w2.logfmt|active|flag|logfmt|row scope marker
contact__log-w2.logfmt|correction|text|logfmt|void or reinstate, present in place of outcome
contact__log-w3.logfmt|ts|timestamp|logfmt|carries an offset and fractional seconds
contact__log-w3.logfmt|unit|text|logfmt|unit identifier in any shipped spelling
contact__log-w3.logfmt|attempt|integer|logfmt|third level of the disposition chain
contact__log-w3.logfmt|outcome|text|logfmt|disposition code
contact__log-w3.logfmt|wave|integer|logfmt|one, two or three
contact__log-w3.logfmt|active|flag|logfmt|row scope marker
contact__log-w3.logfmt|correction|text|logfmt|void or reinstate, present in place of outcome
contact__outcomes.csv|unit_id|text|csv|unit identifier in any shipped spelling
contact__outcomes.csv|wave|integer|csv|one, two or three
contact__outcomes.csv|attempt_no|integer|csv|third level of the disposition chain
contact__outcomes.csv|contact_datetime|timestamp|csv|carries an offset and fractional seconds
contact__outcomes.csv|outcome_code|text|csv|disposition code
contact__outcomes.csv|interviewer_id|text|csv|descriptive
contact__outcomes.csv|active|flag|csv|row scope marker
contact__reissues.jsonl|active|flag|jsonl|row scope marker
contact__reissues.jsonl|attempt_no|integer|jsonl|third level of the disposition chain
contact__reissues.jsonl|contact_datetime|timestamp|jsonl|carries an offset and fractional seconds
contact__reissues.jsonl|outcome_code|text|jsonl|disposition code
contact__reissues.jsonl|reissued|flag|jsonl|marks a reissued approach
contact__reissues.jsonl|unit_id|text|jsonl|unit identifier in any shipped spelling
contact__reissues.jsonl|wave|integer|jsonl|one, two or three
disclosure__cell-registry.csv|table_name|text|csv|published table
disclosure__cell-registry.csv|axis|text|csv|row or column
disclosure__cell-registry.csv|level_key|text|csv|level key of the dimension
disclosure__cell-registry.csv|level_label|text|csv|quoted, descriptive
disclosure__cell-registry.csv|sort_rank|integer|csv|level order
disclosure__cell-registry.csv|active|flag|csv|row scope marker
disclosure__parameters.toml|schema|text|toml|schema marker
disclosure__parameters.toml|min_publish_count|integer|toml|carries no rule of its own
disclosure__parameters.toml|max_publish_cv_bp|integer|toml|carries no rule of its own
disclosure__parameters.toml|dominance_bp|integer|toml|carries no rule of its own
disclosure__parameters.toml|max_cascade_rounds|text|toml|carries no rule of its own
disclosure__parameters.toml|suppression_cost_field|text|toml|carries no rule of its own
disclosure__parameters.toml|margins_suppressible|text|toml|carries no rule of its own
disclosure__parameters.toml|key|text|toml|level key of the dimension
disclosure__parameters.toml|sort_rank|integer|toml|level order
frame__addresses.rfc822|Unit-Id|text|rfc822|unit identifier in any shipped spelling
frame__addresses.rfc822|Dwelling-Units|text|rfc822|absent means unknown, zero means vacant
frame__addresses.rfc822|Parent-Unit|text|rfc822|may name the unit itself or a unit not in the frame
frame__addresses.rfc822|Locality|text|rfc822|locality name, may arrive in a decomposed form
frame__addresses.rfc822|Contact-Band|text|rfc822|band recorded at sampling, carries no rule of its own
frame__addresses.rfc822|Active|flag|rfc822|row scope marker
frame__register-a.csv|record_id|text|csv|register row identifier, not part of the identity
frame__register-a.csv|region_code|text|csv|two letters, may arrive lower case
frame__register-a.csv|serial|text|csv|six digits, may arrive short or padded with spaces
frame__register-a.csv|stratum|text|csv|stratum code, may arrive as a stratum name
frame__register-a.csv|psu_code|text|csv|primary sampling unit
frame__register-a.csv|vintage_rank|integer|csv|higher wins when identities collide
frame__register-a.csv|edit_timestamp|timestamp|csv|second level of the survivor chain
frame__register-a.csv|tenure|text|csv|tenure of the unit
frame__register-b.tsv|record_id|text|tsv|register row identifier, not part of the identity
frame__register-b.tsv|region_code|text|tsv|two letters, may arrive lower case
frame__register-b.tsv|serial|text|tsv|six digits, may arrive short or padded with spaces
frame__register-b.tsv|stratum|text|tsv|stratum code, may arrive as a stratum name
frame__register-b.tsv|psu_code|text|tsv|primary sampling unit
frame__register-b.tsv|vintage_rank|integer|tsv|higher wins when identities collide
frame__register-b.tsv|edit_timestamp|timestamp|tsv|second level of the survivor chain
frame__register-b.tsv|tenure|text|tsv|tenure of the unit
frame__register-c.fwf|record_id|text|fixed width|register row identifier, not part of the identity
frame__register-c.fwf|reg|text|fixed width|carries no rule of its own
frame__register-c.fwf|serial|text|fixed width|six digits, may arrive short or padded with spaces
frame__register-c.fwf|strat|text|fixed width|carries no rule of its own
frame__register-c.fwf|psu|text|fixed width|carries no rule of its own
frame__register-c.fwf|vr|text|fixed width|carries no rule of its own
frame__register-c.fwf|edit_timestamp|timestamp|fixed width|second level of the survivor chain
frame__register-c.fwf|tenure|text|fixed width|tenure of the unit
frame__register-d.jsonl|edit_timestamp|timestamp|jsonl|second level of the survivor chain
frame__register-d.jsonl|note|text|jsonl|free text, carries no rule
frame__register-d.jsonl|psu_code|text|jsonl|primary sampling unit of the household the copy names
frame__register-d.jsonl|record_id|text|jsonl|register row identifier, not part of the identity
frame__register-d.jsonl|stratum|text|jsonl|stratum code, may arrive as a stratum name
frame__register-d.jsonl|tenure|text|jsonl|tenure of the unit
frame__register-d.jsonl|unit_id|text|jsonl|unit identifier in any shipped spelling
frame__register-d.jsonl|vintage_rank|integer|jsonl|higher wins when identities collide
frame__subsample.conf|schema|text|conf|schema marker
frame__subsample.conf|subsample_factor_bp|integer|conf|design weight divisor
frame__subsample.conf|subsampled|text|conf|carries no rule of its own
interview__w1-q1.csv|unit_id|text|csv|unit identifier in any shipped spelling
interview__w1-q1.csv|wave|integer|csv|one, two or three
interview__w1-q1.csv|activity_code|text|csv|activity at that wave
interview__w1-q1.csv|sector_code|text|csv|sector at that wave
interview__w1-q1.csv|hours_worked|text|csv|may be absent, which triggers carry forward
interview__w1-q1.csv|proxy_flag|flag|csv|interview taken by proxy
interview__w1-q1.csv|active|flag|csv|row scope marker
interview__w1-q2.psv|unit_id|text|psv|unit identifier in any shipped spelling
interview__w1-q2.psv|wave|integer|psv|one, two or three
interview__w1-q2.psv|activity_code|text|psv|activity at that wave
interview__w1-q2.psv|sector_code|text|psv|sector at that wave
interview__w1-q2.psv|hours_worked|text|psv|may be absent, which triggers carry forward
interview__w1-q2.psv|proxy_flag|flag|psv|interview taken by proxy
interview__w1-q2.psv|active|flag|psv|row scope marker
interview__w1-q3.jsonl|active|flag|jsonl|row scope marker
interview__w1-q3.jsonl|activity_code|text|jsonl|activity at that wave
interview__w1-q3.jsonl|hours_worked|text|jsonl|may be absent, which triggers carry forward
interview__w1-q3.jsonl|proxy_flag|flag|jsonl|interview taken by proxy
interview__w1-q3.jsonl|sector_code|text|jsonl|sector at that wave
interview__w1-q3.jsonl|unit_id|text|jsonl|unit identifier in any shipped spelling
interview__w1-q3.jsonl|wave|integer|jsonl|one, two or three
interview__w1-q4.tsv|unit_id|text|tsv|unit identifier in any shipped spelling
interview__w1-q4.tsv|wave|integer|tsv|one, two or three
interview__w1-q4.tsv|activity_code|text|tsv|activity at that wave
interview__w1-q4.tsv|sector_code|text|tsv|sector at that wave
interview__w1-q4.tsv|hours_worked|text|tsv|may be absent, which triggers carry forward
interview__w1-q4.tsv|proxy_flag|flag|tsv|interview taken by proxy
interview__w1-q4.tsv|active|flag|tsv|row scope marker
interview__w2-q1.csv|unit_id|text|csv|unit identifier in any shipped spelling
interview__w2-q1.csv|wave|integer|csv|one, two or three
interview__w2-q1.csv|activity_code|text|csv|activity at that wave
interview__w2-q1.csv|sector_code|text|csv|sector at that wave
interview__w2-q1.csv|hours_worked|text|csv|may be absent, which triggers carry forward
interview__w2-q1.csv|proxy_flag|flag|csv|interview taken by proxy
interview__w2-q1.csv|active|flag|csv|row scope marker
interview__w2-q2.fwf|unit_id|text|fixed width|unit identifier in any shipped spelling
interview__w2-q2.fwf|wave|integer|fixed width|one, two or three
interview__w2-q2.fwf|activity_code|text|fixed width|activity at that wave
interview__w2-q2.fwf|sector_code|text|fixed width|sector at that wave
interview__w2-q2.fwf|hours_worked|text|fixed width|may be absent, which triggers carry forward
interview__w2-q2.fwf|proxy_flag|flag|fixed width|interview taken by proxy
interview__w2-q2.fwf|active|flag|fixed width|row scope marker
interview__w2-q3.jsonl|active|flag|jsonl|row scope marker
interview__w2-q3.jsonl|activity_code|text|jsonl|activity at that wave
interview__w2-q3.jsonl|hours_worked|text|jsonl|may be absent, which triggers carry forward
interview__w2-q3.jsonl|proxy_flag|flag|jsonl|interview taken by proxy
interview__w2-q3.jsonl|sector_code|text|jsonl|sector at that wave
interview__w2-q3.jsonl|unit_id|text|jsonl|unit identifier in any shipped spelling
interview__w2-q3.jsonl|wave|integer|jsonl|one, two or three
interview__w2-q4.psv|unit_id|text|psv|unit identifier in any shipped spelling
interview__w2-q4.psv|wave|integer|psv|one, two or three
interview__w2-q4.psv|activity_code|text|psv|activity at that wave
interview__w2-q4.psv|sector_code|text|psv|sector at that wave
interview__w2-q4.psv|hours_worked|text|psv|may be absent, which triggers carry forward
interview__w2-q4.psv|proxy_flag|flag|psv|interview taken by proxy
interview__w2-q4.psv|active|flag|psv|row scope marker
interview__w3-q1.csv|unit_id|text|csv|unit identifier in any shipped spelling
interview__w3-q1.csv|wave|integer|csv|one, two or three
interview__w3-q1.csv|activity_code|text|csv|activity at that wave
interview__w3-q1.csv|sector_code|text|csv|sector at that wave
interview__w3-q1.csv|hours_worked|text|csv|may be absent, which triggers carry forward
interview__w3-q1.csv|proxy_flag|flag|csv|interview taken by proxy
interview__w3-q1.csv|active|flag|csv|row scope marker
interview__w3-q2.tsv|unit_id|text|tsv|unit identifier in any shipped spelling
interview__w3-q2.tsv|wave|integer|tsv|one, two or three
interview__w3-q2.tsv|activity_code|text|tsv|activity at that wave
interview__w3-q2.tsv|sector_code|text|tsv|sector at that wave
interview__w3-q2.tsv|hours_worked|text|tsv|may be absent, which triggers carry forward
interview__w3-q2.tsv|proxy_flag|flag|tsv|interview taken by proxy
interview__w3-q2.tsv|active|flag|tsv|row scope marker
interview__w3-q3.fwf|unit_id|text|fixed width|unit identifier in any shipped spelling
interview__w3-q3.fwf|wave|integer|fixed width|one, two or three
interview__w3-q3.fwf|activity_code|text|fixed width|activity at that wave
interview__w3-q3.fwf|sector_code|text|fixed width|sector at that wave
interview__w3-q3.fwf|hours_worked|text|fixed width|may be absent, which triggers carry forward
interview__w3-q3.fwf|proxy_flag|flag|fixed width|interview taken by proxy
interview__w3-q3.fwf|active|flag|fixed width|row scope marker
interview__w3-q4.psv|unit_id|text|psv|unit identifier in any shipped spelling
interview__w3-q4.psv|wave|integer|psv|one, two or three
interview__w3-q4.psv|activity_code|text|psv|activity at that wave
interview__w3-q4.psv|sector_code|text|psv|sector at that wave
interview__w3-q4.psv|hours_worked|text|psv|may be absent, which triggers carry forward
interview__w3-q4.psv|proxy_flag|flag|psv|interview taken by proxy
interview__w3-q4.psv|active|flag|psv|row scope marker
prior__wave1-bands.csv|unit_id|text|csv|unit identifier in any shipped spelling
prior__wave1-bands.csv|prior_band|text|csv|band at that prior wave
prior__wave1-bands.csv|prior_hours|integer|csv|hours at that prior wave
prior__wave1-bands.csv|source_wave|integer|csv|which prior wave the row describes
prior__wave1-bands.csv|active|flag|csv|row scope marker
prior__wave2-bands.jsonl|active|flag|jsonl|row scope marker
prior__wave2-bands.jsonl|prior_band|text|jsonl|band at that prior wave
prior__wave2-bands.jsonl|prior_hours|integer|jsonl|hours at that prior wave
prior__wave2-bands.jsonl|source_wave|integer|jsonl|which prior wave the row describes
prior__wave2-bands.jsonl|unit_id|text|jsonl|unit identifier in any shipped spelling
ref__band-definitions.properties|schema|text|properties|schema marker
ref__band-definitions.properties|lower_hours_inclusive|text|properties|carries no rule of its own
ref__band-definitions.properties|upper_hours_inclusive|text|properties|carries no rule of its own
ref__band-definitions.properties|sort_rank|integer|properties|level order
ref__band-definitions.properties|control_dimension|text|properties|carries no rule of its own
ref__contact-bands.sexp|schema|text|s-expression|schema marker
ref__contact-bands.sexp|code|text|s-expression|contact band code
ref__contact-bands.sexp|min-attempts|integer|s-expression|lowest attempt count of the band, inclusive
ref__contact-bands.sexp|max-attempts|integer|s-expression|highest attempt count of the band, inclusive
ref__contact-bands.sexp|sort-rank|integer|s-expression|level order
ref__contact-bands.sexp|active|flag|s-expression|row scope marker
ref__region-codes.csv|region_code|text|csv|two letters, may arrive lower case
ref__region-codes.csv|region_name|text|csv|used to read a stratum name
ref__region-codes.csv|macro_zone|text|csv|descriptive
ref__region-codes.csv|coastal_flag|flag|csv|descriptive
ref__region-codes.csv|rank_order|text|csv|level order
ref__region-codes.csv|active|flag|csv|row scope marker
ref__region-codes.csv|notes|text|csv|quoted, may contain a comma
ref__stratum-params.tsv|stratum_code|text|tsv|stratum
ref__stratum-params.tsv|region_code|text|tsv|two letters, may arrive lower case
ref__stratum-params.tsv|stratum_group|text|tsv|urban or rural
ref__stratum-params.tsv|population_units|integer|tsv|N for the design weight
ref__stratum-params.tsv|sampled_units|integer|tsv|descriptive
ref__stratum-params.tsv|collapse_partner|text|tsv|merge target for replication
ref__stratum-params.tsv|subsample_factor_bp|integer|tsv|design weight divisor
ref__stratum-params.tsv|active|flag|tsv|row scope marker
ref__tenure-classes.json|classes|text|json|carries no rule of its own
ref__tenure-classes.json|retired|text|json|carries no rule of its own
ref__tenure-classes.json|schema|text|json|schema marker
ref__tenure-classes.json|control_dimension|text|json|carries no rule of its own
ref__tenure-classes.json|sort_rank|integer|json|level order
ref__tenure-classes.json|tenure_class|text|json|carries no rule of its own
rules__adjustment-cells.toml|schema|text|toml|schema marker
rules__adjustment-cells.toml|min_response_rate_bp|integer|toml|carries no rule of its own
rules__adjustment-cells.toml|min_cell_count|integer|toml|carries no rule of its own
rules__adjustment-cells.toml|max_collapse_rounds|text|toml|carries no rule of its own
rules__adjustment-cells.toml|reference_wave|integer|toml|carries no rule of its own
rules__adjustment-cells.toml|key|text|toml|level key of the dimension
rules__adjustment-cells.toml|sort_rank|integer|toml|level order
rules__disposition-precedence.csv|disposition_code|text|csv|outcome code
rules__disposition-precedence.csv|severity_rank|integer|csv|highest wins the disposition chain
rules__disposition-precedence.csv|eligible|flag|csv|counts toward the eligible set
rules__disposition-precedence.csv|responding|flag|csv|counts toward the responding set
rules__disposition-precedence.csv|superseded|flag|csv|excluded from estimation
rules__disposition-precedence.csv|active|flag|csv|row scope marker
rules__disposition-precedence.csv|label|text|csv|descriptive
rules__margin-order.ini|tolerance_uw|text|ini|carries no rule of its own
rules__margin-order.ini|max_iterations|text|ini|carries no rule of its own
rules__margin-order.ini|control_dimension|text|ini|the control dimension a margin section rakes
rules__margin-order.ini|active|flag|ini|row scope marker
rules__trimming.conf|schema|text|conf|schema marker
rules__trimming.conf|trim_ratio_bp|integer|conf|carries no rule of its own
rules__trimming.conf|trim_trigger_deff_bp|integer|conf|stratum design effect above which trimming applies
rules__trimming.conf|trim_reference|text|conf|carries no rule of its own
rules__trimming.conf|redistribute_within|text|conf|carries no rule of its own
rules__trimming.conf|redistribute_proportional_to|text|conf|carries no rule of its own
rules__trimming.conf|remainder_to|text|conf|carries no rule of its own
rules__trimming.conf|preserve_stratum_total|text|conf|carries no rule of its own
'''


def build_case(root: Path, seed: int, unit_count: int = 420,
               bulk: bool = False, n_areas: int = 5,
               settings: dict | None = None) -> Path:
    """Write a complete HAS-7 extract in the shipped schema under `root`.

    `n_areas` varies how many regions, and therefore how many strata, the round
    carries, so a solver cannot assume the shipped round's shape. `settings`
    fixes the margin order the pilot record implies and the round's caps and
    trim trigger, and switches the decomposed-name and repeated-clock-hour
    families on or off. `bulk` only pads the reference tables; every other
    fixture is planted in every extract, the shipped one included.
    """
    settings = dict(SHIPPED_SETTINGS if settings is None else settings)
    root.mkdir(parents=True, exist_ok=True)
    rng = Stream(seed)
    areas = AREAS[:n_areas]

    codes, pops = [], {}
    bands = ("urban", "rural")
    for area in areas:
        for index, band in enumerate(bands):
            code = "%s%d" % (area, index + 1)
            codes.append(code)
            pops[code] = (area, band, rng.span(12000, 48000))
    partner = {code: codes[(i + 1) % len(codes)] for i, code in enumerate(codes)}
    lone = {codes[2], codes[7]}
    psus = {c: ([c + "P1"] if c in lone else
                [c + "P%d" % (j + 1) for j in range(rng.span(3, 5))]) for c in codes}

    people = []
    serial_at = {a: 2000 for a in areas}
    for i in range(unit_count):
        code = codes[i % len(codes)]
        area = pops[code][0]
        serial_at[area] += rng.span(1, 6)
        roll = rng.span(0, 99)
        dwellings = None if roll < 7 else (0 if roll < 11 else rng.span(1, 3))
        person = {
            "unit": "RH-%s-%06d" % (area, serial_at[area]),
            "region_code": area, "serial": serial_at[area], "stratum": code,
            "psu": rng.one_of(psus[code]), "holding": rng.one_of(HOLDINGS),
            "contact_band": rng.one_of(TOUCH), "dwelling_units": dwellings,
            "sub": rng.odds(17, 100), "parent": None,
            "outcome": {}, "status": {}, "sector_code": {}, "hours": {},
        }
        people.append(person)

    for person in people:
        roll = rng.span(0, 99)
        if roll < 4:
            person["parent"] = person["serial"]
        elif roll < 8:
            person["parent"] = 999900 + rng.span(0, 59)
        elif roll < 20:
            person["parent"] = rng.one_of(people)["serial"]

    for person in people:
        for wave in (1, 2, 3):
            roll = rng.span(0, 999)
            if roll < 560:
                code = "complete"
            elif roll < 640:
                code = "partial"
            elif roll < 760:
                code = "refusal"
            elif roll < 850:
                code = "noncontact"
            elif roll < 900:
                code = "ineligible"
            elif roll < 935:
                code = "vacant"
            elif roll < 965:
                code = "outofscope"
            else:
                code = "superseded"
            if person["dwelling_units"] == 0:
                # Half the vacant dwellings still show a complete interview at the
                # reference wave; a zero dwelling count keeps them ineligible.
                code = "complete" if wave == 3 and person["serial"] % 2 == 0 else "vacant"
            person["outcome"][wave] = code
            person["status"][wave] = rng.one_of(STATUSES)
            person["sector_code"][wave] = rng.one_of(INDUSTRIES)
            person["hours"][wave] = (0 if person["status"][wave] in ("inactive", "seeking")
                                     else rng.span(4, 62))

    # ---- control totals: projections of one joint table, so raking is feasible
    def margin(values, levels):
        tally = {lv: 0 for lv in levels}
        for v in values:
            tally[v] = tally.get(v, 0) + 1
        out, run = {}, 0
        for lv in levels[:-1]:
            out[lv] = GRAND * tally[lv] // len(values)
            run += out[lv]
        out[levels[-1]] = GRAND - run
        return out


    # Which interview rows report no hours is settled here, because the band a unit
    # lands in then follows the carry forward rule rather than its true hours.
    for quarter in range(4):
        chosen = [p for i, p in enumerate(people) if i % 4 == quarter]
        for index, person in enumerate(chosen):
            person["reported"] = {w: (None if index % 37 == 3 else person["hours"][w])
                                  for w in (1, 3)}
            person["reported"][2] = None if index % 74 == 3 else person["hours"][2]
            # The prior wave two band file is stale for a few households whose
            # wave two interview still reports hours, so the interview must win.
            person["stale_prior"] = index % 37 == 3 and index % 74 != 3
            # A few households have no reference wave interview at all, a few
            # have no wave one interview, and a few report no hours at waves two
            # and three and appear in neither prior band file.
            person["no_interview"] = {3: index % 43 == 20, 1: index % 41 == 9, 2: False}
            person["no_prior"] = index % 148 == 3

    def landed(person, wave):
        if person["reported"][wave] is not None:
            return grade_of(person["reported"][wave])
        if wave == 3:
            return grade_of(person["hours"][2])
        return grade_of(person["hours"][wave])

    # The controls project one joint table over the units that will respond at the
    # reference wave, so a raking solution provably exists on that support.
    answering = [p for p in people
                 if p["outcome"][3] in ("complete", "partial") and p["dwelling_units"] != 0]
    controls = {
        "region_tenure": margin([p["region_code"] + "|" + p["holding"] for p in answering],
                                ["%s|%s" % (a, h) for a in areas for h in HOLDINGS]),
        "activity": margin([p["status"][3] for p in answering], list(STATUSES)),
        "band": margin([landed(p, 3) for p in answering], list(GRADES)),
    }

    pad = 205 if bulk else 6
    floor = 2000 if bulk else 0
    _write_registers(root, codes, pops, partner, psus, rng, pad, areas, floor)
    _write_rules(root, rng, pad, areas, settings, floor)
    _write_benchmarks(root, controls, rng, pad, floor)
    _write_frame(root, people, pops, rng, fixtures=True, floor=floor, settings=settings)
    _write_contacts(root, people, rng, fixtures=True, floor=floor, settings=settings)
    _write_sheets(root, people, rng, fixtures=True, floor=floor)
    _write_priors(root, people, rng, pad, fixtures=True, floor=floor)
    _write_pilot(root, controls, rng, settings, seed)
    _put(root / "HAS-7-standard.md", HAS7_STANDARD)
    _put(root / "HAS-7-field-dictionary.psv", HAS7_DICTIONARY)
    return root


def _write_registers(root, codes, pops, partner, psus, rng, pad, areas, floor=0):
    rows = ["region_code,region_name,macro_zone,coastal_flag,rank_order,active,notes"]
    for area in areas:
        rows.append('%s,"%s",zone,N,%d,Y,"canonical region"'
                    % (area, AREA_NAMES[area], areas.index(area)))
    for i in range(pad + 10):
        rows.append('%sL%03d,"%s, legacy %d",zone,N,%d,N,"alias, superseded"'
                    % (areas[i % len(areas)], i,
                       AREA_NAMES[areas[i % len(areas)]], i, 100 + i))
    _top_up(rows, floor, lambda i: 'QL%04d,"legacy region %d",zone,N,%d,N,"retired"'
            % (i, i, 500 + i))
    _put(root / "ref__region-codes.csv", "\n".join(rows) + "\n")

    rows = ["stratum_code\tregion_code\tstratum_group\tpopulation_units\t"
            "sampled_units\tcollapse_partner\tsubsample_factor_bp\tactive"]
    for code in codes:
        area, band, pop = pops[code]
        rows.append("%s\t%s\t%s\t%d\t0\t%s\t6500\tY" % (code, area, band, pop, partner[code]))
    for i in range(pad + 5):
        rows.append("XX%03d\t%s\tretired\t%d\t0\t%s\t6500\tN"
                    % (i, areas[i % len(areas)], 1000 + i, codes[i % len(codes)]))
    _top_up(rows, floor, lambda i: "XQ%04d\tZZ\tretired\t1000\t0\tXQ0000\t6500\tN" % i)
    _put(root / "ref__stratum-params.tsv", "\n".join(rows) + "\n")

    body = {"schema": "has7.tenure.v3", "classes": {}, "retired": {}}
    for holding in HOLDINGS:
        body["classes"][holding] = {
            "tenure_class": "owner" if holding in ("owned", "mortgaged") else "renter",
            "control_dimension": "region_tenure", "sort_rank": HOLDINGS.index(holding)}
    for i in range(pad):
        body["retired"]["legacy_%03d" % i] = {"tenure_class": "owner",
                                              "control_dimension": "none",
                                              "sort_rank": 900 + i, "active": False}
    _put(root / "ref__tenure-classes.json", json.dumps(body, indent=2, sort_keys=True) + "\n")

    lines = ["# band definitions", "schema=has7.band.v4"]
    for grade, (low, high) in zip(GRADES, GRADE_EDGES):
        lines += ["band.%s.lower_hours_inclusive=%d" % (grade, low),
                  "band.%s.upper_hours_inclusive=%d" % (grade, high),
                  "band.%s.sort_rank=%d" % (grade, GRADES.index(grade)),
                  "band.%s.control_dimension=band" % grade]
    for i in range(pad):
        lines.append("retired.band.R%03d.sort_rank=%d" % (i, 900 + i))
    _put(root / "ref__band-definitions.properties", "\n".join(lines) + "\n")

    lines = ["; contact bands", "(schema has7.contact.v2)"]
    for touch in TOUCH:
        low, high = TOUCH_RANGES[touch]
        lines.append("(contact-band (code %s) (min-attempts %d) (max-attempts %d) "
                     "(sort-rank %d) (active yes))" % (touch, low, high, TOUCH.index(touch)))
    for i in range(pad):
        lines.append("(contact-band (code r%03d) (min-attempts %d) "
                     "(max-attempts %d) (sort-rank %d) (active no))"
                     % (i, i % 12, i % 12, 900 + i))
    _put(root / "ref__contact-bands.sexp", "\n".join(lines) + "\n")


def _write_rules(root, rng, pad, areas, settings, floor=0):
    rows = ["disposition_code,severity_rank,eligible,responding,superseded,active,label"]
    for code, (rank, eligible, responding, gone) in OUTCOMES.items():
        rows.append('%s,%d,%s,%s,%s,Y,"%s"' % (code, rank, "Y" if eligible else "N",
                                               "Y" if responding else "N",
                                               "Y" if gone else "N", code))
    for i in range(pad):
        rows.append('retired_%03d,%d,N,N,N,N,"retired"' % (i, 900 + i))
    _top_up(rows, floor, lambda i: 'legacy_%04d,%d,N,N,N,N,"legacy"' % (i, 2000 + i))
    _put(root / "rules__disposition-precedence.csv", "\n".join(rows) + "\n")

    _put(root / "rules__adjustment-cells.toml", "\n".join([
        'schema = "has7.nonresponse.v6"', "min_response_rate_bp = 5500",
        "min_cell_count = 10", "max_collapse_rounds = %d" % settings["max_collapse_rounds"],
        'cell_key_fields = ["stratum_code", "tenure_class", "contact_band"]',
        'parent_key_fields = ["stratum_code", "tenure_class"]',
        'grandparent_key_fields = ["stratum_code"]',
        "reference_wave = 3", "prior_waves = [1, 2]", ""]
        + [line for i in range(pad)
           for line in ("[[withdrawn_cell]]",
                        'key = "legacy_%03d"' % i,
                        "sort_rank = %d" % (900 + i), "")]))

    lines = ["[raking]", "tolerance_uw = 5000000",
             "max_iterations = %d" % settings["max_iterations"], ""]
    for dimension in ("region_tenure", "activity", "band"):
        lines += ["[margin.%s]" % dimension, "control_dimension = %s" % dimension,
                  "active = yes", ""]
    for i in range(pad):
        lines += ["[retired_margin.m%03d]" % i, "control_dimension = none",
                  "active = no", ""]
    _put(root / "rules__margin-order.ini", "\n".join(lines))

    _put(root / "rules__trimming.conf", "\n".join([
        "# trimming", "schema = has7.trim.v2", "trim_ratio_bp = 15000",
        "trim_trigger_deff_bp = %d" % settings["trim_trigger_deff_bp"],
        "trim_reference = stratum_median_final_weight",
        "redistribute_within = stratum",
        "redistribute_proportional_to = current_weight",
        "remainder_to = greatest_weight_then_smallest_unit_id",
        "preserve_stratum_total = yes"]
        + ["retired.profile_%03d.trim_ratio_bp = %d" % (i, 100000 + i)
           for i in range(pad)]) + "\n")

    _put(root / "disclosure__parameters.toml", "\n".join([
        'schema = "has7.disclosure.v4"', "min_publish_count = 15",
        "max_publish_cv_bp = 3300", "dominance_bp = 1800",
        "max_cascade_rounds = %d" % settings["max_cascade_rounds"],
        'suppression_cost_field = "unweighted_count"',
        'cascade_tiebreak = ["suppression_cost", "cell_key"]',
        "margins_suppressible = false", ""]
        + [line for i in range(pad)
           for line in ("[[withdrawn_profile]]",
                        'key = "p%03d"' % i,
                        "sort_rank = %d" % (900 + i), "")]))

    rows = ["table_name,axis,level_key,level_label,sort_rank,active"]
    plan = [("activity_by_region", "row", list(STATUSES)),
            ("activity_by_region", "column", list(areas)),
            ("tenure_by_wquintile", "row", list(HOLDINGS)),
            ("tenure_by_wquintile", "column", ["Q%d" % i for i in range(1, 6)]),
            ("hours_by_sector", "row", list(REGISTRY_SECTORS)),
            ("hours_by_sector", "column", list(GRADES)),
            ("band_transition", "row", list(GRADES)),
            ("band_transition", "column", list(GRADES))]
    for table, axis, levels in plan:
        for level in levels:
            rows.append('%s,%s,%s,"%s level",%d,Y' % (table, axis, level, level,
                                                      levels.index(level)))
    for i in range(pad):
        rows.append('retired_table,row,r%03d,"retired",%d,N' % (i, 900 + i))
    _top_up(rows, floor, lambda i: 'legacy_table,column,q%04d,"legacy",%d,N' % (i, 2000 + i))
    _put(root / "disclosure__cell-registry.csv", "\n".join(rows) + "\n")


def _write_benchmarks(root, controls, rng, pad, floor=0):
    order = {"v1": 3, "v2": 1, "v3": 2}
    holder = {}
    for dimension, levels in controls.items():
        for level in levels:
            holder[(dimension, level)] = rng.one_of(["v1", "v2", "v3"])

    # Levels contested at the SAME rank as the winning offer, so rank alone
    # cannot separate them: one per dimension settled by published_date and one
    # region_tenure level settled by source_id. In each case the winner sits in a
    # file whose name sorts after the loser's, so keeping the first offer read
    # in file name order picks the loser.
    keys_of = {d: list(levels) for d, levels in controls.items()}
    date_case, source_case, date_rival = {}, {}, {}
    for dimension, keys in keys_of.items():
        date_case[dimension] = keys[0]
        holder[(dimension, keys[0])] = "v3" if dimension == "region_tenure" else "v2"
        date_rival[dimension] = "v2" if dimension == "region_tenure" else "v1"
        if dimension == "region_tenure" and len(keys) > 1:
            source_case[dimension] = keys[1]
            holder[(dimension, keys[1])] = "v3"

    def slice_for(dimension, tag):
        out = []
        for level, value in controls[dimension].items():
            winner = holder[(dimension, level)]
            if winner == tag:
                out.append((level, order[tag], value))
                continue
            # the equal-rank rival, placed where the chain sends it to lose
            if date_case.get(dimension) == level and tag == date_rival[dimension]:
                out.append((level, order[winner], max(10, value + rng.span(300, 900))))
                continue
            if source_case.get(dimension) == level and tag == "v1":
                out.append((level, order[winner], max(10, value + rng.span(300, 900))))
                continue
            if order[tag] < order[winner]:
                out.append((level, order[tag], max(10, value + rng.span(-900, 900))))
        return out

    def shown(value, unit):
        factor = {"persons": 1, "hundreds_persons": 100, "thousands_persons": 1000}[unit]
        return format((Decimal(value) / Decimal(factor)).normalize(), "f")

    def stale(dimension, levels, count):
        out, i = [], 0
        periods = ["2024-H1", "2024-H2", "2025-H1", "2025-H2"]
        while len(out) < count:
            for level in levels:
                if len(out) >= count:
                    break
                out.append((periods[i % 4], level, rng.span(1, 3), rng.span(3000, 40000)))
            i += 1
        return out

    rt = list(controls["region_tenure"])
    body = {"schema": "has7.benchmark.v1", "dimension": "region_tenure",
            "source_id": "BEN-D", "published_date": "2026-09-30",
            "unit": "persons", "series": []}
    for level, rank, value in slice_for("region_tenure", "v1"):
        body["series"].append({"reference_period": PERIOD, "key": level, "rank": rank,
                               "value": shown(value, "persons")})
    for period, level, rank, value in stale("region_tenure", rt, pad):
        body["series"].append({"reference_period": period, "key": level, "rank": rank,
                               "value": shown(value, "persons")})
    _put(root / "bench__region-tenure-v1.json",
         json.dumps(body, indent=2, sort_keys=True) + "\n")

    lines = ['schema = "has7.benchmark.v1"', 'dimension = "region_tenure"',
             'source_id = "BEN-Z"', 'published_date = "2026-05-02"',
             'unit = "thousands_persons"', ""]
    for level, rank, value in slice_for("region_tenure", "v2"):
        lines += ["[[series]]", 'reference_period = "%s"' % PERIOD,
                  'key = "%s"' % level, "rank = %d" % rank,
                  'value = "%s"' % shown(value, "thousands_persons"), ""]
    for period, level, rank, value in stale("region_tenure", rt, pad):
        lines += ["[[series]]", 'reference_period = "%s"' % period,
                  'key = "%s"' % level, "rank = %d" % rank,
                  'value = "%s"' % shown(value, "thousands_persons"), ""]
    _put(root / "bench__region-tenure-v2.toml", "\n".join(lines))

    lines = ["[meta]", "schema = has7.benchmark.v1", "dimension = region_tenure",
             "source_id = BEN-Q", "published_date = 2026-09-30",
             "unit = hundreds_persons", ""]
    n = 0
    for level, rank, value in slice_for("region_tenure", "v3"):
        lines += ["[series.%04d]" % n, "reference_period = %s" % PERIOD,
                  "key = %s" % level, "rank = %d" % rank,
                  "value = %s" % shown(value, "hundreds_persons"), ""]
        n += 1
    for period, level, rank, value in stale("region_tenure", rt, pad):
        lines += ["[series.%04d]" % n, "reference_period = %s" % period,
                  "key = %s" % level, "rank = %d" % rank,
                  "value = %s" % shown(value, "hundreds_persons"), ""]
        n += 1
    _put(root / "bench__region-tenure-v3.ini", "\n".join(lines))

    rows = ["reference_period,dimension,level_key,rank,value,unit,source_id,published_date"]
    for level, rank, value in slice_for("activity", "v1"):
        rows.append("%s,activity,%s,%d,%s,persons,BEN-D,2026-09-30"
                    % (PERIOD, level, rank, shown(value, "persons")))
    for period, level, rank, value in stale("activity", list(STATUSES), pad):
        rows.append("%s,activity,%s,%d,%s,persons,BEN-D,2026-09-30"
                    % (period, level, rank, shown(value, "persons")))
    _top_up(rows, floor, lambda i: "%s,activity,%s,%d,%d,persons,BEN-D,2025-03-31"
            % (("2024-H1", "2024-H2", "2025-H1", "2025-H2")[i % 4],
               STATUSES[i % len(STATUSES)], 1 + i % 3, 3000 + (i * 37) % 40000))
    _put(root / "bench__activity-v1.csv", "\n".join(rows) + "\n")

    body = {"schema": "has7.benchmark.v1", "dimension": "activity",
            "source_id": "BEN-Z", "published_date": "2026-10-15",
            "unit": "thousands_persons", "series": []}
    for tag in ("v2", "v3"):
        for level, rank, value in slice_for("activity", tag):
            body["series"].append({"reference_period": PERIOD, "key": level,
                                   "rank": rank,
                                   "value": shown(value, "thousands_persons")})
    for period, level, rank, value in stale("activity", list(STATUSES), pad):
        body["series"].append({"reference_period": period, "key": level, "rank": rank,
                               "value": shown(value, "thousands_persons")})
    _put(root / "bench__activity-v2.json", json.dumps(body, indent=2, sort_keys=True) + "\n")

    lines = ["# band benchmark", "schema=has7.benchmark.v1", "dimension=band",
             "source_id=BEN-D", "published_date=2026-09-30", "unit=persons"]
    n = 0
    for level, rank, value in slice_for("band", "v1"):
        lines += ["series.%04d.reference_period=%s" % (n, PERIOD),
                  "series.%04d.key=%s" % (n, level), "series.%04d.rank=%d" % (n, rank),
                  "series.%04d.value=%s" % (n, shown(value, "persons"))]
        n += 1
    for period, level, rank, value in stale("band", list(GRADES), pad):
        lines += ["series.%04d.reference_period=%s" % (n, period),
                  "series.%04d.key=%s" % (n, level), "series.%04d.rank=%d" % (n, rank),
                  "series.%04d.value=%s" % (n, shown(value, "persons"))]
        n += 1
    _put(root / "bench__band-v1.properties", "\n".join(lines) + "\n")

    lines = ['schema = "has7.benchmark.v1"', 'dimension = "band"',
             'source_id = "BEN-Z"', 'published_date = "2026-10-15"',
             'unit = "hundreds_persons"', ""]
    for tag in ("v2", "v3"):
        for level, rank, value in slice_for("band", tag):
            lines += ["[[series]]", 'reference_period = "%s"' % PERIOD,
                      'key = "%s"' % level, "rank = %d" % rank,
                      'value = "%s"' % shown(value, "hundreds_persons"), ""]
    for period, level, rank, value in stale("band", list(GRADES), pad):
        lines += ["[[series]]", 'reference_period = "%s"' % period,
                  'key = "%s"' % level, "rank = %d" % rank,
                  'value = "%s"' % shown(value, "hundreds_persons"), ""]
    _put(root / "bench__band-v2.toml", "\n".join(lines))

    rows = ["unit_name,persons_per_unit,active,notes"]
    for name, factor in (("persons", 1), ("hundreds_persons", 100),
                         ("thousands_persons", 1000)):
        rows.append("%s,%d,Y,canonical" % (name, factor))
    for i in range(pad + 5):
        rows.append('retired_unit_%03d,%d,N,"withdrawn, do not apply"' % (i, i + 1))
    _top_up(rows, floor, lambda i: 'legacy_unit_%04d,%d,N,"withdrawn"' % (i, i + 2))
    _put(root / "bench__unit-conversions.csv", "\n".join(rows) + "\n")


def _write_pilot(root, controls, rng, settings, seed):
    """The pilot record: a small raked population that pins two settings.

    The pilot is raked under the round's tolerance and iteration limit with the
    round's margin order and rounding point, and only its aggregate figures are
    published: the raked total of every level of every margin and the number of
    iterations. The draw is repeated until exactly one of the twelve
    combinations of order and rounding point reproduces every published figure.
    """
    from itertools import permutations
    levels = {d: sorted(controls[d]) for d in DIMENSIONS}
    wanted = (tuple(settings["order"]), settings["rounding"])
    for _ in range(200):
        units = []
        for index in range(48):
            keys = {d: rng.one_of(levels[d]) for d in DIMENSIONS}
            units.append(("PL-%04d" % (index + 1), keys,
                          rng.span(400, 2600) * UNIT_SCALE + rng.span(0, 999999)))
        targets = {d: {} for d in DIMENSIONS}
        for pid, keys, weight in units:
            truth = weight * rng.span(78, 127) // 100
            for d in DIMENSIONS:
                targets[d][keys[d]] = targets[d].get(keys[d], 0) + truth
        start = {pid: weight for pid, _, weight in units}
        axis = {d: {pid: keys[d] for pid, keys, _ in units} for d in DIMENSIONS}
        figures = {}
        for order in permutations(DIMENSIONS):
            for rounding in ROUNDINGS:
                got, _, used, _ = _rake(start, axis, targets, order, 5000000,
                                        settings["max_iterations"], rounding)
                figures[(order, rounding)] = _pilot_figures(got, axis, used)
        chosen = figures[wanted]
        if [k for k, v in figures.items() if v == chosen] == [wanted]:
            break
    rows = []
    for pid, keys, weight in units:
        rows.append(dict(keys, pilot_id=pid, adjusted_weight_uw=weight, active="Y"))
    for index in range(4):
        pid, keys, weight = units[index * 11 + 3]
        rows.append(dict(keys, pilot_id="PL-9%03d" % index,
                         adjusted_weight_uw=weight * 3, active="N"))
    rows.sort(key=lambda r: r["pilot_id"])
    body = {"schema": "has7.pilot.v2", "reference_period": "2025-H2",
            "controls_uw": {d: dict(sorted(v.items())) for d, v in targets.items()},
            "published": chosen, "units": rows}
    _put(root / "calib__pilot-round.json", json.dumps(body, indent=2, sort_keys=True) + "\n")


def _pilot_figures(weights, axis, used):
    """The aggregates the pilot round published after raking."""
    totals = {d: {} for d in axis}
    for d, keys in axis.items():
        for pid, level in keys.items():
            totals[d][level] = totals[d].get(level, 0) + weights[pid]
    return {"iterations_used": used,
            "raked_totals_uw": {d: dict(sorted(v.items())) for d, v in sorted(totals.items())}}


def _write_frame(root, people, pops, rng, fixtures=False, floor=0, settings=None):
    copies = {}
    for person in people:
        count = 1 if rng.odds(62, 100) else (2 if rng.odds(75, 100) else 3)
        choices = rng.one_of([[2], [1, 3], [3, 1], [2, 3], [1, 2, 3], [3, 2, 1]])
        ranks = choices[:count] if len(choices) >= count else [2] * count
        rows = []
        # For one identity in seven the edit stamps run BACKWARDS against the
        # record ids, so a chain that skips the stamp level picks a different
        # survivor and carries a different stratum and tenure forward.
        flip = (person["serial"] % 7) == 3
        span = len(ranks)
        for index, rank in enumerate(ranks):
            slot = (span - 1 - index) if flip else index
            rows.append({"rank": rank,
                         "record_id": "FR%06d%s" % (person["serial"], chr(65 + index)),
                         "stamp": "2026-0%d-1%dT0%d:15:00Z"
                                  % (2 + slot % 3, slot % 9, slot % 6)})
        copies[person["unit"]] = rows

    for position, person in enumerate(people):
        if position % 47 != 5:
            continue
        rows = copies[person["unit"]]
        best = max(rows, key=lambda r: (r["rank"], r["stamp"], r["record_id"]))
        twin = dict(best)
        twin["record_id"] = best["record_id"][:-1] + "Z"
        # the surviving record is the FIRST of the pair in file order, so a
        # last-one-wins reading picks the wrong one
        rows.insert(0, twin)

    for person in people:
        rows = copies[person["unit"]]
        best = max(rows, key=lambda r: (r["rank"], r["stamp"], r["record_id"]))
        for row in rows:
            row["stratum"] = (person["stratum"] if row is best
                              else rng.one_of(sorted(pops)))
            row["holding"] = (person["holding"] if row is best
                              else rng.one_of(HOLDINGS))

    def damaged(person, row, style):
        area, serial, stratum = person["region_code"], "%06d" % person["serial"], row["stratum"]
        if style == 1:
            serial = "  %s  " % serial
        elif style == 2:
            serial = serial.lstrip("0") or "0"
        elif style == 3:
            area = area.lower()
        elif style == 4:
            stratum = "%s %s" % (AREA_NAMES[pops[stratum][0]], pops[stratum][1])
            # Every other name of a region spelled with a non ASCII letter is
            # written decomposed, so it matches the region register only after
            # NFC; read raw, the record falls outside the frame.
            if settings["nfd_names"] and person["serial"] % 2 == 0:
                stratum = unicodedata.normalize("NFD", stratum)
        return area, serial, stratum

    # For some households that have a reissue copy, the surviving register
    # record leaves psu_code blank; the reissue copy is the only file that
    # carries it.
    for index, person in enumerate(people):
        if index % 9 == 3:
            best = max(copies[person["unit"]],
                       key=lambda r: (r["rank"], r["stamp"], r["record_id"]))
            best["psu_blank"] = True

    def psu_of(person, row):
        return "" if row.get("psu_blank") else person["psu"]

    flat = [(p, r) for p in people for r in copies[p["unit"]]]

    part = [x for x in flat if x[1]["rank"] == 2]
    rows = ["record_id,region_code,serial,stratum,psu_code,vintage_rank,"
            "edit_timestamp,tenure"]
    for index, (person, row) in enumerate(part):
        area, serial, stratum = damaged(person, row, index % 5)
        rows.append("%s,%s,%s,%s,%s,%d,%s,%s"
                    % (row["record_id"], area, serial, stratum, psu_of(person, row),
                       row["rank"], row["stamp"], row["holding"]))
    if fixtures and part:
        # A record whose stratum is neither a code nor a name is outside the
        # frame and contributes nothing, its damaged serial and lower case
        # region included, so no repair is counted for it.
        person, row = part[0]
        rows.append("FR999999X,%s,  %06d  ,%s,%s,2,%s,%s"
                    % (person["region_code"].lower(), person["serial"], "NOWHERE-9",
                       person["psu"], row["stamp"], row["holding"]))
    # Records of a retired sampling frame: their stratum is neither a code nor a
    # name the stratum register knows, so they fall outside the frame.
    _top_up(rows, floor, lambda i: "FQ%06dA,zz, %d,RETIRED-%d,ZZ1P1,3,2025-11-0%dT00:00:00Z,owned"
            % (i, 900000 + i, i % 9, 1 + i % 9))
    _put(root / "frame__register-a.csv", "\n".join(rows) + "\n")

    part = [x for x in flat if x[1]["rank"] == 1]
    rows = ["record_id\tregion_code\tserial\tstratum\tpsu_code\tvintage_rank\t"
            "edit_timestamp\ttenure"]
    for index, (person, row) in enumerate(part):
        area, serial, stratum = damaged(person, row, (index + 2) % 5)
        rows.append("\t".join([row["record_id"], area, serial, stratum, psu_of(person, row),
                               str(row["rank"]), row["stamp"], row["holding"]]))
    _top_up(rows, floor, lambda i: "FQ%06dB\tzz\t%d\tRETIRED-%d\tZZ1P1\t3\t2025-11-0%dT00:00:00Z\towned"
            % (i, 900000 + i, i % 9, 1 + i % 9))
    _put(root / "frame__register-b.tsv", "\n".join(rows) + "\n")

    part = [x for x in flat if x[1]["rank"] == 3]
    head = ["record_id", "reg", "serial", "strat", "psu", "vr", "edit_timestamp", "tenure"]
    lines = [_pad(head, FRAME_WIDTHS)]
    for index, (person, row) in enumerate(part):
        area, serial, stratum = damaged(person, row, (index + 4) % 5)
        lines.append(_pad([row["record_id"], area, serial.strip(), stratum,
                           psu_of(person, row), row["rank"], row["stamp"], row["holding"]],
                          FRAME_WIDTHS))
    _put(root / "frame__register-c.fwf", "\n".join(lines) + "\n")

    lines = []
    for index, person in enumerate(people):
        if index % 3:
            continue
        best = max(copies[person["unit"]],
                   key=lambda r: (r["rank"], r["stamp"], r["record_id"]))
        lines.append(json.dumps({"record_id": best["record_id"] + "R",
                                 "unit_id": spell(person["unit"], index % 6),
                                 "stratum": best["stratum"], "psu_code": person["psu"],
                                 "vintage_rank": 0,
                                 "edit_timestamp": "2026-01-04T00:00:00Z",
                                 "tenure": HOLDINGS[(HOLDINGS.index(best["holding"]) + 1) % 4],
                                 "note": "reissue, superseded by the register"},
                                sort_keys=True))
    _top_up(lines, floor, lambda i: json.dumps(
        {"record_id": "FQ%06dR" % i, "unit_id": "RH-ZZ-%06d" % i, "stratum": "RETIRED",
         "psu_code": "ZZ1P1", "vintage_rank": 0, "edit_timestamp": "2025-11-01T00:00:00Z",
         "tenure": "owned", "note": "retired frame reissue"}, sort_keys=True))
    _put(root / "frame__register-d.jsonl", "\n".join(lines) + "\n")

    blocks = []
    for index, person in enumerate(people):
        dwellings = "" if person["dwelling_units"] is None else str(person["dwelling_units"])
        parent = ("" if person["parent"] is None
                  else "RH-%s-%06d" % (person["region_code"], person["parent"]))
        locality = AREA_NAMES[person["region_code"]]
        if index % 41 == 0:
            locality = unicodedata.normalize("NFD", locality[:-1] + "é")
        blocks.append("Unit-Id: %s\nDwelling-Units: %s\nParent-Unit: %s\n"
                      "Locality: %s\nContact-Band: %s\nActive: Y\n"
                      % (spell(person["unit"], index % 6), dwellings, parent,
                         locality, person["contact_band"]))
    _put(root / "frame__addresses.rfc822", "\n".join(blocks))

    lines = ["# subsample register", "schema = has7.subsample.v2",
             "subsample_factor_bp = 6500"]
    for person in people:
        lines.append("unit.%s.subsampled = %s"
                     % (person["unit"], "yes" if person["sub"] else "no"))
    _put(root / "frame__subsample.conf", "\n".join(lines) + "\n")


def _write_contacts(root, people, rng, fixtures=False, floor=0, settings=None):
    months = {1: "2026-01", 2: "2026-03", 3: "2026-06"}

    def attempts_for(person, wave):
        truth = person["outcome"][wave]
        top = OUTCOMES[truth][0]
        weaker = [c for c, v in OUTCOMES.items() if v[0] < top]
        events = []
        for k in range(rng.span(1, 3)):
            if not weaker:
                break
            events.append({"code": rng.one_of(weaker), "attempt": k + 1,
                           "date": rng.span(2, 20), "hour": rng.span(9, 19),
                           "time": rng.span(0, 59), "offset": "+01:00",
                           "frac": rng.span(100, 999)})
        events.append({"code": truth, "attempt": len(events) + 1,
                       "date": rng.span(21, 27), "hour": rng.span(9, 19),
                       "time": rng.span(0, 59), "offset": "+01:00",
                       "frac": rng.span(100, 999)})
        return events

    history = {1: [], 2: [], 3: []}
    for person in people:
        for wave in (1, 2, 3):
            history[wave].append((person, attempts_for(person, wave)))

    # The reference wave carries the duplicated local hour, so the instant
    # tiebreak decides which attempt settles the wave. The twin repeats the same
    # outcome at the same local clock reading under a different offset, and
    # carries the HIGHER attempt number, so a solver comparing clock readings
    # rather than instants reports the wrong attempt.
    # One unit in 29 carries two attempts at the same outcome and the same
    # instant, so only the greater attempt number settles the wave. The echo
    # pins the second explicitly, because the stamp otherwise varies with the
    # attempt number and the two instants would differ. The higher-numbered
    # echo is written after the lower one, so keeping the first record loses.
    for position, (person, events) in enumerate(history[3]):
        if position % 29 != 11:
            continue
        latest = events[-1]
        latest["second"] = (latest["time"] * 7 + latest["attempt"]) % 60
        echo = dict(latest)
        echo["attempt"] = latest["attempt"] + 1
        events.append(echo)

    for position, (person, events) in enumerate(history[3]):
        if not settings["clock_twins"] or position % 53 != 7:
            continue
        latest = events[-1]
        twin = dict(latest)
        twin["attempt"] = latest["attempt"] + 1
        twin["offset"] = "+02:00"
        latest["repeat"] = True
        twin["repeat"] = True
        events.insert(len(events) - 1, twin)

    if fixtures:
        # Severity outranks time. One unit in 17 receives, after the attempt
        # that settles its reference wave, a later attempt with a weaker outcome,
        # so a solver that takes the latest attempt reports the wrong disposition.
        for position, (person, events) in enumerate(history[3]):
            if position % 17 != 6:
                continue
            settled = events[-1]
            rank = OUTCOMES[settled["code"]][0]
            weaker = sorted(c for c, v in OUTCOMES.items() if v[0] < rank)
            if not weaker or settled.get("repeat"):
                continue
            later = dict(settled)
            later.pop("second", None)
            later["code"] = weaker[0]
            later["attempt"] = settled["attempt"] + 1
            later["date"] = 28
            events.append(later)
            person["late"] = True

    # Late evidence. After the round closed, the field office voided some
    # settling attempts and later reinstated a few of them. The correction lines
    # sit at the end of the reference wave log, after the attempts they change,
    # and name the household in a different spelling from the log's own. Only
    # the net state of each attempt counts: a void later reinstated changes
    # nothing, and a void, reinstatement and second void voids.
    corrections = []
    # (kind, step): a later step is a later instant, an equal step the same
    # instant. Lines are written in the listed order, so the fourth pattern puts
    # the governing reinstatement first in the file and the sixth writes a
    # same-instant reinstatement before the void it outranks.
    patterns = ((("void", 0),),
                (("void", 0), ("reinstate", 1)),
                (("void", 0), ("reinstate", 1), ("void", 2)),
                (("reinstate", 1), ("void", 0)),
                (("void", 1), ("reinstate", 1)),
                (("reinstate", 1), ("void", 1)))
    if fixtures:
        live_count = 0
        for position, (person, events) in enumerate(history[3]):
            if person.get("late") or len(events) < 2:
                continue
            if any(e.get("repeat") or e.get("second") is not None for e in events):
                continue
            if position % 23 == 5:
                # An out of scope void of the very attempt that settles the wave.
                corrections.append((person, events[-1]["attempt"], (("void", 0),), False))
                continue
            if position % 19 != 13:
                continue
            corrections.append((person, events[-1]["attempt"],
                                patterns[live_count % len(patterns)], True))
            live_count += 1

    def stamp(wave, event):
        day = "25" if event.get("repeat") else "%02d" % event["date"]
        month = "2026-10" if event.get("repeat") else months[wave]
        hour = "02" if event.get("repeat") else "%02d" % event["hour"]
        second = event.get("second")
        if second is None:
            second = (event["time"] * 7 + event["attempt"]) % 60
        return "%s-%sT%s:%02d:%02d.%03d%s" % (month, day, hour, event["time"],
                                              second, event["frac"], event["offset"])

    lines = []
    for person, events in history[1]:
        for event in events:
            lines.append('<134>1 %s has7.collect contact - - [has7 unit="%s" '
                         'attempt="%d" outcome="%s" wave="1"]'
                         % (stamp(1, event), person["unit"], event["attempt"],
                            event["code"]))
    _put(root / "contact__log-w1.rfc5424", "\n".join(lines) + "\n")

    for wave, name in ((2, "contact__log-w2.logfmt"), (3, "contact__log-w3.logfmt")):
        lines = []
        for person, events in history[wave]:
            for event in events:
                lines.append("ts=%s unit=%s attempt=%d outcome=%s wave=%d active=true"
                             % (stamp(wave, event), spell(person["unit"], 2),
                                event["attempt"], event["code"], wave))
        if wave == 3:
            for index, (person, attempt, pattern, live) in enumerate(corrections):
                for kind, step in pattern:
                    lines.append("ts=2026-10-%02dT%02d:%02d:00.%03d+01:00 unit=%s "
                                 "correction=%s attempt=%d wave=3 active=%s"
                                 % (2 + 9 * step + index % 7, 9 + index % 8,
                                    (7 * index) % 60, rng.span(100, 999),
                                    spell(person["unit"], 1), kind, attempt,
                                    "true" if live else "false"))
        _put(root / name, "\n".join(lines) + "\n")

    rows = ["unit_id,wave,attempt_no,contact_datetime,outcome_code,interviewer_id,active"]
    for wave in (1, 2, 3):
        for person, events in history[wave]:
            last = events[-2] if (wave == 3 and person.get("late")) else events[-1]
            rows.append("%s,%d,%d,%s,%s,IV%03d,Y"
                        % (spell(person["unit"], 4), wave, last["attempt"],
                           stamp(wave, last), last["code"], person["serial"] % 200))
    _put(root / "contact__outcomes.csv", "\n".join(rows) + "\n")

    lines = []
    for index, person in enumerate(people):
        if index % 4:
            continue
        lines.append(json.dumps({"unit_id": spell(person["unit"], 1), "wave": 2,
                                 "reissued": True, "attempt_no": 0,
                                 "outcome_code": "noncontact",
                                 "contact_datetime": "2026-03-02T08:00:00.000+01:00",
                                 "active": True}, sort_keys=True))
    _top_up(lines, floor, lambda i: json.dumps(
        {"unit_id": "RH-ZZ-%06d" % i, "wave": 2, "reissued": True, "attempt_no": 0,
         "outcome_code": "noncontact", "contact_datetime": "2026-03-02T08:00:00.000+01:00",
         "active": False}, sort_keys=True))
    _put(root / "contact__reissues.jsonl", "\n".join(lines) + "\n")


def _write_sheets(root, people, rng, fixtures=False, floor=0):
    plan = [(1, 0, "interview__w1-q1.csv", "comma"), (1, 1, "interview__w1-q2.psv", "pipe"),
            (1, 2, "interview__w1-q3.jsonl", "lines"), (1, 3, "interview__w1-q4.tsv", "tab"),
            (2, 0, "interview__w2-q1.csv", "comma"), (2, 1, "interview__w2-q2.fwf", "fixed"),
            (2, 2, "interview__w2-q3.jsonl", "lines"), (2, 3, "interview__w2-q4.psv", "pipe"),
            (3, 0, "interview__w3-q1.csv", "comma"), (3, 1, "interview__w3-q2.tsv", "tab"),
            (3, 2, "interview__w3-q3.fwf", "fixed"), (3, 3, "interview__w3-q4.psv", "pipe")]
    head = ["unit_id", "wave", "activity_code", "sector_code", "hours_worked",
            "proxy_flag", "active"]
    for wave, quarter, name, shape in plan:
        chosen = [p for i, p in enumerate(people) if i % 4 == quarter]
        records = []
        for index, person in enumerate(chosen):
            if person["no_interview"][wave]:
                continue
            reported = person["reported"][wave]
            hours = "" if reported is None else str(reported)
            records.append([spell(person["unit"], index % 6), str(wave),
                            person["status"][wave], person["sector_code"][wave], hours,
                            "Y" if index % 11 == 0 else "N",
                            "yes" if fixtures and index % 9 == 4 else "Y"])
        for i in range(max(6, floor - len(records))):
            records.append(["RH-ZZ-%06d" % i, str(wave), "inactive", "agri", "0", "N", "N"])
        if shape == "comma":
            body = [",".join(head)] + [",".join(r) for r in records]
        elif shape == "pipe":
            body = ["|".join(head)] + ["|".join(r) for r in records]
        elif shape == "tab":
            body = ["\t".join(head)] + ["\t".join(r) for r in records]
        elif shape == "fixed":
            body = [_pad(head, SHEET_WIDTHS)] + [_pad(r, SHEET_WIDTHS) for r in records]
        else:
            body = [json.dumps(dict(zip(head, r)), sort_keys=True) for r in records]
        _put(root / name, "\n".join(body) + "\n")


def _write_priors(root, people, rng, pad, fixtures=False, floor=0):
    rows = ["unit_id,prior_band,prior_hours,source_wave,active"]
    for person in people:
        if person["no_prior"]:
            continue
        rows.append("%s,%s,%d,1,Y" % (person["unit"], grade_of(person["hours"][1]),
                                      person["hours"][1]))
    for i in range(pad):
        rows.append("RH-ZZ-%06d,B1,0,1,N" % i)
    _top_up(rows, floor, lambda i: "RH-ZZ-%06d,B1,0,1,N" % (pad + i))
    _put(root / "prior__wave1-bands.csv", "\n".join(rows) + "\n")

    lines = []
    for person in people:
        if person["no_prior"]:
            continue
        band = grade_of(person["hours"][2])
        if person.get("stale_prior"):
            band = GRADES[(GRADES.index(band) + 2) % len(GRADES)]
        lines.append(json.dumps({"unit_id": person["unit"],
                                 "prior_band": band,
                                 "prior_hours": person["hours"][2],
                                 "source_wave": 2, "active": True}, sort_keys=True))
    for i in range(pad):
        lines.append(json.dumps({"unit_id": "RH-ZZ-%06d" % i,
                                 "prior_band": "B1", "prior_hours": 0,
                                 "source_wave": 2, "active": False},
                                sort_keys=True))
    if fixtures:
        # An out of scope row whose marker is the string "N": the standard keeps
        # only Y, yes and true, so it must not lend this unit a prior band.
        person = people[1]
        lines.append(json.dumps({"unit_id": person["unit"],
                                 "prior_band": "B1" if grade_of(person["hours"][2]) != "B1" else "B2",
                                 "prior_hours": 0, "source_wave": 2, "active": "N"},
                                sort_keys=True))
    _top_up(lines, floor, lambda i: json.dumps(
        {"unit_id": "RH-ZZ-%06d" % (pad + i), "prior_band": "B1", "prior_hours": 0,
         "source_wave": 2, "active": False}, sort_keys=True))
    _put(root / "prior__wave2-bands.jsonl", "\n".join(lines) + "\n")


# ================================================ independent reference model
def _round_ratio(top, bottom):
    if bottom == 0:
        return 0
    return ((2 * top + bottom) // (2 * bottom) if top >= 0
            else -((-2 * top + bottom) // (2 * bottom)))


def _root(value):
    if value <= 0:
        return 0
    guess = math.isqrt(value)
    return guess + 1 if (value - guess * guess) > guess else guess


def _fold_unit(raw):
    text = unicodedata.normalize("NFC", str(raw)).strip().upper()
    text = text.replace("_", "-").replace(".", "-")
    hit = re.match(r"^RH-([A-Z]{2})-(\d+)$", text)
    return None if hit is None else "RH-%s-%06d" % (hit.group(1), int(hit.group(2)))


def _instant(raw):
    hit = re.match(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})"
                   r"(?:\.(\d+))?(Z|[+-]\d{2}:\d{2})$", raw.strip())
    if hit is None:
        raise ValueError(raw)
    fields = [int(hit.group(i)) for i in range(1, 7)]
    tail = hit.group(8)
    gap = (timedelta(0) if tail == "Z" else
           (1 if tail[0] == "+" else -1) * timedelta(hours=int(tail[1:3]),
                                                     minutes=int(tail[4:6])))
    when = datetime(*fields, tzinfo=timezone.utc) - gap
    return int(when.timestamp()), when.strftime("%Y-%m-%dT%H:%M:%SZ")


def _lines(path):
    return path.read_text(encoding="utf-8").splitlines()


def _delimited(path, mark):
    raw = _lines(path)
    names = raw[0].split(mark)
    return [dict(zip(names, row.split(mark))) for row in raw[1:] if row]


def _commas(path):
    import csv as _csv
    with path.open(newline="", encoding="utf-8") as handle:
        return list(_csv.DictReader(handle))


def _ndjson(path):
    return [json.loads(row) for row in _lines(path) if row.strip()]


def _flat(path):
    found = {}
    for row in _lines(path):
        row = row.strip()
        if row and row[0] != "#" and "=" in row:
            name, value = row.split("=", 1)
            found[name.strip()] = value.strip()
    return found


def _sections(path):
    cfg = configparser.ConfigParser()
    cfg.read_string(path.read_text(encoding="utf-8"))
    return cfg


def _tomlfile(path):
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _fixed(path, widths):
    def carve(row):
        parts, at = [], 0
        for width in widths:
            parts.append(row[at:at + width].strip())
            at += width
        return parts

    raw = _lines(path)
    names = carve(raw[0])
    return [dict(zip(names, carve(row))) for row in raw[1:] if row.strip()]


def _blocks(path):
    found, item = [], {}
    for row in path.read_text(encoding="utf-8").splitlines():
        if not row.strip():
            if item:
                found.append(item)
                item = {}
            continue
        if ":" in row:
            name, value = row.split(":", 1)
            item[name.strip()] = value.strip()
    if item:
        found.append(item)
    return found


def _is_on(value):
    """Standard section 3: in scope when the marker is Y, yes or true.

    A JSON or TOML boolean true is the marker true; boolean false is not.
    """
    if isinstance(value, bool):
        return value
    return str(value).strip() in ("Y", "yes", "true")


def _nfc(text):
    return unicodedata.normalize("NFC", str(text))


def _reference_model(dd: Path) -> dict:
    """Everything the standard defines, derived here and not from the submission."""
    # ---- registers
    strata = {_nfc(r["stratum_code"]): r
              for r in _delimited(dd / "ref__stratum-params.tsv", "\t") if _is_on(r["active"])}
    areas = {_nfc(r["region_code"]): r for r in _commas(dd / "ref__region-codes.csv")
             if _is_on(r["active"])}
    tenure_doc = json.loads((dd / "ref__tenure-classes.json").read_text(encoding="utf-8"))
    tenure_class = {_nfc(k): _nfc(v["tenure_class"]) for k, v in tenure_doc["classes"].items()
                    if _is_on(v.get("active", True))}
    grade_flat = _flat(dd / "ref__band-definitions.properties")
    grade_rows = {}
    for name, value in grade_flat.items():
        if name.startswith("band."):
            _, level, field = name.split(".", 2)
            grade_rows.setdefault(_nfc(level), {})[field] = value
    grade_order = sorted(grade_rows, key=lambda k: int(grade_rows[k]["sort_rank"]))
    grade_span = {k: (int(v["lower_hours_inclusive"]), int(v["upper_hours_inclusive"]))
                  for k, v in grade_rows.items()}
    outcomes = {_nfc(r["disposition_code"]): r
                for r in _commas(dd / "rules__disposition-precedence.csv")
                if _is_on(r["active"])}
    touch_ranges = []
    for row in _lines(dd / "ref__contact-bands.sexp"):
        found = dict(re.findall(r"\(([a-z-]+) ([^()\s]+)\)", row))
        if row.startswith("(contact-band") and _is_on(found.get("active")):
            touch_ranges.append((int(found["min-attempts"]), int(found["max-attempts"]),
                                 _nfc(found["code"])))
    cell_rules = _tomlfile(dd / "rules__adjustment-cells.toml")
    margin_cfg = _sections(dd / "rules__margin-order.ini")
    margin_names = sorted(_nfc(s.split(".", 1)[1]) for s in margin_cfg.sections()
                          if s.startswith("margin.") and _is_on(margin_cfg[s]["active"]))
    listed_order = [_nfc(s.split(".", 1)[1]) for s in margin_cfg.sections()
                    if s.startswith("margin.") and _is_on(margin_cfg[s]["active"])]
    tolerance = int(margin_cfg["raking"]["tolerance_uw"])
    iteration_cap = int(margin_cfg["raking"]["max_iterations"])
    pilot = _pilot_settings(dd, margin_names, tolerance, iteration_cap)
    trim_cfg = _flat(dd / "rules__trimming.conf")
    limits = _tomlfile(dd / "disclosure__parameters.toml")
    sub_cfg = _flat(dd / "frame__subsample.conf")
    prior_one = {_fold_unit(r["unit_id"]): _nfc(r["prior_band"])
                 for r in _commas(dd / "prior__wave1-bands.csv") if _is_on(r["active"])}
    prior_two = {_fold_unit(r["unit_id"]): _nfc(r["prior_band"])
                 for r in _ndjson(dd / "prior__wave2-bands.jsonl") if _is_on(r["active"])}
    registry = [r for r in _commas(dd / "disclosure__cell-registry.csv")
                if _is_on(r["active"])]

    def levels_of(table, axis):
        picked = [r for r in registry if r["table_name"] == table and r["axis"] == axis]
        return [_nfc(r["level_key"]) for r in sorted(picked, key=lambda r: int(r["sort_rank"]))]

    def grade_at(hours):
        for level in grade_order:
            low, high = grade_span[level]
            if low <= hours <= high:
                return level
        return grade_order[-1]

    # ---- control totals
    scale_of = {_nfc(r["unit_name"]): Decimal(r["persons_per_unit"])
                for r in _commas(dd / "bench__unit-conversions.csv") if _is_on(r["active"])}
    bids = {}

    def bid(dimension, level, rank, value, unit, source, published, period):
        if period != PERIOD:
            return
        bids.setdefault((_nfc(dimension), _nfc(level)), []).append(
            (int(rank), published, source,
             int(Decimal(str(value)) * scale_of[_nfc(unit)] * UNIT_SCALE)))

    doc = json.loads((dd / "bench__region-tenure-v1.json").read_text(encoding="utf-8"))
    for entry in doc["series"]:
        bid(doc["dimension"], entry["key"], entry["rank"], entry["value"], doc["unit"],
            doc["source_id"], doc["published_date"], entry["reference_period"])
    doc = _tomlfile(dd / "bench__region-tenure-v2.toml")
    for entry in doc["series"]:
        bid(doc["dimension"], entry["key"], entry["rank"], entry["value"], doc["unit"],
            doc["source_id"], doc["published_date"], entry["reference_period"])
    cfg = _sections(dd / "bench__region-tenure-v3.ini")
    top = cfg["meta"]
    for name in cfg.sections():
        if name.startswith("series."):
            entry = cfg[name]
            bid(top["dimension"], entry["key"], entry["rank"], entry["value"],
                top["unit"], top["source_id"], top["published_date"],
                entry["reference_period"])
    for entry in _commas(dd / "bench__activity-v1.csv"):
        bid(entry["dimension"], entry["level_key"], entry["rank"], entry["value"],
            entry["unit"], entry["source_id"], entry["published_date"],
            entry["reference_period"])
    doc = json.loads((dd / "bench__activity-v2.json").read_text(encoding="utf-8"))
    for entry in doc["series"]:
        bid(doc["dimension"], entry["key"], entry["rank"], entry["value"], doc["unit"],
            doc["source_id"], doc["published_date"], entry["reference_period"])
    band_flat = _flat(dd / "bench__band-v1.properties")
    band_rows = {}
    for name, value in band_flat.items():
        if name.startswith("series."):
            _, index, field = name.split(".", 2)
            band_rows.setdefault(index, {})[field] = value
    for entry in band_rows.values():
        bid(band_flat["dimension"], entry["key"], entry["rank"], entry["value"],
            band_flat["unit"], band_flat["source_id"], band_flat["published_date"],
            entry["reference_period"])
    doc = _tomlfile(dd / "bench__band-v2.toml")
    for entry in doc["series"]:
        bid(doc["dimension"], entry["key"], entry["rank"], entry["value"], doc["unit"],
            doc["source_id"], doc["published_date"], entry["reference_period"])

    controls, chosen = {}, {}
    for (dimension, level), offers in bids.items():
        offers.sort(key=lambda o: (o[0], o[1], o[2]))
        rank, published, source, persons = offers[-1]
        controls.setdefault(dimension, {})[level] = persons
        chosen["%s|%s" % (dimension, level)] = (rank, source)

    # ---- frame
    label_to_code = {}
    for code, row in strata.items():
        label = "%s %s" % (areas.get(_nfc(row["region_code"]), {}).get("region_name", ""),
                           row["stratum_group"])
        label_to_code[_nfc(label)] = code
    tally = dict.fromkeys(REPAIR_CODES, 0)
    gathered = []

    def absorb(rid, area, serial, stratum, psu, rank, stamp, holding):
        # Outside the frame contributes nothing, its repairs included.
        stratum = _nfc(stratum)
        if stratum not in strata:
            if stratum not in label_to_code:
                return
            tally["M7"] += 1
            stratum = label_to_code[stratum]
        if serial != serial.strip():
            tally["M1"] += 1
        serial = serial.strip()
        if len(serial) < 6:
            tally["M2"] += 1
            serial = serial.zfill(6)
        if area != area.upper():
            tally["M3"] += 1
        area = _nfc(area.upper())
        gathered.append((area, serial, int(rank), stamp, rid, stratum, _nfc(psu.strip()),
                         _nfc(holding)))

    for row in _commas(dd / "frame__register-a.csv"):
        absorb(row["record_id"], row["region_code"], row["serial"], row["stratum"],
               row["psu_code"], row["vintage_rank"], row["edit_timestamp"], row["tenure"])
    for row in _delimited(dd / "frame__register-b.tsv", "\t"):
        absorb(row["record_id"], row["region_code"], row["serial"], row["stratum"],
               row["psu_code"], row["vintage_rank"], row["edit_timestamp"], row["tenure"])
    for row in _fixed(dd / "frame__register-c.fwf", FRAME_WIDTHS):
        absorb(row["record_id"], row["reg"], row["serial"], row["strat"], row["psu"],
               row["vr"], row["edit_timestamp"], row["tenure"])
    reissue_psu = {}
    for row in _ndjson(dd / "frame__register-d.jsonl"):
        name = _fold_unit(row["unit_id"])
        if name is not None:
            reissue_psu[name] = _nfc(row["psu_code"])

    pile = {}
    for item in gathered:
        pile.setdefault(item[0:2], []).append(item)
    units, dropped = {}, []
    for identity, items in pile.items():
        items.sort(key=lambda i: (i[2], i[3], i[4]))
        if len(items) > 1:
            tally["M8"] += len(items) - 1
            dropped.extend(i[4] for i in items[:-1])
        keep = items[-1]
        name = "RH-%s-%s" % identity
        units[name] = {"region_code": identity[0], "stratum": keep[5],
                       "psu": keep[6] or reissue_psu.get(name, ""), "holding": keep[7]}

    loops, orphans = [], []
    for block in _blocks(dd / "frame__addresses.rfc822"):
        name = _fold_unit(block.get("Unit-Id", ""))
        if name is None or name not in units:
            continue
        raw = block.get("Dwelling-Units", "").strip()
        if raw == "":
            tally["M4"] += 1
            units[name]["dwelling_units"] = 1
        else:
            units[name]["dwelling_units"] = int(raw)
        parent = block.get("Parent-Unit", "").strip()
        if parent:
            folded = _fold_unit(parent)
            if folded == name:
                tally["M5"] += 1
                loops.append(name)
            elif folded not in units:
                tally["M6"] += 1
                orphans.append(name)
    for name, row in units.items():
        row["sub"] = _is_on(sub_cfg.get("unit.%s.subsampled" % name, "no"))
        row.setdefault("dwelling_units", 1)

    # ---- dispositions
    log, fixes = {}, {}

    def note(raw_unit, wave, attempt, stamp, code):
        name, code = _fold_unit(raw_unit), _nfc(code)
        if name is None or name not in units or code not in outcomes:
            return
        moment, shown = _instant(stamp)
        log.setdefault((name, int(wave)), []).append(
            (int(outcomes[code]["severity_rank"]), moment, int(attempt), code, shown))

    grab = re.compile(r'unit="([^"]+)"\s+attempt="(\d+)"\s+outcome="([^"]+)"\s+wave="(\d+)"')
    for row in _lines(dd / "contact__log-w1.rfc5424"):
        hit = grab.search(row)
        if hit:
            note(hit.group(1), hit.group(4), hit.group(2), row.split(" ")[1], hit.group(3))
    for name in ("contact__log-w2.logfmt", "contact__log-w3.logfmt"):
        for row in _lines(dd / name):
            kv = dict(p.split("=", 1) for p in row.split(" ") if "=" in p)
            if not _is_on(kv.get("active")):
                continue
            if "correction" in kv:
                name = _fold_unit(kv["unit"])
                if name is not None:
                    fixes.setdefault((name, int(kv["wave"]), int(kv["attempt"])), []).append(
                        (_instant(kv["ts"])[0], _nfc(kv["correction"]) == "reinstate"))
                continue
            note(kv["unit"], kv["wave"], kv["attempt"], kv["ts"], kv["outcome"])
    for row in _commas(dd / "contact__outcomes.csv"):
        if _is_on(row["active"]):
            note(row["unit_id"], row["wave"], row["attempt_no"],
                 row["contact_datetime"], row["outcome_code"])
    for row in _ndjson(dd / "contact__reissues.jsonl"):
        if _is_on(row["active"]):
            note(row["unit_id"], row["wave"], row["attempt_no"],
                 row["contact_datetime"], row["outcome_code"])

    voided = {key for key, marks in fixes.items() if not max(marks)[1]}
    verdicts = {}
    for identity, events in log.items():
        kept = sorted(e for e in events if (identity[0], identity[1], e[2]) not in voided)
        if not kept:
            continue
        _, _, attempt, code, shown = kept[-1]
        row = outcomes[code]
        verdicts[identity] = {"disposition": code, "attempt_no": attempt,
                              "resolved_utc": shown, "attempts": len(events),
                              "eligible": _is_on(row["eligible"]),
                              "responding": _is_on(row["responding"]),
                              "superseded": _is_on(row["superseded"])}

    # The contact band is derived from the attempt records of the prior waves.
    for name, row in units.items():
        seen = len(log.get((name, 1), ())) + len(log.get((name, 2), ()))
        row["contact_band"] = next((code for low, high, code in sorted(touch_ranges)
                                    if low <= seen <= high), "")

    # ---- interviews
    sheets = [("interview__w1-q1.csv", "comma"), ("interview__w1-q2.psv", "pipe"),
              ("interview__w1-q3.jsonl", "lines"), ("interview__w1-q4.tsv", "tab"),
              ("interview__w2-q1.csv", "comma"), ("interview__w2-q2.fwf", "fixed"),
              ("interview__w2-q3.jsonl", "lines"), ("interview__w2-q4.psv", "pipe"),
              ("interview__w3-q1.csv", "comma"), ("interview__w3-q2.tsv", "tab"),
              ("interview__w3-q3.fwf", "fixed"), ("interview__w3-q4.psv", "pipe")]
    answers = {}
    for name, shape in sheets:
        path = dd / name
        if shape == "comma":
            rows = _commas(path)
        elif shape == "pipe":
            rows = _delimited(path, "|")
        elif shape == "tab":
            rows = _delimited(path, "\t")
        elif shape == "fixed":
            rows = _fixed(path, SHEET_WIDTHS)
        else:
            rows = _ndjson(path)
        for row in rows:
            if not _is_on(row.get("active")):
                continue
            name_folded = _fold_unit(str(row["unit_id"]))
            if name_folded is None or name_folded not in units:
                continue
            hours = str(row["hours_worked"]).strip()
            answers[(name_folded, int(row["wave"]))] = {
                "status": _nfc(row["activity_code"]), "sector_code": _nfc(row["sector_code"]),
                "hours": None if hours == "" else int(hours)}

    def grade_for(name, wave):
        row = answers.get((name, wave))
        if row is None:
            return None
        if row["hours"] is not None:
            return grade_at(row["hours"])
        if wave == WAVE:
            earlier = answers.get((name, 2))
            if earlier is not None and earlier["hours"] is not None:
                return grade_at(earlier["hours"])
            if name in prior_two:
                return prior_two[name]
        if name in prior_one:
            return prior_one[name]
        return grade_at(0)

    eligible = {n for n in units
                if verdicts.get((n, WAVE), {}).get("eligible")
                and units[n]["dwelling_units"] != 0}
    responding = {n for n in eligible
                  if verdicts[(n, WAVE)]["responding"]
                  and not verdicts[(n, WAVE)]["superseded"] and (n, WAVE) in answers}

    per_stratum = {}
    for row in units.values():
        per_stratum[row["stratum"]] = per_stratum.get(row["stratum"], 0) + 1
    sub_share = int(sub_cfg["subsample_factor_bp"])
    design = {}
    for name, row in units.items():
        value = _round_ratio(UNIT_SCALE * int(strata[row["stratum"]]["population_units"]),
                             per_stratum[row["stratum"]])
        design[name] = _round_ratio(value * 10000, sub_share) if row["sub"] else value

    axis_keys = {
        "region_tenure": {n: "%s|%s" % (units[n]["region_code"], units[n]["holding"])
                          for n in responding},
        "activity": {n: answers[(n, WAVE)]["status"] for n in responding},
        "band": {n: grade_for(n, WAVE) for n in responding},
    }

    return SimpleNamespace(**{
        "strata": strata, "units": units, "tally": tally, "loops": loops,
        "orphans": orphans, "dropped": dropped, "verdicts": verdicts,
        "answers": answers, "eligible": eligible, "responding": responding,
        "design": design, "controls": controls, "chosen": chosen,
        "axis_keys": axis_keys, "tenure_class": tenure_class,
        "cell_rules": cell_rules, "margin_seq": pilot["order"],
        "rounding": pilot["rounding"], "pilot": pilot, "listed_order": listed_order,
        "tolerance": tolerance, "max_iterations": iteration_cap,
        "trim_cfg": trim_cfg, "limits": limits, "levels_of": levels_of,
        "grade_for": grade_for, "sub_share": sub_share})


def _pilot_settings(dd, names, tolerance, cap):
    """The one margin order and rounding point that reproduce the pilot figures."""
    from itertools import permutations
    doc = json.loads((dd / "calib__pilot-round.json").read_text(encoding="utf-8"))
    rows = [r for r in doc["units"] if _is_on(r["active"])]
    start = {r["pilot_id"]: int(r["adjusted_weight_uw"]) for r in rows}
    axis = {d: {r["pilot_id"]: _nfc(r[d]) for r in rows} for d in names}
    targets = {d: {_nfc(k): int(v) for k, v in doc["controls_uw"][d].items()} for d in names}
    published = doc["published"]
    wanted = [("iterations_used", published["iterations_used"])] + [
        ((d, _nfc(k)), int(v)) for d, levels in published["raked_totals_uw"].items()
        for k, v in levels.items()]
    scores = {}
    for order in permutations(names):
        for rounding in ROUNDINGS:
            got, _, used, _ = _rake(start, axis, targets, list(order), tolerance, cap, rounding)
            figures = _pilot_figures(got, axis, used)
            seen = dict([("iterations_used", figures["iterations_used"])] + [
                ((d, k), v) for d, levels in figures["raked_totals_uw"].items()
                for k, v in levels.items()])
            scores[(order, rounding)] = sum(1 for key, value in wanted if seen.get(key) == value)
    winners = [k for k, n in scores.items() if n == len(wanted)]
    if len(winners) != 1:
        raise ValueError("the pilot does not single out one combination")
    order, rounding = winners[0]
    return {"order": list(order), "rounding": rounding, "figures": len(wanted),
            "runner_up": max(n for k, n in scores.items() if k != winners[0])}


def _cell_of(name, model, depth):
    row = model.units[name]
    klass = model.tenure_class.get(row["holding"], "owner")
    if depth == 0:
        return "%s|%s|%s" % (row["stratum"], klass, row["contact_band"])
    if depth == 1:
        return "%s|%s" % (row["stratum"], klass)
    return row["stratum"]


def _rake(start, axis_keys, controls, order, tolerance, cap, rounding="margin"):
    """Rake `start` onto `controls`, margins in `order`.

    rounding "margin": every weight is rounded each time a margin rescales it.
    rounding "iteration": weights stay exact through the margins of one
    iteration and are rounded once when the iteration ends.
    """
    from fractions import Fraction
    where = {}
    for dimension in order:
        pockets = {}
        for name in start:
            pockets.setdefault(axis_keys[dimension][name], []).append(name)
        where[dimension] = pockets
    live = dict(start)
    steps, rounds, settled = [], 0, False
    for index in range(1, cap + 1):
        rounds = index
        exact = {n: Fraction(v) for n, v in live.items()}
        for dimension in order:
            for level, group in where[dimension].items():
                goal = controls[dimension].get(level)
                if goal is None:
                    continue
                held = sum(exact[n] for n in group)
                if held <= 0:
                    continue
                for name in group:
                    scaled = exact[name] * goal / held
                    if rounding == "margin":
                        scaled = Fraction(_round_ratio(scaled.numerator, scaled.denominator))
                    exact[name] = scaled
        live = {n: _round_ratio(v.numerator, v.denominator) for n, v in exact.items()}
        drift = 0
        for dimension in order:
            for level, goal in controls[dimension].items():
                held = sum(live[n] for n in where[dimension].get(level, ()))
                drift = max(drift, abs(held - goal))
        steps.append({"iteration": index, "max_deviation_uw": drift})
        if drift <= tolerance:
            settled = True
            break
    return live, steps, rounds, settled


def _chain(model, design, eligible, responding, axis_keys, order=None, cap=None,
           trigger=None, rounding=None):
    """Nonresponse adjustment, raking and trimming over one set of design weights."""
    rules = model.cell_rules
    floor_rate = int(rules["min_response_rate_bp"])
    floor_count = int(rules["min_cell_count"])
    depth = dict.fromkeys(eligible, 0)

    def totals():
        wide, narrow, heads = {}, {}, {}
        for name in eligible:
            key = _cell_of(name, model, depth[name])
            wide[key] = wide.get(key, 0) + design[name]
            if name in responding:
                narrow[key] = narrow.get(key, 0) + design[name]
                heads[key] = heads.get(key, 0) + 1
        return wide, narrow, heads

    passes = 0
    while passes < int(rules["max_collapse_rounds"]):
        wide, narrow, heads = totals()
        weak = {k for k, v in wide.items()
                if (_round_ratio(10000 * narrow.get(k, 0), v) if v else 0) < floor_rate
                or heads.get(k, 0) < floor_count}
        shifted = False
        for name in eligible:
            if _cell_of(name, model, depth[name]) in weak and depth[name] < 2:
                depth[name] += 1
                shifted = True
        passes += 1
        if not shifted:
            break

    wide, narrow, heads = totals()
    lift, listing = {}, []
    for key in sorted(wide):
        got = narrow.get(key, 0)
        lift[key] = _round_ratio(UNIT_SCALE * wide[key], got) if got else 0
        listing.append({"cell_key": key, "depth": key.count("|"),
                        "eligible_weight_uw": wide[key], "responding_weight_uw": got,
                        "responding_count": heads.get(key, 0),
                        "response_rate_bp": _round_ratio(10000 * got, wide[key])
                        if wide[key] else 0,
                        "adjustment_factor_uw": lift[key]})

    scaled = {n: _round_ratio(design[n] * lift[_cell_of(n, model, depth[n])], UNIT_SCALE)
              for n in responding}

    live, steps, rounds, settled = _rake(scaled, axis_keys, model.controls,
                                         order or model.margin_seq, model.tolerance,
                                         cap or model.max_iterations,
                                         rounding or model.rounding)

    ratio = int(model.trim_cfg["trim_ratio_bp"])
    trigger = int(model.trim_cfg["trim_trigger_deff_bp"]) if trigger is None else trigger
    pens = {}
    for name in responding:
        pens.setdefault(model.units[name]["stratum"], []).append(name)
    settledw = dict(live)
    clipped, roofs, spared, gated = [], {}, 0, []
    for pen in sorted(pens):
        crowd = pens[pen]
        ranked = sorted(settledw[n] for n in crowd)
        middle = ranked[(len(ranked) - 1) // 2]
        roof = _round_ratio(middle * ratio, 10000)
        roofs[pen] = roof
        heap = sum(ranked)
        effect = _round_ratio(10000 * len(ranked) * sum(v * v for v in ranked),
                              heap * heap) if heap else 0
        if effect <= trigger:
            spared += sum(1 for v in ranked if v > roof)
            continue
        gated.append(pen)
        spill, tall = 0, []
        for name in crowd:
            if settledw[name] > roof:
                spill += settledw[name] - roof
                tall.append(name)
                settledw[name] = roof
        if not spill:
            continue
        clipped.extend(tall)
        tall_set = set(tall)
        short = [n for n in crowd if n not in tall_set]
        floorsum = sum(settledw[n] for n in short)
        if floorsum <= 0:
            continue
        paid = 0
        for name in short:
            part = _round_ratio(spill * settledw[name], floorsum)
            settledw[name] += part
            paid += part
        rest = spill - paid
        if rest:
            settledw[sorted(short, key=lambda n: (-settledw[n], n))[0]] += rest

    return SimpleNamespace(**{"cells": listing, "rounds": passes, "depth": depth, "lift": lift,
            "scaled": scaled, "raked": live, "final": settledw,
            "clipped": sorted(clipped), "roofs": roofs, "spared": spared, "gated": gated,
            "trace": {"iterations_used": rounds, "converged": settled,
                      "final_max_deviation_uw": steps[-1]["max_deviation_uw"] if steps else 0,
                      "per_iteration": steps}})


def _pens(model):
    held = {}
    for row in model.units.values():
        held.setdefault(row["stratum"], set()).add(row["psu"])
    home = {pen: pen for pen in held}
    for pen in sorted(held):
        if len(held[pen]) < 2:
            mate = model.strata[pen]["collapse_partner"]
            if mate in held:
                home[pen] = home.get(mate, mate)
    merged, inside = {}, {}
    for pen, group in home.items():
        merged.setdefault(group, set()).update(held[pen])
        inside.setdefault(group, []).append(pen)
    return ({g: sorted(p) for g, p in merged.items() if len(p) >= 2}, home,
            {g: sorted(v) for g, v in inside.items()})


def _crosstab(names, weight, rows, cols, row_levels, col_levels):
    grid = {"%s|%s" % (r, c): [0, 0, 0] for r in row_levels for c in col_levels}
    for name in names:
        slot = grid.get("%s|%s" % (rows.get(name), cols.get(name)))
        if slot is None:
            continue
        slot[0] += weight[name]
        slot[1] += 1
        slot[2] = max(slot[2], weight[name])
    return grid


def _dump_json(payload):
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _dump_rows(head, rows, mark):
    return "\n".join([mark.join(head)]
                     + [mark.join(str(c) for c in r) for r in rows]) + "\n"


def _yn(flag):
    return "Y" if flag else "N"


def expected(dd: Path) -> dict:
    """The exact bytes every artifact must carry, derived from the extract."""
    run = _derive(_reference_model(dd))
    pub = _publication(run.tables, run.shape, run.model.limits)
    return _render(run.model, run.full, run.final, run.groups, run.inside, run.replicas,
                   run.tables, run.spread, run.shares, *pub)


def _derive(model, cap=None):
    """The weighting chain, the replicate replays and the four tables."""
    units, responding, eligible = model.units, model.responding, model.eligible
    design = model.design
    axis_keys = model.axis_keys

    full = _chain(model, design, eligible, responding, axis_keys)
    final = full.final
    groups, home, inside = _pens(model)

    replicas = []
    for group in sorted(groups):
        size = len(groups[group])
        for gone in groups[group]:
            rebased = {}
            for name, value in design.items():
                if home[units[name]["stratum"]] != group:
                    rebased[name] = value
                elif units[name]["psu"] == gone:
                    rebased[name] = 0
                else:
                    rebased[name] = _round_ratio(value * size, size - 1)
            alive = {n for n in responding if rebased[n] > 0}
            alive_eligible = {n for n in eligible if rebased[n] > 0}
            trimmed_keys = {d: {n: axis_keys[d][n] for n in alive} for d in axis_keys}
            piece = _chain(model, rebased, alive_eligible, alive, trimmed_keys, cap=cap)
            replicas.append({"replicate_id": "%s::%s" % (group, gone), "group": group,
                             "dropped_psu": gone, "group_size": size,
                             "iterations_used": piece.trace["iterations_used"],
                             "converged": piece.trace["converged"],
                             "trimmed_count": len(piece.clipped),
                             "final_total_uw": sum(piece.final.values()),
                             "weights": piece.final, "responding": alive})

    ladder = sorted(responding, key=lambda n: (final[n], n))
    span = len(ladder)
    fifth = {n: "Q%d" % (1 + (5 * i) // span) for i, n in enumerate(ladder)} if span else {}

    rows_of = {"activity_by_region": {n: model.answers[(n, WAVE)]["status"]
                                      for n in responding},
               "tenure_by_wquintile": {n: units[n]["holding"] for n in responding},
               "hours_by_sector": {n: model.answers[(n, WAVE)]["sector_code"]
                                   for n in responding},
               "band_transition": {n: model.grade_for(n, 1) for n in responding}}
    cols_of = {"activity_by_region": {n: units[n]["region_code"] for n in responding},
               "tenure_by_wquintile": fifth,
               "hours_by_sector": {n: model.grade_for(n, WAVE) for n in responding},
               "band_transition": {n: model.grade_for(n, WAVE) for n in responding}}

    shape = {t: (model.levels_of(t, "row"), model.levels_of(t, "column"))
             for t in TABLES}
    anchor = {t: _crosstab(responding, final, rows_of[t], cols_of[t], *shape[t])
              for t in TABLES}
    spread = {t: {k: 0 for k in anchor[t]} for t in TABLES}
    shares = {t: {} for t in TABLES}
    for replica in replicas:
        size = replica["group_size"]
        for table in TABLES:
            grid = _crosstab(replica["responding"], replica["weights"], rows_of[table],
                             cols_of[table], *shape[table])
            running = shares[table].setdefault(replica["group"], 0)
            gained = 0
            for key, slot in anchor[table].items():
                gap = grid[key][0] - slot[0]
                bit = ((size - 1) * gap * gap) // size
                spread[table][key] += bit
                gained += bit
            shares[table][replica["group"]] = running + gained

    tables = {}
    for table in TABLES:
        row_levels, col_levels = shape[table]
        listing = []
        for row in row_levels:
            for col in col_levels:
                key = "%s|%s" % (row, col)
                total, heads, biggest = anchor[table][key]
                err = _root(spread[table][key])
                listing.append({
                    "cell_key": key, "row_level": row, "column_level": col,
                    "point_estimate_uw": total, "unweighted_count": heads,
                    "standard_error_uw": err,
                    "cv_bp": _round_ratio(10000 * err, total) if total > 0 else 0,
                    "dominance_bp": _round_ratio(10000 * biggest, total) if total > 0 else 0})
        tables[table] = listing

    return SimpleNamespace(model=model, full=full, final=final, groups=groups,
                           inside=inside, replicas=replicas, tables=tables,
                           spread=spread, shares=shares, shape=shape)


def _publication(tables, shape, limits, floor_heads=None, roof_cv=None, cascade_cap=None):
    """Screening, the cross table ranking and the secondary cascade."""
    floor_heads = int(limits["min_publish_count"]) if floor_heads is None else floor_heads
    roof_cv = int(limits["max_publish_cv_bp"]) if roof_cv is None else roof_cv
    roof_dom = int(limits["dominance_bp"])
    cascade_cap = int(limits["max_cascade_rounds"]) if cascade_cap is None else cascade_cap
    order = sorted(((r["cv_bp"], r["cell_key"], t) for t in TABLES for r in tables[t]),
                   key=lambda x: (-x[0], x[2], x[1]))
    place = {(t, k): i + 1 for i, (_, k, t) in enumerate(order)}

    screening, first = {}, {}
    for table in TABLES:
        board, hits = [], []
        for record in tables[table]:
            causes = []
            if record["unweighted_count"] < floor_heads:
                causes.append("count")
            if record["cv_bp"] > roof_cv:
                causes.append("cv")
            if record["dominance_bp"] > roof_dom:
                causes.append("dominance")
            board.append({"cell_key": record["cell_key"],
                          "screening_rank": place[(table, record["cell_key"])],
                          "cv_bp": record["cv_bp"],
                          "dominance_bp": record["dominance_bp"],
                          "unweighted_count": record["unweighted_count"],
                          "reasons": causes})
            if causes:
                hits.append({"cell_key": record["cell_key"], "reasons": causes})
        screening[table] = sorted(board, key=lambda r: r["screening_rank"])
        first[table] = sorted(hits, key=lambda r: r["cell_key"])

    second, spins = {}, {}
    for table in TABLES:
        row_levels, col_levels = shape[table]
        lookup = {r["cell_key"]: r for r in tables[table]}
        hidden = {h["cell_key"] for h in first[table]}
        extra, turn = [], 0
        while turn < cascade_cap:
            turn += 1
            moved = False
            strips = ([("row", r, ["%s|%s" % (r, c) for c in col_levels])
                       for r in row_levels]
                      + [("column", c, ["%s|%s" % (r, c) for r in row_levels])
                         for c in col_levels])
            for axis, level, keys in strips:
                if len([k for k in keys if k in hidden]) != 1:
                    continue
                free = [k for k in keys if k not in hidden]
                if not free:
                    continue
                free.sort(key=lambda k: (lookup[k]["unweighted_count"], k))
                hidden.add(free[0])
                extra.append({"cell_key": free[0], "axis": axis,
                              "axis_level": level, "round": turn})
                moved = True
            if not moved:
                break
        second[table] = sorted(extra, key=lambda r: r["cell_key"])
        spins[table] = turn

    return screening, first, second, spins, place


def disclosure_facts(dd: Path) -> dict:
    """The closing-summary figures the judged channel names; no check reads them."""
    model = _reference_model(dd)
    run = _derive(model)
    limits = model.limits

    def status(pub):
        _, first, second, _, _ = pub
        return {(t, r["cell_key"]) for t in TABLES for r in first[t] + second[t]}

    base = status(_publication(run.tables, run.shape, limits))
    stricter_count = status(_publication(run.tables, run.shape, limits,
                                         floor_heads=int(limits["min_publish_count"]) + 2))
    stricter_cv = status(_publication(run.tables, run.shape, limits,
                                      roof_cv=int(limits["max_publish_cv_bp"]) - 500))
    one_pass = status(_publication(run.tables, run.shape, limits, cascade_cap=1))
    listed = _chain(model, model.design, model.eligible, model.responding, model.axis_keys,
                    order=model.listed_order)
    trigger = int(model.trim_cfg["trim_trigger_deff_bp"]) + 100
    raised = _chain(model, model.design, model.eligible, model.responding, model.axis_keys,
                    trigger=trigger)
    longer = _derive(model, cap=2 * model.max_iterations)
    settled_later = max(b["iterations_used"] for b in longer.replicas)
    other = [r for r in ROUNDINGS if r != model.rounding][0]
    flipped = _chain(model, model.design, model.eligible, model.responding, model.axis_keys,
                     rounding=other)
    return {
        "final_deviation_other_rounding_point_uw": flipped.trace["final_max_deviation_uw"],
        "pilot_runner_up_matches": model.pilot["runner_up"],
        "pilot_figures": model.pilot["figures"],
        "status_changes_count_plus_two": len(base ^ stricter_count),
        "status_changes_cv_minus_500": len(base ^ stricter_cv),
        "final_total_listed_order_uw": sum(listed.final.values()),
        "strata_trimmed_trigger_plus_100": len(raised.gated),
        "slowest_replicate_iterations_double_cap": settled_later,
        "suppressed_cells_single_pass": len(one_pass),
    }


def _render(model, full, final, groups, inside, replicas, tables, spread, shares,
            screening, first, second, spins, place):
    units, responding = model.units, model.responding
    controls = model.controls
    grand = sum(controls["region_tenure"].values())
    out = {}

    out["frame_audit.json"] = _dump_json({
        "repair_counts": dict(sorted(model.tally.items())),
        "self_referencing_units": sorted(model.loops),
        "dangling_parent_units": sorted(model.orphans),
        "discarded_record_ids": sorted(model.dropped),
        "resolved_unit_count": len(units),
        "subsample_factor_bp": model.sub_share})

    out["control_totals.json"] = _dump_json({
        "reference_period": PERIOD, "grand_total_uw": grand,
        "dimensions": {d: dict(sorted(v.items())) for d, v in controls.items()},
        "level_counts": {d: len(v) for d, v in controls.items()}})

    heads, block = {}, {}
    for (name, wave), row in model.verdicts.items():
        if wave != WAVE:
            continue
        heads[row["disposition"]] = heads.get(row["disposition"], 0) + 1
        block[name] = {"disposition": row["disposition"], "attempt_no": row["attempt_no"],
                       "resolved_utc": row["resolved_utc"], "attempts": row["attempts"]}
    out["response_status.json"] = _dump_json({
        "reference_wave": WAVE, "disposition_counts": dict(sorted(heads.items())),
        "eligible_count": len(model.eligible),
        "responding_count": len(responding),
        "superseded_units": sorted(n for (n, w), r in model.verdicts.items()
                                   if w == WAVE and r["superseded"]),
        "units": block})

    out["design_weights.csv"] = _dump_rows(
        ["unit_id", "stratum", "psu_code", "subsampled", "design_weight_uw"],
        [[n, units[n]["stratum"], units[n]["psu"], _yn(units[n]["sub"]),
          model.design[n]] for n in sorted(units)], ",")

    out["control_margins.tsv"] = _dump_rows(
        ["dimension", "level_key", "control_total_uw", "chosen_rank", "chosen_source"],
        [[d, k, controls[d][k], model.chosen["%s|%s" % (d, k)][0],
          model.chosen["%s|%s" % (d, k)][1]]
         for d in sorted(controls) for k in sorted(controls[d])], "\t")

    out["adjustment_cells.json"] = _dump_json({
        "collapse_rounds": full.rounds, "cell_count": len(full.cells),
        "cells": full.cells,
        "depth_counts": {str(d): sum(1 for c in full.cells if c["depth"] == d)
                         for d in (0, 1, 2)}})

    out["adjusted_weights.csv"] = _dump_rows(
        ["unit_id", "cell_key", "adjustment_factor_uw", "adjusted_weight_uw"],
        [[n, _cell_of(n, model, full.depth[n]),
          full.lift[_cell_of(n, model, full.depth[n])], full.scaled[n]]
         for n in sorted(responding)], ",")

    out["raking_trace.json"] = _dump_json({
        "margin_order": model.margin_seq, "tolerance_uw": model.tolerance,
        "max_iterations": model.max_iterations,
        "iterations_used": full.trace["iterations_used"],
        "converged": full.trace["converged"],
        "final_max_deviation_uw": full.trace["final_max_deviation_uw"],
        "per_iteration": full.trace["per_iteration"]})

    clipped = set(full.clipped)
    out["final_weights.csv"] = _dump_rows(
        ["unit_id", "stratum", "raked_weight_uw", "trimmed", "final_weight_uw"],
        [[n, units[n]["stratum"], full.raked[n], _yn(n in clipped), final[n]]
         for n in sorted(responding)], ",")

    weight_sum = sum(final.values())
    squares = sum(v * v for v in final.values())
    count = len(final)
    pen_totals = {}
    for name in responding:
        pen = units[name]["stratum"]
        pen_totals[pen] = pen_totals.get(pen, 0) + final[name]
    ladder = sorted(final.values())
    out["weight_diagnostics.json"] = _dump_json({
        "responding_count": count, "final_weight_total_uw": weight_sum,
        "design_effect_bp": _round_ratio(10000 * count * squares,
                                         weight_sum * weight_sum) if weight_sum else 0,
        "median_weight_uw": ladder[(count - 1) // 2] if count else 0,
        "maximum_weight_uw": ladder[-1] if count else 0,
        "minimum_weight_uw": ladder[0] if count else 0,
        "trimmed_count": len(full.clipped), "trimmed_units": full.clipped,
        "stratum_totals_uw": dict(sorted(pen_totals.items())),
        "stratum_ceilings_uw": dict(sorted(full.roofs.items()))})

    out["replicate_design.json"] = _dump_json({
        "replicate_count": len(replicas), "group_count": len(groups),
        "groups": {g: {"psus": groups[g], "size": len(groups[g]), "strata": inside[g]}
                   for g in sorted(groups)},
        "merged_groups": {g: inside[g] for g in sorted(inside)
                          if len(inside[g]) > 1 and g in groups}})

    out["replicate_summary.csv"] = _dump_rows(
        ["replicate_id", "group", "dropped_psu", "group_size", "iterations_used",
         "converged", "trimmed_count", "final_total_uw"],
        [[r["replicate_id"], r["group"], r["dropped_psu"], r["group_size"],
          r["iterations_used"], _yn(r["converged"]), r["trimmed_count"],
          r["final_total_uw"]]
         for r in sorted(replicas, key=lambda r: r["replicate_id"])], ",")

    head = ["cell_key", "row_level", "column_level", "point_estimate_uw",
            "unweighted_count", "standard_error_uw", "cv_bp", "dominance_bp"]
    for table in TABLES:
        out["estimates_%s.csv" % table] = _dump_rows(
            head, [[r["cell_key"], r["row_level"], r["column_level"],
                    r["point_estimate_uw"], r["unweighted_count"],
                    r["standard_error_uw"], r["cv_bp"], r["dominance_bp"]]
                   for r in tables[table]], ",")

    out["variance_components.json"] = _dump_json({
        "replicate_count": len(replicas),
        "tables": {t: {"summed_cell_variance_uw2": sum(spread[t].values()),
                       "by_group": dict(sorted(shares[t].items()))} for t in TABLES}})

    out["cv_screening.json"] = _dump_json({
        "min_publish_count": int(model.limits["min_publish_count"]),
        "max_publish_cv_bp": int(model.limits["max_publish_cv_bp"]),
        "dominance_bp": int(model.limits["dominance_bp"]),
        "tables": screening})

    out["primary_suppression.json"] = _dump_json({
        "tables": first, "counts": {t: len(first[t]) for t in TABLES},
        "total": sum(len(first[t]) for t in TABLES)})

    out["secondary_suppression.json"] = _dump_json({
        "tables": second, "cascade_rounds": spins,
        "counts": {t: len(second[t]) for t in TABLES},
        "total": sum(len(second[t]) for t in TABLES)})

    audit = []
    for table in TABLES:
        blocked = {r["cell_key"] for r in first[table]}
        follow = {r["cell_key"] for r in second[table]}
        for record in tables[table]:
            key = record["cell_key"]
            if key in blocked:
                status, why = "suppressed", "primary"
            elif key in follow:
                status, why = "suppressed", "secondary"
            else:
                status, why = "published", "none"
            audit.append([place[(table, key)], table, key, status, why,
                          record["point_estimate_uw"], record["unweighted_count"],
                          record["cv_bp"]])
    audit.sort(key=lambda r: (r[0], r[1], r[2]))
    out["disclosure_audit.tsv"] = _dump_rows(
        ["screening_rank", "table_name", "cell_key", "status", "reason",
         "point_estimate_uw", "unweighted_count", "cv_bp"], audit, "\t")

    drift = 0
    for dimension, levels in controls.items():
        for level, goal in levels.items():
            held = sum(final[n] for n in responding
                       if model.axis_keys[dimension][n] == level)
            drift = max(drift, abs(held - goal))

    board, leftover = {}, 0
    for table in TABLES:
        blocked = {r["cell_key"] for r in first[table]}
        follow = {r["cell_key"] for r in second[table]}
        total = shown = veiled = 0
        for record in tables[table]:
            total += record["point_estimate_uw"]
            if record["cell_key"] in blocked or record["cell_key"] in follow:
                veiled += record["point_estimate_uw"]
            else:
                shown += record["point_estimate_uw"]
        gap = total - shown - veiled
        leftover += abs(gap)
        board[table] = {"total_uw": total, "published_uw": shown,
                        "suppressed_uw": veiled, "residual_uw": gap,
                        "coverage_gap_uw": weight_sum - total}

    checks = [
        {"name": "raking_converged", "expected": 1,
         "observed": int(full.trace["converged"])},
        {"name": "final_total_within_tolerance", "expected": 1,
         "observed": int(abs(weight_sum - grand) <= model.tolerance)},
        {"name": "trimming_preserves_total", "expected": 1,
         "observed": int(sum(full.raked.values()) == weight_sum)},
        {"name": "suppression_conservation", "expected": 1,
         "observed": int(leftover == 0)},
    ]
    for check in checks:
        check["verdict"] = "pass" if check["observed"] == check["expected"] else "fail"

    out["closure_report.json"] = _dump_json({
        "post_trim_margin_deviation_uw": drift,
        "final_weight_total_uw": weight_sum, "control_grand_total_uw": grand,
        "conservation_residual_uw": leftover,
        "final_total_gap_uw": weight_sum - grand,
        "responding_count": len(responding), "replicate_count": len(replicas),
        "primary_suppression_total": sum(len(first[t]) for t in TABLES),
        "secondary_suppression_total": sum(len(second[t]) for t in TABLES),
        "tables": board, "checks": checks,
        "all_checks_pass": all(c["verdict"] == "pass" for c in checks)})

    return out


# ================================================= harness plumbing
import shutil

_cache: dict = {}
_cache_locks: dict = {}
_CACHE_GUARD = threading.Lock()

SPEC_HEADERS = {
    "design_weights.csv": "unit_id,stratum,psu_code,subsampled,design_weight_uw",
    "control_margins.tsv": "dimension\tlevel_key\tcontrol_total_uw\tchosen_rank\tchosen_source",
    "adjusted_weights.csv": "unit_id,cell_key,adjustment_factor_uw,adjusted_weight_uw",
    "final_weights.csv": "unit_id,stratum,raked_weight_uw,trimmed,final_weight_uw",
    "replicate_summary.csv": ("replicate_id,group,dropped_psu,group_size,iterations_used,"
                              "converged,trimmed_count,final_total_uw"),
    "disclosure_audit.tsv": ("screening_rank\ttable_name\tcell_key\tstatus\treason\t"
                             "point_estimate_uw\tunweighted_count\tcv_bp"),
}
for _table in TABLES:
    SPEC_HEADERS["estimates_%s.csv" % _table] = (
        "cell_key,row_level,column_level,point_estimate_uw,unweighted_count,"
        "standard_error_uw,cv_bp,dominance_bp")


def _cached(key, build):
    """Compute `build()` once per key, safely under concurrent checks."""
    with _CACHE_GUARD:
        lock = _cache_locks.setdefault(key, threading.Lock())
    with lock:
        if key not in _cache:
            try:
                _cache[key] = ("ok", build())
            except Exception as exc:  # recorded so every caller sees the same failure
                _cache[key] = ("error", exc)
    state, value = _cache[key]
    if state == "error":
        raise value
    return value


def _tests_are_root_owned() -> bool:
    try:
        status = Path("/tests").stat()
    except FileNotFoundError:
        return False
    return status.st_uid == 0 and (status.st_mode & 0o077) == 0


def _grant_read(argument: str) -> None:
    """Make an agent-written path readable before the uid drop.

    Agent editors write through a temp file in the same directory and rename it,
    so a program the agent wrote can land at mode 0600 (owner-only). The checks
    run that program as an unprivileged user, which then cannot open it, and a
    correct submission would score zero for a reason that has nothing to do with
    the task. The verifier runs as root, so widening the mode is always allowed
    here and it changes no graded content.
    """
    if not argument.startswith("/app"):
        return
    path = Path(argument)
    if not path.exists():
        return
    try:
        path.chmod(path.stat().st_mode | (0o555 if path.is_dir() else 0o444))
        for parent in path.parents:
            parent.chmod(parent.stat().st_mode | 0o555)
            if str(parent) == "/app":
                break
    except OSError:
        pass


def _as_untrusted(command):
    if os.name != "posix" and _tests_are_root_owned():
        raise RuntimeError("verifier isolation requires POSIX uid and gid dropping")
    if os.name == "posix" and os.geteuid() != 0 and _tests_are_root_owned():
        raise RuntimeError("verifier must run as root to isolate submitted code")
    if os.name == "posix" and os.geteuid() == 0:
        for argument in command:
            _grant_read(argument)
        return [*_SETPRIV, *command]
    return command


_LAUNCH_LOCK = threading.Lock()
_IN_FLIGHT = 0


def _reap(proc) -> None:
    """Kill everything the delivered program left behind, after any exit.

    The program runs in its own session as the dropped user, so its process
    group goes first. rewardkit runs checks concurrently, so the sweep over
    every remaining process of that user, which catches a child that called
    setsid() to leave the group, waits until no other check has a program
    running and therefore cannot kill a sibling check's live program.
    """
    global _IN_FLIGHT
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, AttributeError):
        pass
    with _LAUNCH_LOCK:
        _IN_FLIGHT -= 1
        if _IN_FLIGHT == 0 and os.name == "posix" and os.geteuid() == 0:
            try:
                subprocess.run(["pkill", "-KILL", "-u", "nobody"], check=False,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=10)
            except (OSError, subprocess.SubprocessError):
                pass


def _run_program(data_dir: Path, out_dir: Path, timeout: int = 120) -> None:
    """Run the delivered program once, as an unprivileged subprocess.

    The cap is 120 seconds because the tests invoke the program seven times
    across the suite (the shipped extract, three hidden extracts, and a repeat, a
    renamed and a shuffled copy of the challenge extract). Runs are serialised by
    a lock, so concurrent checks never make two runs share the CPU, and seven runs
    at the cap plus the derivations still sit inside the verifier timeout. The
    reference program takes well under the cap. The program sees a minimal
    environment, runs in its own session, and nothing it starts outlives the
    check that launched it.
    """
    with _RUN_LOCK:
        _launch(data_dir, out_dir, timeout)


_RUN_LOCK = threading.Lock()


def _launch(data_dir: Path, out_dir: Path, timeout: int) -> None:
    global _IN_FLIGHT
    out_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(out_dir, 0o777)
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(out_dir),
           "LC_ALL": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
    with _LAUNCH_LOCK:
        _IN_FLIGHT += 1
    try:
        proc = subprocess.Popen(
            _as_untrusted([sys.executable, str(PROGRAM), str(data_dir), str(out_dir)]),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, env=env, start_new_session=True)
    except Exception:
        with _LAUNCH_LOCK:
            _IN_FLIGHT -= 1
        raise
    try:
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                pass
            proc.wait()
            raise
    finally:
        _reap(proc)
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, proc.args)


CORPORA = {
    "shipped": (SAMPLE_SEED, SHIPPED_UNITS, 5, SHIPPED_SETTINGS, True),
    "challenge": (CHALLENGE_SEED, 420, 5, CHALLENGE_SETTINGS, False),
    "second": (SECOND_SEED, 560, 4, SECOND_SETTINGS, False),
    "third": (EVAL_SEED, 480, 5, THIRD_SETTINGS, False),
}

# Report groups graded on every hidden extract, one check per group.
GROUPS = {
    "frame": ("frame_audit.json", "design_weights.csv"),
    "benchmarks": ("control_totals.json", "control_margins.tsv"),
    "dispositions": ("response_status.json",),
    "adjustment": ("adjustment_cells.json", "adjusted_weights.csv", "raking_trace.json"),
    "trimming": ("final_weights.csv", "weight_diagnostics.json"),
    "estimates": ("replicate_design.json", "replicate_summary.csv", "variance_components.json",
                  "estimates_activity_by_region.csv", "estimates_tenure_by_wquintile.csv",
                  "estimates_hours_by_sector.csv", "estimates_band_transition.csv"),
    "disclosure": ("cv_screening.json", "primary_suppression.json",
                   "secondary_suppression.json", "disclosure_audit.tsv",
                   "closure_report.json"),
}


def _corpus(name):
    """An extract built inside the verifier, with its expected bytes."""
    def build():
        seed, units, areas, settings, bulk = CORPORA[name]
        holder = Path(tempfile.mkdtemp(prefix="has7%s" % name))
        os.chmod(holder, 0o777)
        root = build_case(holder / "data", seed, units, bulk=bulk, n_areas=areas,
                          settings=settings)
        return holder, root, expected(root)
    return _cached(("corpus", name), build)


def _variant(name, how):
    """A private copy of an extract, renamed or row-shuffled."""
    holder, root, _ = _corpus(name)
    # The shuffled copy keeps the original directory name, so a program keyed on
    # the name cannot fire this check as well as the renaming one.
    target = holder / "renamed_extract" if how == "renamed" else holder / "shuffled" / root.name
    if not target.exists():
        shutil.copytree(root, target)
        if how == "shuffled":
            sheet = target / "frame__register-a.csv"
            rows = sheet.read_text(encoding="utf-8").splitlines()
            head, body = rows[0], rows[1:]
            stride = Stream(SHUFFLE_SEED)
            for index in range(len(body) - 1, 0, -1):
                swap = stride.step() % (index + 1)
                body[index], body[swap] = body[swap], body[index]
            sheet.write_text("\n".join([head] + body) + "\n", encoding="utf-8", newline="\n")
    return target


def _outputs(name, run="main"):
    """Run the delivered program once on an extract; map artifact -> text or None."""
    def build():
        holder, root, _ = _corpus(name)
        source = root if run in ("main", "repeat") else _variant(name, run)
        target = holder / ("out_" + run)
        _run_program(source, target)
        found = {}
        for artifact in ARTIFACTS:
            path = target / artifact
            try:
                found[artifact] = path.read_text(encoding="utf-8") if path.is_file() else None
            except (OSError, UnicodeDecodeError):
                found[artifact] = None
        found["extra"] = sorted(p.name for p in target.iterdir()
                                if p.name not in set(ARTIFACTS))
        return found
    return _cached(("run", name, run), build)


def _holds(fn):
    try:
        return bool(fn())
    except Exception:
        return False


def _delivered(name):
    return (OUT / name).read_text(encoding="utf-8")


def _shipped_group(*names):
    """The delivered reports and the program's own run on the shipped extract both
    equal the bytes the standard gives, so the reports are the program's work."""
    wanted = _corpus("shipped")[2]
    got = _outputs("shipped")
    return all((OUT / n).is_file() and _delivered(n) == wanted[n] and got[n] == wanted[n]
               for n in names)


def _group_on(corpus, group):
    got = _outputs(corpus)
    wanted = _corpus(corpus)[2]
    return all(got[n] is not None and got[n] == wanted[n] for n in GROUPS[group])


def _well_formed(name, text):
    if text.startswith("\ufeff") or "\r" in text or not text.endswith("\n") or text.endswith("\n\n"):
        return False
    if name.endswith(".json"):
        return text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"
    return text.split("\n", 1)[0] == SPEC_HEADERS[name] and '"' not in text


# ----------------------------------------------------------- presence and format
@criterion(description="Every declared artifact exists under /app/out and every JSON report parses.")
def artifact_set_exists_and_parses(workspace) -> bool:
    try:
        if not PROGRAM.is_file():
            return False
        for name in ARTIFACTS:
            if not (OUT / name).is_file():
                return False
            if name.endswith(".json"):
                json.loads(_delivered(name))
        return True
    except Exception:
        return False


@criterion(description="Every report under /app/out follows the standard serialization: UTF-8 without a byte order mark, one trailing newline, JSON with sorted keys and a two space indent, and delimited files under the exact header with no quoting.")
def report_serialization_format(workspace) -> bool:
    return _holds(lambda: all(_well_formed(n, _delivered(n)) for n in ARTIFACTS))


@criterion(description="Run on an unseen extract, the delivered program writes all twenty-two reports and every JSON report parses.")
def unseen_run_writes_complete_report_set(workspace) -> bool:
    try:
        got = _outputs("challenge")
        for name in ARTIFACTS:
            if got[name] is None:
                return False
            if name.endswith(".json"):
                json.loads(got[name])
        return True
    except Exception:
        return False


# ----------------------------------------------------------- shipped extract
@criterion(description="On the shipped extract the delivered program writes, and /app/out holds, the frame, benchmark, disposition and design weight reports the standard gives.")
def shipped_frame_to_design_reports(workspace) -> bool:
    return _holds(lambda: _shipped_group("frame_audit.json", "control_totals.json",
                                         "control_margins.tsv", "response_status.json",
                                         "design_weights.csv"))


@criterion(description="On the shipped extract the delivered program writes, and /app/out holds, the adjustment, raking and trimming reports the standard gives.")
def shipped_weighting_reports(workspace) -> bool:
    return _holds(lambda: _shipped_group("adjustment_cells.json", "adjusted_weights.csv",
                                         "raking_trace.json", "final_weights.csv",
                                         "weight_diagnostics.json"))


@criterion(description="On the shipped extract the delivered program writes, and /app/out holds, the replication reports and the four estimate tables the standard gives.")
def shipped_replication_and_estimates(workspace) -> bool:
    return _holds(lambda: _shipped_group(*GROUPS["estimates"]))


@criterion(description="On the shipped extract the delivered program writes, and /app/out holds, the screening, suppression, audit and closure reports the standard gives.")
def shipped_disclosure_reports(workspace) -> bool:
    return _holds(lambda: _shipped_group(*GROUPS["disclosure"]))


# ----------------------------------------------------------- hidden extracts
# Three extracts the program has never seen, each with its own settings and its
# own trap mix: the challenge extract has no decomposed names, a binding collapse
# cap and a binding cascade cap; the second has four regions, no repeated clock
# hour and a raking limit the round runs out of; the third has neither
# decomposed names nor a repeated clock hour.
@criterion(description="On the challenge extract the program writes frame_audit.json and design_weights.csv as the standard gives them.")
def challenge_frame(workspace) -> bool:
    return _holds(lambda: _group_on("challenge", "frame"))


@criterion(description="On the challenge extract the program writes control_totals.json and control_margins.tsv as the standard gives them.")
def challenge_benchmarks(workspace) -> bool:
    return _holds(lambda: _group_on("challenge", "benchmarks"))


@criterion(description="On the challenge extract the program writes response_status.json as the standard gives it.")
def challenge_dispositions(workspace) -> bool:
    return _holds(lambda: _group_on("challenge", "dispositions"))


@criterion(description="On the challenge extract the program writes the adjustment and raking reports as the standard gives them.")
def challenge_adjustment(workspace) -> bool:
    return _holds(lambda: _group_on("challenge", "adjustment"))


@criterion(description="On the challenge extract the program writes final_weights.csv and weight_diagnostics.json as the standard gives them.")
def challenge_trimming(workspace) -> bool:
    return _holds(lambda: _group_on("challenge", "trimming"))


@criterion(description="On the challenge extract the program writes the replication reports and the four estimate tables as the standard gives them.")
def challenge_estimates(workspace) -> bool:
    return _holds(lambda: _group_on("challenge", "estimates"))


@criterion(description="On the challenge extract the program writes the screening, suppression, audit and closure reports as the standard gives them.")
def challenge_disclosure(workspace) -> bool:
    return _holds(lambda: _group_on("challenge", "disclosure"))


@criterion(description="On the second extract the program writes frame_audit.json and design_weights.csv as the standard gives them.")
def second_frame(workspace) -> bool:
    return _holds(lambda: _group_on("second", "frame"))


@criterion(description="On the second extract the program writes control_totals.json and control_margins.tsv as the standard gives them.")
def second_benchmarks(workspace) -> bool:
    return _holds(lambda: _group_on("second", "benchmarks"))


@criterion(description="On the second extract the program writes response_status.json as the standard gives it.")
def second_dispositions(workspace) -> bool:
    return _holds(lambda: _group_on("second", "dispositions"))


@criterion(description="On the second extract the program writes the adjustment and raking reports as the standard gives them.")
def second_adjustment(workspace) -> bool:
    return _holds(lambda: _group_on("second", "adjustment"))


@criterion(description="On the second extract the program writes final_weights.csv and weight_diagnostics.json as the standard gives them.")
def second_trimming(workspace) -> bool:
    return _holds(lambda: _group_on("second", "trimming"))


@criterion(description="On the second extract the program writes the replication reports and the four estimate tables as the standard gives them.")
def second_estimates(workspace) -> bool:
    return _holds(lambda: _group_on("second", "estimates"))


@criterion(description="On the second extract the program writes the screening, suppression, audit and closure reports as the standard gives them.")
def second_disclosure(workspace) -> bool:
    return _holds(lambda: _group_on("second", "disclosure"))


@criterion(description="On the third extract the program writes frame_audit.json and design_weights.csv as the standard gives them.")
def third_frame(workspace) -> bool:
    return _holds(lambda: _group_on("third", "frame"))


@criterion(description="On the third extract the program writes control_totals.json and control_margins.tsv as the standard gives them.")
def third_benchmarks(workspace) -> bool:
    return _holds(lambda: _group_on("third", "benchmarks"))


@criterion(description="On the third extract the program writes response_status.json as the standard gives it.")
def third_dispositions(workspace) -> bool:
    return _holds(lambda: _group_on("third", "dispositions"))


@criterion(description="On the third extract the program writes the adjustment and raking reports as the standard gives them.")
def third_adjustment(workspace) -> bool:
    return _holds(lambda: _group_on("third", "adjustment"))


@criterion(description="On the third extract the program writes final_weights.csv and weight_diagnostics.json as the standard gives them.")
def third_trimming(workspace) -> bool:
    return _holds(lambda: _group_on("third", "trimming"))


@criterion(description="On the third extract the program writes the replication reports and the four estimate tables as the standard gives them.")
def third_estimates(workspace) -> bool:
    return _holds(lambda: _group_on("third", "estimates"))


@criterion(description="On the third extract the program writes the screening, suppression, audit and closure reports as the standard gives them.")
def third_disclosure(workspace) -> bool:
    return _holds(lambda: _group_on("third", "disclosure"))


# ----------------------------------------------------------- negative checks
def _hardcoded():
    got = _outputs("challenge")
    wanted = _corpus("shipped")[2]
    return sum(1 for n in ARTIFACTS if got[n] is not None and got[n] == wanted[n]) >= 11


def _steady():
    first, again = _outputs("challenge"), _outputs("challenge", "repeat")
    return all(first[n] == again[n] for n in ARTIFACTS)


def _moved(run):
    first, other = _outputs("challenge"), _outputs("challenge", run)
    return any(first[n] is not None and other[n] is not None and first[n] != other[n]
               for n in ARTIFACTS)


@criterion(description="NEGATIVE: on an unseen extract the program writes at least half of the shipped extract's reports byte for byte.")
def negative_hardcoded_sample_answers(workspace) -> bool:
    # Inverted: returns True only when the hardcoding signature is present.
    return _holds(_hardcoded)


@criterion(description="NEGATIVE: two runs of the program over one unseen extract write different bytes.")
def negative_nondeterministic_output(workspace) -> bool:
    # Inverted: returns True only when repeat runs disagree.
    return _holds(lambda: not _steady())


@criterion(description="NEGATIVE: the same extract under another directory name gives different output while repeat runs agree.")
def negative_filename_dependent_behaviour(workspace) -> bool:
    # Inverted: returns True only when output follows the directory name.
    return _holds(lambda: _steady() and _moved("renamed"))


@criterion(description="NEGATIVE: reordering the rows of one frame register changes the output while repeat runs agree.")
def negative_input_row_order_dependence(workspace) -> bool:
    # Inverted: returns True only when output follows row order.
    return _holds(lambda: _steady() and not _moved("renamed") and _moved("shuffled"))


@criterion(description="NEGATIVE: on an unseen extract whose pilot implies another margin order the program rakes in the shipped round's order.")
def negative_reuses_shipped_margin_order(workspace) -> bool:
    # Inverted: returns True only when the shipped order is reused; the hardcoding
    # check owns a program that replays the shipped reports wholesale.
    try:
        text = _outputs("challenge")["raking_trace.json"]
        if text is None or _hardcoded():
            return False
        return json.loads(text).get("margin_order") == list(SHIPPED_SETTINGS["order"])
    except Exception:
        return False


@criterion(description="NEGATIVE: run on an unseen extract the program leaves files beside the twenty-two reports in its output directory.")
def negative_writes_outside_declared_artifacts(workspace) -> bool:
    # Inverted: returns True only when stray files are written.
    return _holds(lambda: bool(_outputs("challenge")["extra"]))


@criterion(description="NEGATIVE: the delivered program imports a module outside the Python standard library.")
def negative_uses_a_third_party_library(workspace) -> bool:
    # Inverted: returns True only when a non standard library import is found.
    try:
        import ast
        outside = set()
        for path in sorted(OUT.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = {a.name.split(".")[0] for a in node.names}
                elif isinstance(node, ast.ImportFrom) and not node.level:
                    names = {(node.module or "").split(".")[0]}
                else:
                    continue
                outside |= {n for n in names if n and n not in sys.stdlib_module_names}
        return bool(outside)
    except Exception:
        return False


def _write_corpus(root: Path) -> None:
    build_case(root / "data", SAMPLE_SEED, SHIPPED_UNITS, bulk=True)


if __name__ == "__main__":
    _write_corpus(Path(sys.argv[1]))


criteria.artifact_set_exists_and_parses(weight=1)
criteria.report_serialization_format(weight=1)
criteria.unseen_run_writes_complete_report_set(weight=1)
criteria.shipped_frame_to_design_reports(weight=5)
criteria.shipped_weighting_reports(weight=5)
criteria.shipped_replication_and_estimates(weight=5)
criteria.shipped_disclosure_reports(weight=5)
criteria.challenge_frame(weight=5)
criteria.challenge_benchmarks(weight=5)
criteria.challenge_dispositions(weight=5)
criteria.challenge_adjustment(weight=5)
criteria.challenge_trimming(weight=5)
criteria.challenge_estimates(weight=5)
criteria.challenge_disclosure(weight=5)
criteria.second_frame(weight=5)
criteria.second_benchmarks(weight=5)
criteria.second_dispositions(weight=5)
criteria.second_adjustment(weight=5)
criteria.second_trimming(weight=5)
criteria.second_estimates(weight=5)
criteria.second_disclosure(weight=5)
criteria.third_frame(weight=5)
criteria.third_benchmarks(weight=5)
criteria.third_dispositions(weight=5)
criteria.third_adjustment(weight=5)
criteria.third_trimming(weight=5)
criteria.third_estimates(weight=5)
criteria.third_disclosure(weight=5)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_filename_dependent_behaviour(weight=-3)
criteria.negative_input_row_order_dependence(weight=-3)
criteria.negative_reuses_shipped_margin_order(weight=-5)
criteria.negative_writes_outside_declared_artifacts(weight=-3)
criteria.negative_uses_a_third_party_library(weight=-3)

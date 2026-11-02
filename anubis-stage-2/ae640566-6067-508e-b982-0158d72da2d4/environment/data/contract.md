# Helios gravimeter array derivation contract

The material beside this contract is authoritative. It defines every rule, but it
does not publish a derivation procedure. The worked calibration evidence establishes
rule composition, rounding and the report encoding.

All metrology figures are exact integer nanounits. A quantity may
be negative, and a negative quantity is a real observation rather than an error.
Integer figures in this archive are not constrained to the range that binary floating
point represents exactly, so arithmetic that passes through a 64-bit float can lose a
unit. A raw count may run to dozens of digits, wider than default precision decimal
arithmetic carries as well, so only exact integer arithmetic keeps every unit through
unit conversion, gain, ladder correction and rounding. Epochs are ISO-8601 local
instants and compare as instants, never as text: the
date and the time of day may be separated by `T` or by a single space, and any numeric
component may omit its leading zeros, so `2031-3-5 8:04:00` and `2031-03-05T08:04:00`
name the same instant. An empty interval end is open ended. An empty override is
absent; zero is supplied. Identifier ordering is case-sensitive Unicode code-point
order. The flags `provisional` and `standing_basis` read `true` or `false` in any
letter case; a blank `standing_basis` is true and a blank `provisional` is false.

Tabular material is comma-separated text in the usual quoted dialect: a field that
contains a comma is wrapped in double quotes, a wholly blank line carries no record,
and whitespace surrounding a field is insignificant. Splitting a line on every comma
is therefore not a faithful read of this archive.

## Reference meanings

The network policy supplies report identity, canonical unit, parameter defaults, the
sample-value floor and uncertainty budget. Reporting thresholds supply report rosters,
alert gates, area floor bands and the custody secondary band. Units map normalised
tokens to factors, and each normalised token appears on at most one row. A factor is
a positive integer or a ratio `numerator/denominator` of two positive integers, with
insignificant whitespace around either part and no requirement that the ratio be in
lowest terms. Anything else, including a zero numerator or a zero denominator, supplies
no factor, so the unit resolves to nothing. The channel registry owns canonical
channels, provisional status and each channel's reporting area. Aliases map normalised
historical labels to
channels. Stations belong to area reports and may supply parameter overrides.
Deployments and station custody are effective-dated. Agencies supply operator classes.
Certificates are effective-dated channel calibrations. Standards form traceability
parent links. Observations carry lifecycle state and say whether they are a
`standing_basis`. Amendments revise lifecycle or fields, may revoke or restore certificates,
and may revise traceability standards.

Rows in the custody material with an `array_channel_id` are standing-custody links:
the named channel is held by `custodian_channel_id`. Other custody rows connect a
station to its operator. A channel has at most one standing custodian, and standing
custody has no cycle.

## Record rules

Each non-blank ledger line holds one JSON object. A line that is not a JSON object,
or whose `entry_id` is not a non-empty string, or whose `sequence` is not a JSON
integer (a number written without fraction or exponent; `true`, `false` and quoted
digits are not integers), is malformed: it counts as unmatched, it is never posted,
and it claims no `entry_id`. Each well-formed amendment carries a `sequence`. Ledger
order is ascending
`sequence`, and a tied `sequence` is ordered by ascending `entry_id` under the identifier
ordering above, character by character, with no numeric or case-insensitive reading; the
order the lines happen to appear in the file carries no meaning. An `entry_id` that appears more
than once is posted once, on its first appearance in ledger order, and every later
appearance is ignored.

`revise` overwrites the named sample fields (`channel_token`, `epoch`, `raw_count`,
`unit_token` and `standing_basis`, the last written as a JSON boolean) unless the
sample is void. `void` changes a
non-void sample to void. `reinstate` changes a void sample to observed. `certify`
changes a suspect sample to observed. `revoke_certificate` makes an existing
certificate unavailable at every epoch, and revoking an already revoked certificate is
ignored. `restore_certificate` makes a revoked certificate available again at every
epoch; restoring a certificate that is not revoked at that point of the ledger is
ignored, and a restored certificate may be revoked again later. `revise_standard`
names a `standard_id` and overwrites that standard's `parent_standard_id` (a JSON
string; an empty string makes the standard a parentless primary), its `ratio_ppm` (a
JSON integer), or both. One that names no standard in the standards table is
unmatched; one that carries neither field, or carries either field with a value of any
other JSON type, is ignored and changes nothing. Certificate availability and every
standard's parent and ratio are the state left after the whole ledger, and every
ladder is walked over those final standards, so a revision can close a loop, open
one, or move a certificate onto another path. Missing targets and unknown operations
are unmatched; failed state preconditions are ignored.

A `sample_id` that appears on more than one observation row is carried by its first
row alone. Every later row with that identifier is a `duplicate_sample`: it is held
before any other rule is considered, it is never an amendment target, and it never
qualifies a channel. Duplicate rows are still observations and still count once each
toward the observed total.

A sample is `malformed_sample` when, after amendment effects, its `raw_count` is not a
whole number or its `epoch` is not a readable instant. A whole number is an optional `+`
or `-` followed by one or more ASCII digits `0`-`9`; separators, underscores, fractions,
exponents, other numeral systems and blank values are not whole numbers. A readable
instant is a year, month and day joined by `-`, then `T` or a single space, then hours,
minutes and seconds joined by `:`, every component being one or more ASCII digits.
Whitespace surrounding either field is insignificant. A `revise` writes the value it
carries: a `raw_count` that is not a JSON integer, or an `epoch` that is not a JSON
string naming a readable instant, leaves the sample malformed, and a later well formed
revision of the same field repairs it. Void samples are still voided and suspect samples
still held as `unresolved_suspect` whatever their fields hold. For an observed sample,
`malformed_sample` is decided before every rule in the list below, and a malformed
sample never qualifies a channel. Only observation values can be malformed; every other
table in this archive is well formed.

After amendment effects, void samples are voided and suspect samples are quarantined
as `unresolved_suspect`. An observed sample may instead be quarantined for any of:

- `unknown_channel`: its label resolves to no owned channel;
- `unknown_unit`: its unit resolves to no factor;
- `no_deployment`: no covering deployment exists, or it names no station;
- `no_custody`: no covering station-custody row exists, or it names no agency;
- `no_certificate`: no effective, unrevoked channel certificate exists;
- `broken_ladder`: the selected standard cannot reach a parentless primary, including
  when its parent chain returns to a standard it has already visited;
- `unreported_array`: the sample is not a standing basis and its channel has not
  earned reporting standing.

The first applicable outcome is demonstrated by the calibration control. Quarantined
samples contribute only to lifecycle and reason counts.

Labels are upper-cased and stripped to letters and digits. Aliases are compared in
that form. A structural label `HLS` plus digits denotes `HLS-` plus four padded digits.
Unit tokens are lower-cased and stripped to letters and digits. The calibration
boundary records determine how competing identity rules compose.

A covering interval includes both endpoints. A certificate covers the instants from its
`valid_from` through its `valid_to`; an empty `valid_to` is open ended, and an expired
certificate is not effective. Among overlapping deployments, the
later start wins and a tied start uses the lower identifier. Station custody follows
the same rule. Among effective unrevoked certificates, the later start wins and a
tied start uses the higher certificate identifier.

Gain, offset and drift each take one supplied value. Ordinary channels use certificate,
station and network sources; provisional channels exchange the first two sources.
The calibration evidence, not this paragraph's presentation order, fixes composition.

A certificate's ladder correction is the sum of ratios on its path toward the
parentless primary, excluding the primary's own value. Samples sharing channel and
certificate have drift positions ordered by epoch then sample identifier, beginning
at zero. Only accepted samples occupy positions: a record quarantined by any rule,
including the standing rule (`unreported_array`), holds no position and does not
shift the positions of the samples after it. Parameter-source counts likewise count
accepted samples only.

Canonical quantity is raw count times unit factor, rounded to an integer nanounit when
the factor is a ratio, and every later step starts from that integer. Gain and ladder correction each
produce a rounded integer nanounit, gain first: the canonical figure times the gain in
micro-units divided by one million is rounded, and that rounded figure times one
million plus the ladder correction in parts per million, divided by one million, is
rounded again. That second figure is the traced quantity. The drift quantity is the
drift position times the drift rate; it is subtracted from the traced quantity and the
offset is added. The final sample figure is no lower than the policy sample-value
floor, which applies to negative figures exactly as it applies to positive ones. Exact
half cases in the calibration evidence, on both sides of zero, determine the single
rounding convention used everywhere a ratio becomes an integer.

## Earned reporting standing

Only `standing_basis=true` observations that survive every non-standing rule are
qualifying observations. Counts are non-negative counts; sample sign and magnitude do
not reduce them. Conditional observations never count toward standing.

For an area, the applicable reporting floor is the band with the greatest
`reporting_arrays_at_least` not exceeding the number of reporting channels in that
area. A channel is added to reporting standing when its qualifying count reaches its
area's applicable floor. It is also added when its standing custodian is reporting and
its own qualifying count reaches the custody secondary band. Once added, standing is
retained.

The reporting set is the least set consistent with those statements. Standing must be
earned: a channel may not rely on an observation admitted by its own reporting status
to reach the count granting that status, directly or through any custody chain. This
is a monotone closure because only qualifying observations are counted and admitting
more channels cannot remove a count or standing already earned.

A non-basis observation of a non-reporting channel is `unreported_array`, even when
its certificate was selected only by falling back after a retroactive revocation.
The selected fallback certificate remains visible in the standing-exclusion audit.

Reporting standing is settled in rounds. Round 1 tests every channel against the
statements above with nothing yet reporting; each later round tests the channels still
outside the set against the set as it stood at the end of the previous round, and every
channel that qualifies in a round joins together at the end of that round. A channel's
reporting round is the number of the round in which it joined. Rounds stop when one
adds no channel.

## Aggregates

Accepted samples aggregate by station area and operator class. Every roster area and
class receives a report, including empty ones. Samples in an unrostered area still
contribute to their class and network totals.

The uncertainty budget is apportioned separately over roster areas and roster classes,
weighted by accepted counts. Integer shares use largest remainders; equal remainders
use ascending bucket names. A zero population receives zero shares. A nonzero
apportionment sums exactly to the budget, to the unit, however large the budget is.

An area or class alert exists when the magnitude of reported minus canonical total is
at least its alert gate. Each alert is an object carrying the bucket name under `name`
and the signed reported minus canonical difference under `delta_nano`; an area or class
report lists its own alert, if any. The network alert list holds the area alerts only,
in area-name order. Largest sample
uses greatest reported value then lower sample identifier. When no sample is accepted the
largest sample carries a zero value and a null identifier, and an archive holding no
observation has a zero quarantine ratio.

The policy audit identifies applied, revoked and unused certificates, ladder values,
parameter-source counts, provisional channels, thresholds, the reporting and
non-reporting channel sets, each reporting round, qualifying counts, area reporting
counts (one entry for every area named in the channel registry, including areas outside
the report roster) and certificates selected for standing-excluded records, the last
as an object mapping each standing-excluded sample identifier to the certificate
identifier selected for it. The data-quality
report accounts for every observation, quarantine reasons, amendment anomalies,
orphan aliases (the alias cells as written in the alias table, trimmed of surrounding
spaces but not upper-cased, whose channel is absent from the registry, in ascending
order), unrostered-area accepted counts and the rounded quarantine ratio, and its
input file count is the number of files present in the archive directory, whether or not
the derivation reads them.

The example outputs built from the calibration slice are the authority for object fields,
list ordering, indentation, key ordering and terminal newline. The
`calibration_example.json` file holds one worked report per output artifact, keyed by its
file name (`summary.json`, `policy_audit.json`, `data_quality.json`, each `region_*.json`
and each `segment_*.json`), so the exact field names and nesting of every report can be
read off it.

Field names keep the archive's own vocabulary. In the summary and data-quality reports
an `array` is a station area (`array_counts`, `array_totals`,
`array_allocation_nano`, `unreported_array_counts`); in the policy audit the
`*_arrays` and `*_by_array` fields are keyed by channel identifier.

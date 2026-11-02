# Record layouts

The eight layouts this extract is written in, and the fields each one carries.

## 1. Layouts

A `.csv` file is comma separated with a header line. A `.tsv` file is tab
separated with a header line. A `.psv` file is pipe separated with a header
line. In all three, a data line whose field count differs from the header is
`MALFORMED_ROW`, and no field is ever quoted.

A `.jsonl` file carries one JSON object per line. A line that is not a JSON
object is `MALFORMED_ROW`.

A `.kv` file carries records separated by one blank line. Inside a record each
line is a field name, a colon, a space, and the value, and a field with an empty
value ends at the colon. A record carrying a line in any other shape is
`MALFORMED_ROW`.

A `.rec` file carries one record per line, as `name=value` pairs joined by
semicolons. A line carrying a segment with no equals sign is `MALFORMED_ROW`.

An `.xml` file carries one element per line inside a single wrapping element.
Every field is an attribute of that element, and the five XML entities are
written in their escaped form.

A `.fixed` file carries one record per line in fixed width columns with no
header and no separator. Trailing spaces at the end of a line are dropped, so a
line may be shorter than the full width, and the missing columns are empty.
Every value is left aligned inside its column and padded with spaces.

## 2. Commitment assertion rows

Files named `commitments_*` carry commitment assertions with these fields:

```
assertion_id      the identifier of this row
commitment_key    the commitment the row asserts
obligor           the principal who owes the commitment
obligee           the principal it is owed to
project_ref       the project reference, resolved as the protocol states
due_at            the instant the commitment falls due
effort            the effort figure, read as the protocol states
effort_unit       minutes, hours or halfdays
cadence_ref       the standing obligation this discharges, or empty
observed_at       the instant this row was recorded
```

**The `.fixed` and `.rec` commitment layouts carry no `effort_unit` field. In
both of those two layouts the `effort` figure is a count of hours.** Every other
commitment layout carries `effort_unit` and takes its factor from that field,
and the value written there is compared exactly as it stands.

The fixed width columns for a commitment assertion, in order, are:

```
assertion_id     12
commitment_key   12
obligor          40
obligee          40
project_ref      10
due_at           18
effort            8
cadence_ref      10
observed_at      18
```

## 3. State assertion rows

Files named `states_*` carry state assertions with these fields:

```
state_id          the identifier of this row
commitment_key    the commitment whose state is asserted
to_state          the state asserted
observed_at       the instant this row was recorded
```

The fixed width columns for a state assertion, in order, are:

```
state_id         12
commitment_key   12
to_state         12
observed_at      18
```

## 4. Edge rows

Files named `edges_*` carry dependency edges with these fields:

```
edge_id           the identifier of this row
dependent_key     the commitment that waits
blocker_key       the commitment it waits on
asserted_at       the instant this claim was made
```

## 5. Alias rows

Files named `aliases_*` carry alias assertions with these fields:

```
surface           the reference the assertion is about
target            what the reference stands for
scope_start       the first instant the assertion holds
scope_end         the first instant after it stops holding
asserted_at       the instant the assertion was recorded
```

## 6. Roster rows

Files named `roster_*` carry roster lines with `actor_id`, `canonical_handle`,
`line_from` and `line_to`. One principal holds several lines, and the lines for
one principal may spell its handle in more than one way. Every spelling folds to
the same string and every line names the same principal.

The canonical handle of a principal is the spelling that appears on the greatest
number of its roster lines across all three files, and a tie between two
spellings is settled in favour of the one that sorts earlier.

## 7. Reference tables

```
project_registry.csv   project_code, revision, display_name, parent_code,
                       default_effort, revised_at
project_events.tsv     event_id, project_code, event_type, payload,
                       effective_at
cadence_register.csv   cadence_id, revision, obligor, project_ref, period_days,
                       anchor_at, revised_at
waivers_desk.csv       waiver_id, cadence_id, period_index, reason, asserted_at
waivers_partner.psv    the same fields as waivers_desk.csv
attention_budget.csv   actor_id, year_month, monthly_minutes
budget_overrides.psv   actor_id, year_month, monthly_minutes
feed_manifest.csv      feed_file, source_class, revision, retired_at,
                       declared_at
```

In `project_events.tsv` the only event type any rule reads is `RENAME`, whose
`payload` is the code the project becomes. Every other event type is a record of
the project's history and governs nothing.

In `feed_manifest.csv` a feed file appears once per revision, and the row that
governs is the one carrying the greatest `revision`. An empty `retired_at` on
that row means the feed was never retired, whatever a superseded revision of the
same file carries.

In `project_registry.csv` a project appears once per revision. The revision that
governs a lookup is the one with the greatest `revised_at` at or before the
resolving instant, and the parent of a project is the one its latest revision
carries. A code the registry declares that no assertion ever names is part of
the register and reaches no figure.

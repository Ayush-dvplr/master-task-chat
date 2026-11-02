# Relay governance

## What a cycle covers

A cycle adjudicates promotion requests whose `submitted_at` falls inside the half
open horizon named in `horizon_config.json`. The field the horizon applies to is
named in that same file. A request whose stamp sits outside the horizon belongs to
another cycle and appears nowhere in this cycle's output, however recently it was
recorded.

## The governing record

Several tables keep history in two time axes. `effective_at` is when a statement
started to describe the world. `recorded_at` is when the relay learned it. For a
given key the governing record is chosen like this.

1. Discard rows whose `effective_at` is later than the decision instant.
2. Among what remains take the row with the greatest `recorded_at`.
3. If two rows share that `recorded_at`, take the one with the greater row
   identifier. Row identifiers are fixed width and are issued in filing order.

There is no filter on `recorded_at`. A statement filed yesterday about a change
that took effect in July governs over a statement filed in July about a change
that took effect last week. The tables that work this way are marked bi-temporal
in the data index.

A promotion request is not bi-temporal in that sense. Requests arrive more than
once and the relay keeps every copy. For one `request_id` the copy that counts is
the one with the greatest `recorded_at`; where several copies share it, the one
with the greatest `priority_hint`; where several still remain, the one that appears
last in the file. Copies that do not win count nowhere, including in any total.

## Deciding one request

Each request that survives the horizon and the duplicate rule is tested against a
fixed set of conditions. Every condition carries a reason code and every reason
code carries exactly one of three decisions: `admitted`, `deferred` or `rejected`.
When more than one condition holds for the same request, the code reported is the
one whose `order` in `reason_code_registry.json` is lowest. The code `ok` is the
only code that carries `admitted`.

The conditions are these.

* The content reference does not resolve to a unit. Code `alias_unresolved`.
* The target channel is not adjacent to the unit's current seating. Code
  `channel_not_adjacent`.
* The target channel already seats the unit at the requested revision or better.
  Code `revision_regression`.
* The requested revision stands withdrawn. Code `withdrawn_revision`.
* A quarantine floor covers the unit's family and the target channel and the
  requested revision falls below that floor. Code `quarantine_floor`.
* An embargo holds the revision past the end of the horizon. Code `embargo_active`.
* An embargo releases the revision after the decision instant but before the end
  of the horizon. Code `embargo_pending`.
* Integrity authority does not clear the revision. Code `attestation_failed`.
* The channel does not admit the unit's risk tier. Code `risk_tier_blocked`.
* The channel is still inside its reseal cooldown. Code `channel_cooldown`.
* A freeze window covers the decision instant at the submitting site. Code
  `freeze_window`.
* A recurring hold covers the decision instant at the submitting site. Code
  `recurring_hold`.
* A requirement of the revision is not met. Code `missing_dependency`.
* Two requests in this cycle require each other. Code `cycle_unresolved`.
* The channel has no capacity left. Code `budget_exhausted`.
* The request has been carried too long. Code `carry_forward_exhausted`.

## Quarantine and bulletins

A quarantine floor is set by `quarantine_directives.json`. The governing directive
for a family and channel must carry status `active`. A directive whose
`scope_channel` is `any` covers every channel. Bulletins in
`release_bulletins.json` adjust which risk tiers a channel admits and nothing
else. A bulletin counts when it is the governing record for its channel, family
and risk tier and its `status` is `active`. A bulletin whose action claims to lift
a quarantine changes no decision and never competes with one that allows a tier.

## Risk tiers

Three layers decide whether a channel admits a unit's risk tier. The baseline is
`risk_tier_table.json`. A denial in `site_overrides.json` for the submitting site
and the target channel removes a tier. A governing bulletin whose action allows a
risk tier for that channel and that family restores it. The bulletin layer is read
last and wins over the other two.

## Escalation

`carry_forward_policy.json` names a carry count. When the `as_of_cycle` row of
`carry_forward_state.csv` for the unit and target channel of this cycle reaches
that count and the reset flag does not carry the cleared value, a deferred outcome
is reported under the escalated reason code instead of the code the condition
would otherwise carry. The excluded code named in that policy never escalates, and
a rejected outcome never escalates. An escalated request is listed with the code
the condition carried before the rewrite.

## Risk tier and owning site

The governing row of `unit_catalog.csv` supplies a unit's risk tier and owning
site. The `declared_family` field of a request is what a submitter typed and
carries no authority.

## Normative parameters

```
duplicate_rank_fields: recorded_at,priority_hint,file_order
request_priority_field: priority_hint
decision_values: admitted,deferred,rejected
```

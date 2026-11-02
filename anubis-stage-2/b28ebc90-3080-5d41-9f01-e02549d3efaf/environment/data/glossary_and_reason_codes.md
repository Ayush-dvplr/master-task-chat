# Glossary and closed vocabularies

## Reason codes set at intake

- `UNCONVERTIBLE_UNIT`
- `OUT_OF_DAY`
- `IMPLAUSIBLE_DEMAND`
- `RETIRED_ROUTINE`
- `UNRESOLVED_ACTION`
- `OCCURRENCE_CAP_ZERO`

## Reason codes set after intake

- `COOLDOWN`
- `SUPPRESSED`
- `PREREQ_MISSING`
- `NO_FALLBACK_FITS`
- `DISPLACED_FINAL`
- `GATE_CLOSED`
- `PREREQ_WITHDRAWN`
- `CAPACITY_DISPLACED`
- `UNKNOWN_CEILING`
- `FALLBACK_DISPLACED`
- `READMITTED`

## Alias decision statuses

- `bound` the alias binds to the canonical name shown
- `collision` a stronger source already bound this alias
- `self` the alias and the canonical name are the same text
- `cycle` following the alias returned to a name already seen

## Edge drop reasons

- `SELF_EDGE`
- `DUPLICATE_EDGE`
- `UNRESOLVED_ENDPOINT`
- `UNCONVERTIBLE_UNIT`

## Policy layers

Their ranks are in `precedence_directive.docx` part A; the
list below is in no particular order of strength.

- `action`
- `context`
- `device`
- `global`
- `mandatory`
- `oneshot`
- `routine`
- `class_floor` is not a layer. It is the floor stage r04
  applies to the resolved cooldown after the layers have
  settled it, and it is what the audit records as the winning
  layer when the floor raised the value.

## Policy fields

- `tier`
- `intensity`
- `cooldown`
- `mandatory`
- `max_occurrences`
- `suppress`
- `fallback_chain`

## Stage identifiers

- `r01` unit normalisation
- `r02` identifier resolution
- `r03` routine expansion
- `r04` policy layer resolution
- `r05` initial eligibility
- `r06` dependency graph
- `r07` cycle settlement
- `r08` canonical order
- `r09` demand
- `r10` capacity binding
- `r11` fallback expansion
- `r12` precedence overturn
- `r13` state transitions
- `r14` feedback and publication

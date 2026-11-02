# Glossary

- **admitted movement**: a movement that cleared the headway ladder of stage 7.
- **base**: the path a variant names in its `variant_of` column.
- **candidate set**: the days of one period that satisfy a rule's `byday` and
  `bymonthday` conditions.
- **canonical identifier**: the single spelling of a path identifier that stage
  1 defines.
- **chain depth**: the number of bases between a path and its chain root.
- **chain root**: the path at the end of a path's base chain.
- **deferral**: a whole number of deferral steps added to every entry instant
  of one movement.
- **entry instant**: the UTC instant at which a movement reaches one section.
- **fold**: a local wall clock reading that two UTC instants name.
- **gap**: a local wall clock reading that no UTC instant names.
- **movement**: one path on one running day.
- **path minutes**: the admitted movement count of a path multiplied by the span
  of its route.
- **registered path**: a register row whose identifier is not on an alias cycle.
- **rejected path**: a path on a variant cycle, which runs on no date.
- **route span**: the largest section offset of a route, in minutes.
- **running day set**: the days a path runs on, after the stage it is named in.
- **service date**: the running day a movement's departure was taken from.
- **superseded file**: a file that carries a field it does not decide.
- **withheld movement**: a movement no deferral count cleared.

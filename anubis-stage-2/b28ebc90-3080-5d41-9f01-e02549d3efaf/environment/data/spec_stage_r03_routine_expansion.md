# Stage r03 - routine expansion

Fed by: r01, r02.
Feeds: r04, r05.

Expand every routine into the occurrences it fires this cycle,
under `expansion_policy.yaml`.

- A routine whose `enabled` column is not `yes` is withheld under
  `RETIRED_ROUTINE`.
- Resolve `action_ref`. A reference that does not resolve to a
  catalogue action is withheld under `UNRESOLVED_ACTION`.
- Carry the anchor, period, span start and span end under RR2, and
  apply the anchor sign under RR5. A quantity that cannot be carried
  withholds the routine under `UNCONVERTIBLE_UNIT`.
- Resolve the occurrence cap from three sources in order: the memo
  cap table, the routine layer `max_occurrences`, the memo default.
  The first source that records a cap settles it. A cap of zero or
  less withholds the routine under `OCCURRENCE_CAP_ZERO`.
- Generate `trigger = anchor + step * period` for `step` from zero.
  Stop when the trigger reaches the span end, when the cap is met, or
  after 512 steps. A trigger below the span start is discarded and
  does not consume the cap. A period of zero generates exactly one
  trigger, at the anchor, which the span rules then keep or discard.
- The occurrence index is the ordinal of the surviving occurrence
  from zero. The instance id is the routine id, a `#`, and the index
  in two digits.
- Place the occurrence in the window whose start is at or below the
  trigger and whose end is above it. Where two windows qualify, the
  one with the lower ordinal takes it. A trigger matching no window is
  withheld under `OUT_OF_DAY` and still consumes the cap.
- Publish `expansion_ledger.csv`.

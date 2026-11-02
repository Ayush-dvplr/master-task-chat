# Stage r11 - fallback expansion

Fed by: r10.
Feeds: r12.

Consult the fallback chain of every displaced instance.

- Take the displaced instances in canonical order.
- The chain is the instance's resolved `fallback_chain`, truncated to
  the memo's fallback chain depth cap.
- A candidate qualifies when it is a catalogue action, when its own
  policy resolved for this window, trigger and routine does not
  suppress it, when every hard prerequisite of the candidate in the
  surviving graph has an allocated instance in this window or an
  earlier one, and when no earlier displacement has already proposed
  that candidate for this window and device.
- The first qualifying candidate is proposed. It stands in for the
  displaced instance, runs on the displaced instance's device, and
  takes its own catalogue energy and class. Its instance id is the
  candidate action id, an `@`, and the displaced instance id.
- No capacity test happens here. Capacity is settled in r12.
- A displaced instance with no qualifying candidate is terminal under
  `NO_FALLBACK_FITS`. r12 carries these terminals forward with its
  own, and the suppression ledger records them under `r12`.
- Publish `fallback_expansion.json`.

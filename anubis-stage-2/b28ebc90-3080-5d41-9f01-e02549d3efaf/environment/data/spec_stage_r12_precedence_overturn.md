# Stage r12 - precedence overturn

Fed by: r11.
Feeds: r13.

Re-run the binding over the holders and the proposals together,
round after round, until no proposal is left or the cap is reached.

- The round cap is in `precedence_directive.docx` part C. It counts
  every binding of the chain, r10 included as round one, so r12
  runs rounds two up to the cap. A cap of two means one round here.
- The holders of a window and device start as the discretionary
  instances r10 allocated there. Round two takes the proposals of
  r11.
- In each round, for every window and device that received at least
  one proposal in that round, take its current holders together
  with the round's proposals for it, and offer them the same pool
  r10 offered at the start of its discretionary phase, under the
  same order key. Whatever fits becomes the holders. A window and
  device r10 never pooled keeps none of its proposals; they are
  terminal under `FALLBACK_DISPLACED`.
- A proposal or an earlier kept proposal that loses is terminal
  under `FALLBACK_DISPLACED`. An instance r10 allocated that loses
  is terminal under `DISPLACED_FINAL` and is recorded as overturned
  with the round that overturned it.
- When the round is not the last the cap allows, the instances it
  overturned consult their own fallback chains under exactly the
  rules of r11, the candidates already proposed for a window and
  device in any earlier round staying taken. Those proposals make
  the next round. An overturned instance with no qualifying
  candidate stays under `DISPLACED_FINAL`. Instances overturned in
  the last round consult nothing.
- Publish `precedence_reconciliation.json`, one group per window,
  device and round that bound proposals.

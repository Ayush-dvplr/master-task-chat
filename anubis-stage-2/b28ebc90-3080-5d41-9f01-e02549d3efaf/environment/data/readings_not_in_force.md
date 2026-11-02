# Readings this household does not support

Each entry names a reading of these papers that is plausible and
wrong, beside the reading in force. The list is a reading aid,
not a defect list: most of these readings appear nowhere in the
shipped project, and a reading absent from this list may still
be wrong.

1. **Not in force**: the last row for a key in a register wins.
   **In force**: only when two rows share a key *and* a
   revision (RR1).
2. **Not in force**: an empty cell means zero. **In force**: an
   empty cell means the field is absent and inherits from the
   next layer down; a written zero settles the field (RR4).
3. **Not in force**: the greatest revision in a register is the
   live one. **In force**: the live row is the greatest revision
   at or below the frozen revision for that key (RR1).
4. **Not in force**: a context whose start equals its end is
   active at that instant. **In force**: the interval is empty
   and the context layer does not apply.
5. **Not in force**: an instance whose elapsed time since the
   last firing exactly equals its cooldown is still cooling
   down. **In force**: the cooldown has elapsed and the instance
   is eligible.
6. **Not in force**: a carried cooldown replaces the resolved
   one. **In force**: the greater of the two applies.
7. **Not in force**: a soft edge withholds its dependent when
   the prerequisite does not fire. **In force**: soft edges only
   order; only hard edges withhold.
8. **Not in force**: an action whose demand exactly equals the
   pool is displaced. **In force**: equality fits, binds the
   pool and does not displace.
9. **Not in force**: a demand exactly at the implausibility
   threshold is quarantined. **In force**: only a demand above
   it is.
10. **Not in force**: a displaced action is discarded. **In
    force**: it is displaced, and its fallback chain is
    consulted.
11. **Not in force**: mandatory instances draw after the
    discretionary selection. **In force**: they draw first,
    before the reserve is withheld.
12. **Not in force**: an alias that maps to itself is a cycle.
    **In force**: it is a self alias and is ignored.
13. **Not in force**: a binding resolved through several aliases
    records one hop per link. **In force**: hops is one for
    every binding that resolves to another name, zero for one
    that resolves to itself.
14. **Not in force**: a dependency cycle is an error. **In
    force**: cycles are legal and are settled one edge at a
    time under the directive's key order.
15. **Not in force**: a gate key written at the very instant of
    the gated trigger counts. **In force**: only a write
    strictly before the trigger counts.

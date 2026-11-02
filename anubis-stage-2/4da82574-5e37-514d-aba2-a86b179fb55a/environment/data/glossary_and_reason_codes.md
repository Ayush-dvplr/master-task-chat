# Glossary and reason codes

**credit unit (cu)** the basis unit of every published quantity.

**canonical position** the one based index of an event in the
canonical order. Every range, watermark and probe is a position.

**watermark** the canonical position a checkpoint stands after.

**pending queue** the ordered list of events whose eligibility
predicate was false when they were offered. It is part of the state
and travels inside a checkpoint body.

**re offer round** one sweep of the pending queue after the window
is exhausted. Rounds run until a round admits nothing or the round
ceiling is reached.

**disposition** what became of a compensating event: `applied`,
`void_duplicate` or `void_unapplied`.

## Reason codes

| code | stage | meaning |
| --- | --- | --- |
| EVT-DRAFTREVISION | r01 | the record lodges above the frozen register revision |
| EVT-WITHDRAWN | r01 | the identifier sits in the withdrawn journal |
| EVT-UNKNOWNSTATION | r02 | the station is absent from the frozen register |
| EVT-UNKNOWNPROGRAMME | r02 | the programme is absent from the register |
| EVT-NONPOSITIVE | r01 | the normalised quantity is zero or below |
| EVT-IMPLAUSIBLE | r01 | the normalised quantity passes the memo ceiling |
| CMP-WITHDRAWN | r09 | the compensation link is absent or withdrawn |
| CMP-NOTARGET | r09 | the named target sits outside the canonical history |
| DEP-SELF | r07 | the record names itself as a dependency |
| DEP-CYCLE | r07 | the record sits on a dependency cycle |
| DEP-MISSING | r07 | a dependency is neither in the checkpoint nor earlier in the window |

A record that fails two tests carries the code that comes first in
the screening order in `eligibility_policy.yaml`.

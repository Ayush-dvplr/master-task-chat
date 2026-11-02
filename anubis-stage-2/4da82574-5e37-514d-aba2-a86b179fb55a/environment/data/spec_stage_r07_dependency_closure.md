# Stage r07: Dependency closure

`dependency_edges.psv` is the authoritative edge set. Only rows whose
`edge_kind` is `requires` and whose revision stands at or below the
frozen register revision are edges. The `depends_on` list carried inside
a journal record is a copy of an earlier edge set and governs nothing.

An event that names itself carries `DEP-SELF`. An event that sits on a
cycle in the edge graph carries `DEP-CYCLE`. These two are tested
before any other dependency test. A self edge is a cycle of one, so an
event that names itself also stands among the cycle members, and
`DEP-SELF`, tested first, decides its code.

An event sits on a cycle when some path of edges in force leads from it
back to itself, however long the path and wherever a walk that finds it
begins. An edge naming an identifier the canonical history does not
carry takes no part in the cycle test.

Otherwise each dependency is settled by the canonical position of the
event it names. A dependency whose position stands before the window
opening is already folded into the restored checkpoint and is satisfied
without being replayed. A dependency whose position stands at or after
the window opening and before the depending event is satisfied inside
the window. Anything else, including a dependency naming an identifier
that is not in the canonical history and a dependency standing later
than the depending event, leaves the event with `DEP-MISSING`.

The published closure counts how many dependencies each of the two
satisfying routes accounted for across the whole window, over the
events that clear every screening and dependency test. An event that is
set aside adds nothing to either count, even for a dependency of it that
was satisfied.

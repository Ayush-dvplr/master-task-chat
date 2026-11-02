# Attribution of stalls and the blame settlement

Every stall event names two threads. The worker of the segment is the thread
that waited. The owner column names the thread that held the lock at the moment
the wait was recorded. A thread can wait on one lock class and hold events on
several others in the same window.

## Budget ladders

Every lock class carries a ladder of budgets in the ladder table, indexed by
rung. Rung zero is the tightest budget the class admits and the highest rung it
carries is the loosest. Ladders are not all the same depth.

A lock class enters the window at the loosest rung its own ladder carries.

## Contention and implication

These two readings are taken against one assignment of rungs to lock classes.

A lock class is contended under an assignment when more of the counted events
blocked on it carry a wait span above its budget at its rung than carry a wait
span at or below that budget.

A worker is implicated under an assignment when more of the counted events it
owns are blocked on contended classes than are blocked on classes that are not
contended. A worker that owns no counted event is never implicated.

## The settlement

One condition governs the settled assignment, and it is read at every lock
class at once: no lock class stands above rung zero while any counted event
blocked on it is owned by an implicated worker.

Many assignments meet that condition, and the window reports the loosest of
them. Budgets only ever tighten away from the entering assignment, a ladder is
finite, and tightening a class can only add contention and only add implicated
workers, so the loosest assignment meeting the condition is unique and the
window is well defined.

## Quarantine and budget standing

A lock class that comes to rest at rung zero and is still contended under the
settled assignment is quarantined.

A counted event is within budget when its wait span is at or below the budget
of the lock class it is blocked on, read at that class's settled rung. The
entering budget has no standing once the assignment has settled.

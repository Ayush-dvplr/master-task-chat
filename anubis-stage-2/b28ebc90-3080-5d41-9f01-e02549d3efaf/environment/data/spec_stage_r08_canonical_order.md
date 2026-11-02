# Stage r08 - canonical order

Fed by: r07, r05.
Feeds: r09.

Put the surviving graph and the eligible instances in canonical
order.

- Order the actions by Kahn's method over the surviving edges: at
  each step take the least action identifier among those with no
  unsatisfied prerequisite. Every catalogue action appears, including
  actions no edge touches.
- Only an edge whose kind is `hard` imposes an instance level
  prerequisite. A `soft` or `advisory` edge orders the graph and
  withholds nothing.
- An eligible instance whose action has a hard prerequisite with no
  eligible instance at or before its own trigger is withheld under
  `PREREQ_MISSING`. Withholding one instance can withhold another;
  repeat until nothing changes.
- Order the surviving instances by trigger ascending, then by the
  action's position in the action order, then by instance id.
- Publish `canonical_action_order.json`.

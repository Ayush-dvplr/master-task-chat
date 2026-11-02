# Migration semantics

Rules M1 to M12. Field states, presence and the fill rule are in the header of
`null_semantics.ini`; corrections are in the header of `correction_log.txt`.

M1. A schema id is `<domain>.v<n>`; `schema_versions.json` lists every schema
with its `domain` and a `canonical` flag. Each domain has one canonical schema,
the target of every record of that domain.

M2. `migration_edges.csv` columns: `edge_id`, `source`, `target` (schemas of one
domain), `requires`, `operations`, `cost` (positive integer).

M3. `requires` is empty or a `;`-separated list of `has:<field>` and
`lacks:<field>`. `has:f` holds when f counts as present (N2); `lacks:f` holds
when it does not.

M4. `operations` is empty or a `;`-separated list applied left to right:
`rename:a>b` moves field a, in whatever state it is (an explicit null stays an
explicit null), to b, replacing b; nothing happens when a is absent.
`drop:a` removes a. `add:a` applies the fill rule (N4). `cast:a:int`,
`cast:a:float`, `cast:a:str` convert a value (M5); null and absent are left
alone.

M5. Casts. int: an int stays; a float with no fractional part becomes that int;
a string that is an optional sign and digits (surrounding spaces ignored)
becomes that int. float: an int or float becomes a float; a decimal string
(optional sign, digits with an optional point) becomes a float. str: an int or a
float becomes Python `str()` of it. Anything else, booleans included, is left
unchanged.

M6. An edge applies to a record when every prerequisite holds on the record as
it is at that point of the plan: after the operations of every earlier edge of
the plan (and, during execution, after the corrections applied so far).

M7. A plan is a list of edges, each leaving the schema the previous one reached,
that starts at the record's schema, ends at the canonical schema, and where every
edge applies (M6). A plan may pass through a schema more than once. A record
already at its canonical schema has the empty plan. When no plan exists the
record is rejected with E_UNREACHABLE.

M8. Among all plans the planner returns the one with the smallest total cost;
among plans of equal total cost, the one whose list of edge ids is smallest when
the lists are compared element by element as strings, first edge first (the way
Python compares two lists of strings).

M9. Planning sees the payload after null-token replacement and never sees
corrections. Two records with the same source schema can therefore need
different plans.

M10. `state_signature` returns, for each field named in a `requires` entry of
any edge whose source schema belongs to the record's domain, the field's state
(`absent`, `null` or `value`, N1), keyed by field name in sorted order.

M11. Execution follows the plan edge by edge. Corrections are applied as the C
rules say. Before each edge its prerequisites are checked on the record as it is
at that moment. When one fails, execution stops: status `failed`, code
E_PREREQ_FAILED, `failed_edge` that edge, `completed_steps` the number of edges
already applied, `schema` the schema reached, `payload` null.

M12. `execute_plan` returns `{"status", "code", "schema", "payload",
"completed_steps", "failed_edge", "corrections_applied"}`; on success status is
`migrated`, code and failed_edge are null, schema is the canonical schema,
payload the migrated record, and `corrections_applied` lists the ids of the
corrections applied, in the order they were applied.

# Report forms

Write all nine report files on every successful call. Each is a JSON object.
Encode UTF-8 with literal non-ASCII characters, no BOM, recursively ascending
text object keys, no indentation or spaces between tokens, and one trailing LF.
Arrays retain the order specified here. Integers are JSON integers, flags are
JSON booleans, and an empty collection is an empty object or array of its stated
kind. Every object has exactly its defined keys. Report names are case-sensitive.

region_North.json has name (North), in_scope (whether it has events), events
(the ordered event objects), final_state (North final state), units (sum of event
unit quantities). Each event object has event (integer identifier), instant
(corrected instant), identity (resolved text), units (signed unit quantity),
state (the state after that event).

policy_audit.json has final_offsets (source-to-offset object for the last epoch),
identity_totals (identity-to-summed-unit-quantity object for identities reached
by events), weighted_state (sum of event identifier times that event's state).
It carries one offset per source, and no epoch timeline.

region_East.json has name (East), in_scope (whether it has requests), credits
(ordered request objects), total (sum of all credits). Each request object has
request (integer identifier), account (text), credit (signed credit).
segment_commercial.json has name (commercial), in_scope (whether it has
requests), accounts (account-to-total-credit object for accounts reached),
weighted_credit (sum of request identifier times its credit).

region_South.json has name (South), in_scope (whether it has streams), streams
(ordered stream objects), total (sum of settled units). Each stream object has
stream (identifier), x and y (settled pair), units (settled units).
segment_public.json has name (public), in_scope (whether it has streams),
settlement (sum of each stream's settled units times its one-based position in
the ordered stream list), eligible (eligible stream identifiers in that order).

region_West.json has name (West), in_scope (whether it has amendments), state
(the final amendment state, or the initial least-to-greatest path fold if there
are no amendments),
weighted_states (the weighted states defined in replay.md), revised (applied
amendment count). data_quality.json has amendments (the ordered amendment
objects), orphan_count, superseded_count, applied_count (counts of each status).
An amendment object has amendment (integer identifier), status (orphan,
superseded or applied), state (its path-fold state from replay.md).

summary.json has report_id (policy's report_id), parts (an object mapping North
to its final_state, East to its total, South to its total, West to its state),
total (sum of parts), residual (total minus the sum of the North identity_totals
in policy_audit.json, the commercial accounts in segment_commercial.json,
the South total and the West state). Residual is the adjustment between raw
North quantities and its replay valuation, and may be signed. The conservation
identity connects summary, audit, commercial and regional reports: the four
stated operands plus residual equal total. Each operand uses its lane definition.

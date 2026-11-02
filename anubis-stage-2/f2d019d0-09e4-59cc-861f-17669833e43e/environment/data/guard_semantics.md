# Guard keys

One code object exists for the router and one for each index in
`moe_layer_indices`, named `moe_block_<index>`. Each rank holds its own cache of
compiled entries for each code object.

Dimensions, in the order they appear in a key:

- the router code object guards `tokens`
- an expert region guards `capacity` and `local_experts` and nothing else,
  because the padded dispatch tensor carries no token axis once the router has
  scattered into slots

Values: `tokens` is the token count of the step, `capacity` is `rank_bucket` for
the rank holding the entry, `local_experts` is the number of experts placed on
that rank. Marking `tokens` dynamic therefore reaches the router alone, and the
router is never captured.

## Promotion

Promotion is tracked per code object and per dimension and is shared across
ranks. A dimension named in `mark_dynamic` is dynamic from the first step. Any
other dimension accumulates the distinct values it has been compiled against.
The pending value is inserted into that set before the count is compared, so the
count includes the shape currently being compiled. When the count reaches
`promotion_threshold` the dimension becomes dynamic for that code object from
that compilation onward. Promotion happens only when
`dynamic_promotion_enabled` is true, and a promotion is never undone.

The revision register decides whether the pending shape counts. Read it.

## Key text

Each dimension contributes one component and the components are joined with a
single vertical bar in the dimension order above. A dimension contributes the
literal `dyn` when it is dynamic **and** its value is neither zero nor one. A
dynamic dimension whose value is zero or one contributes that value, because the
compiler specialises those two sizes even after a dimension has gone dynamic.
Every other dimension contributes its decimal value.

The static dimension count of a key is the number of components that are not
`dyn`. The count taken before the pending promotions are applied and the count
taken after are both recorded, and their difference is the guard delta of the
event.

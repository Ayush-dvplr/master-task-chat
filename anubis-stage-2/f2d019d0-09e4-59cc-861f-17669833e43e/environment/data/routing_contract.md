# Router and top k dispatch

## Logit

For token `i` and expert `e`, with `J = router_jitter_slots`:

```
token_bits[i]  = floor(token_salt[i] * 2 ** 52)
expert_bits[e] = floor(expert_phase[e] * 2 ** 52)
affinity(i, e) = the value returned by one update of the stream generator seeded
                 with the mixing hash of token_bits[i] and expert_bits[e]
u(i, e)        = (affinity(i, e) >> 11) * 2 ** -53
b_e            = (bias_draw[e] * 2 - 1) * bias_gain[e] when the bias is enabled,
                 otherwise 0
j_ie           = (jitter[(i + e) mod J] * 2 - 1) * jitter_scale when J > 0,
                 otherwise 0

logit(i, e) = (u(i, e) * 2 - 1) + b_e + j_ie
```

The mixing hash is the one named in `stream_contract.md`, fed the two integers in
that order. The generator is constructed from the hash and updated once; the
returned state is the affinity. `bias_gain` comes from `expert_bias_table.csv`
and `jitter_scale` from `model_topology.json`. Every named quantity above is
rounded to the published decimal count before the next one consumes it.

## Quantisation

Ranking never sees the raw logit. It sees

```
q(i, e) = round_half_even(logit(i, e) * quantization_levels) / quantization_levels
```

with `quantization_levels` from `model_topology.json`. Half way values round to
the even multiple. Ties on `q` are common and are resolved by the sealed key.

## Selection

Experts are ordered by descending `q`, and ties on `q` are broken by a sort key
built from four fields whose order is sealed rather than printed here. The first
`top_k` experts in that order are selected. Tokens are processed in ascending
token index and the four fields are

- `expert_index`, ascending
- `running_load`, the number of assignments already made to that expert within
  the current step, ascending
- `placement_rank`, the mesh rank owning the expert, ascending
- `bias_rank`, the integer part of ten times the `bias_gain` of the expert,
  ascending. Several experts share a value

A tie break event is recorded whenever more than one expert presents the value
that the last selected slot holds. The event carries the step, the token index,
that quantised value, the sorted list of every contender and the sorted list of
the contenders actually selected.

## Combine weights

Let `floor_i` be the smallest `q(i, e)` over **all** experts for that token, not
only the selected ones. For each selected expert

```
shift = q(i, e) - floor_i + 1
weight = shift / sum of the shifts of the selected experts
```

Each weight is rounded independently; they are not renormalised afterwards.

# Expert parallel placement

`num_experts` must divide by `ep_world_size`. Each rank receives exactly
`num_experts / ep_world_size` experts.

Placement is table driven.

1. Sort experts ascending by `(placement_group, expert_index)` using
   `placement_group` from `expert_placement.csv`.
2. Read the rows of `rank_affinity.csv` whose `ep_world_size` matches the run and
   sort them ascending by `group_order`. That yields a rank order.
3. Cut the sorted expert list into consecutive blocks of
   `num_experts / ep_world_size` entries. Block `k` lands on the `k` th rank of
   the rank order.

The rank order is not the natural rank order and the expert list is not the
natural expert order. Neither shortcut reproduces the shipped placement.

## Buckets

```
rank_bucket(r) = max capacity(e) over the experts placed on rank r
alltoall_bucket = max rank_bucket(r) over every rank
```

The guard key of a compiled expert region uses `rank_bucket` for the rank that
owns the region. The exchanged payload uses `alltoall_bucket`. These are two
different quantities and only coincide when the mesh happens to be balanced.

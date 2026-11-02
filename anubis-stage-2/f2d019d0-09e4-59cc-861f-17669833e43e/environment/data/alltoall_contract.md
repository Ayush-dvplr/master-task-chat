# Collective exchange

Each step exchanges a uniform payload.

```
payload_slots = alltoall_bucket * ep_world_size * experts_per_rank
rank_bucket_spread = max rank_bucket - min rank_bucket
```

A step is uniform when the spread is zero. The cost of the exchange is

```
alltoall_us = fixed_us + per_slot_us * alltoall_bucket * ep_world_size
```

with both coefficients read from `alltoall_cost_table.csv` for the world size in
force. A world size of one has both coefficients at zero.

# Deterministic input stream

Every run is reproducible from its configuration alone. No file records the
per step token features; they are drawn.

## Generator

A 64 bit xorshift with the update applied in this order, all arithmetic masked
to 64 bits:

```
x ^= (x << 13)
x ^= (x >> 7)
x ^= (x << 17)
```

`next_u64` applies the update and returns the new state. A unit draw is
`(state >> 11) * 2 ** -53`. A zero seed is replaced by `0x9E3779B97F4A7C15`.

## Per step seed

```
h = 0xCBF29CE484222325
for part in (config.seed, step):
    h ^= part
    h = (h * 0x100000001B3) mod 2**64
    h ^= (h >> 29)
```

The step index is one based. The generator is constructed fresh for every step
from `h`.

## Consumption order

Exactly these blocks are drawn, in this order, and nothing else:

```
for count in (tokens_in_step,
              num_experts,
              num_experts if expert_bias_enabled else 0,
              router_jitter_slots):
    draw count unit values
```

The first block is `token_salt`, the second is `expert_phase`, the third is
`bias_draw`, the fourth is `jitter`. When `expert_bias_enabled` is false the
third block consumes nothing at all and every `bias_draw` entry is treated as
`0.5`, which the routing contract then turns into a zero bias.

`tokens_in_step` is read from `seq_length_schedule.csv` for the profile named by
the configuration, ordered by the `step` column, cycled when the run is longer
than the schedule.

# Numeric contract

Two dtypes are in play on the compiled path. Storage is bfloat16, which is the
top sixteen bits of a binary32 value rounded to nearest with ties to even.
Accumulation is binary32. The dispatch payload additionally passes through an
eight bit float described in `fp8_format_notes.md`.

The compiled path applies the casts at these points, in this order, for each
expert walked in ascending expert index and for each accepted slot walked in
ascending slot index:

1. the token feature `t` is stored
2. the combine weight `w` is stored
3. `raw = w * (1 - t * 0.25)` is accumulated
4. `raw * payload_scale` is accumulated and then cast to the eight bit float
5. the payload divided by `payload_scale` is accumulated
6. the running expert accumulator absorbs it and is accumulated

After the slots of an expert are exhausted:

7. the expert output is the accumulator divided by the number of accepted slots
   and is stored. An expert with no accepted slot stores a zero
8. each contribution `output * cost_weight` is accumulated
9. the step signal accumulates those contributions in ascending expert index
10. each gradient `output * signal_weight * cost_weight` is accumulated
11. each scaled gradient `gradient * loss_scale` is accumulated
12. each squared scaled gradient is accumulated
13. the sum of squares is accumulated
14. each clipped scaled gradient is accumulated
15. each unscaled gradient is accumulated
16. each parameter update is stored
17. the loss terms are rounded

The eager reference performs the identical walk in binary64 with no cast at any
of those points. The two paths therefore differ only by rounding, and the parity
band measures that difference.

`payload_scale`, `signal_weight`, `base_loss` and `decay_rate` come from
`model_topology.json`.

```
loss(step) = base_loss / (1 + decay_rate * step) + aux_loss(step)
           + signal_weight * step_signal(step)
```

Each of the three terms is rounded before the sum, and the sum is rounded.

Every published float is rounded to `float_decimals` from
`validation_tolerances.json`, except the timing figures which use
`time_decimals`. A negative zero is published as zero.

# Step time

Every named term is rounded to `time_decimals` before the total consumes it, and
the total is rounded again.

```
compile_us  = sum over the recompile events of the step of the cost read from
              compile_cost_table.csv for the compile mode and for the static
              dimension count taken **before** the pending promotions applied
capture_us  = capture_us of the mode times the number of successful captures
compute_us  = max over ranks of the sum over the experts on that rank of
              kernel_us_per_slot * rank_bucket(rank)
              multiplied by replay_discount when at least one capture succeeded,
              otherwise unscaled
alltoall_us = see the collective contract
bubble_us   = sum over fired causes of bubble_us times the number of expert
              layers, plus sync_bubble_us when the step recompiled anything
step_us     = compile_us + capture_us + compute_us + alltoall_us + bubble_us
```

The eager reference uses the same walk with no compile cost, no capture cost, no
bubble, no discount, and `compute_us` multiplied by `eager_compute_multiplier`.

The throughput gate divides the eager total by the compiled total over the steps
strictly greater than `warmup_bound`. `amortized_compile_us` divides the compile
cost of the whole run by the number of gated steps.

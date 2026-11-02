# Balance term

```
fraction(e)    = demand(e) / total_assignments
probability(e) = gate_mass(e) / token_count
aux_loss       = aux_loss_weight * num_experts * sum over e of
                 fraction(e) * probability(e)
```

`demand` is the count recorded before capacity is applied. `gate_mass` is the sum
of the combine weights of every assignment naming the expert, again before
capacity is applied. Each fraction and each probability is rounded when it is
formed, and either one is zero when its denominator is zero. Each product is
rounded before the running sum absorbs it and the sum is rounded before the
weight multiplies it. The revision register decides which of the two sourcings
is in force. Read it.

The convergence record, the parity record and the settled gate verdicts all
compare against `parity_band`. The sweep's `convergence_band_unmet` cause
compares the probe horizon deviation against `settlement_parity_band`. The two
figures differ and neither substitutes for the other.

`load_dispersion` is the largest fraction minus the smallest fraction taken over
the experts whose demand is non zero. Experts with zero demand are excluded from
both ends of that comparison; they are not treated as zero. With exactly one live
expert the dispersion is zero and with none it is null.

`expert_utilization` publishes one entry per expert in ascending expert index. An
expert with zero demand publishes null. Every other expert publishes its accepted
count divided by its demand, multiplied by its fraction.

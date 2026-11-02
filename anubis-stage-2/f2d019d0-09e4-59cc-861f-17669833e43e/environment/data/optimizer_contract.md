# Optimizer

```
gradient(e)   = output(e) * signal_weight * cost_weight(e)
scaled(e)     = gradient(e) * loss_scale
norm          = square root of the sum over e in ascending index of scaled(e) ** 2
reference     = clip_threshold * loss_scale
factor        = 1 when norm is at most the reference, otherwise reference / norm
unscaled(e)   = scaled(e) * factor / loss_scale
parameter(e)  = parameter(e) - learning_rate * unscaled(e)
```

The norm is taken on the scaled gradients and compared against the scaled
reference. Unscaling before clipping is a different computation on this path
because the casts land in different places. Parameters start at zero.

A step is clipped when the norm is strictly greater than the reference.

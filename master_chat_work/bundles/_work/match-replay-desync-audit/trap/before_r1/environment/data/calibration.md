# Calibration slice

The engine writes eleven quantities into its captures that no shipped file
states. For each one the set of values it may take is published here, together
with one control figure. The figures are published in an order in which each is
fixed by the quantities the figures ahead of it pin, together with one further
quantity. At least one value of that further quantity reproduces the figure, and
the value the engine used is one of them.

Every control figure is the twelve character digest this engine stamps over the
material the row names.

| quantity | candidate values | control | the control reads |
| --- | --- | --- | --- |
| `frame_bias_limit` | 4 through 15 | CTRL-A | the frame bias the capture headers carry |
| `weave_seed_offset` | 17 through 30 | CTRL-B | the payload line order inside every block |
| `sentinel_code_value` | 200 through 215 | CTRL-C | the payload bytes once the reserved byte is unwrapped |
| `drift_modulus` | 5 through 16 | CTRL-D | the payload bytes once the block mask is lifted |
| `seal_label_index` | 0 through 11 | CTRL-E | the opening payload of every capture once the label mask is lifted |
| `spin_modulus` | 7 through 18 | CTRL-F | the opening entry of every capture once its bytes are set straight |
| `shadow_pad_base` | 3 through 14 | CTRL-G | every entry of every capture once the padding is set aside |
| `alias_donor_shift` | 1 through 10 | CTRL-H | every entry once the recorded words are read against the right table |
| `echo_window_span` | 2 through 13 | CTRL-I | every entry once the repeated slots take the payload they inherit |
| `cadence_modulus` | 2 through 11 | CTRL-J | the cadence class every surviving unit falls in |
| `upkeep_target_scale` | 11 through 22 | CTRL-K | the upkeep target the engine settles against |

| control | published figure |
| --- | --- |
| CTRL-A | `e06544fda91a` |
| CTRL-B | `6de353b13e0d` |
| CTRL-C | `5ca8d54f2e85` |
| CTRL-D | `d48421311491` |
| CTRL-E | `54619f819922` |
| CTRL-F | `26c44f4c6e4a` |
| CTRL-G | `3e17132d6284` |
| CTRL-H | `e04399bf5857` |
| CTRL-I | `175a8793b874` |
| CTRL-J | `a2e4b1a2a02c` |
| CTRL-K | `a0320f91a53c` |

A candidate is rejected against the first control figure in the order above
that separates it from the value the engine used.

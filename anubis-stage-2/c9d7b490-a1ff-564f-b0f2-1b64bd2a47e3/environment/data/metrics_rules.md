# Metrics rules

The metric population of a group of observations is its observations that
carry no exclusion and are labelled `bad` or `good`. A higher score means a
lower risk.

`auc_ppm` is the probability that a `good` member of the population has a
higher score than a `bad` member, counting a tied pair as one half, over every
pair of one `good` and one `bad` member. `ks_ppm` is the largest absolute
difference, over every score `c` held by a member, between the share of `bad`
members scoring at or below `c` and the share of `good` members scoring at or
below `c`. `bad_rate_ppm` is the share of the population labelled `bad`.

Each of the three is an exact fraction expressed in parts per million and
rounded once to the nearest integer, a fraction of exactly one half going to
the even integer. `auc_ppm` and `ks_ppm` are `null` when the population has
no `bad` or no `good` member, and `bad_rate_ppm` is `null` when the
population is empty.

`population`, `bad` and `good` count the population and its two labels.
`approved` counts the approved members of the population and `approved_bad`
the approved members labelled `bad`.

# T01 reading canonicalisation

## Input

comparison_session_log.csv holds every acquisition attempt the receivers made
during the interval. session_withdrawal_journal.tsv names the acquisition
sessions the desk has withdrawn. link_register.csv is the frozen register of
links. epoch_grid_policy.yaml holds the grid and attribution parameters.

## The publication grid

The interval carries thirty grid epochs, numbered 1 to 30. The instant of
epoch k is

    interval_start_epoch_s + (k - 1) * grid_step_seconds + grid_instant_offset_s

taking interval_start_epoch_s and grid_step_seconds from network_config.json
and grid_instant_offset_s from epoch_grid_policy.yaml.

## Attribution

A row is attributed to epoch k when its acq_time_s satisfies

    instant(k) - attribution_tolerance_s  <=  acq_time_s  <  instant(k) + attribution_tolerance_s

The window is half open. The lower edge belongs to the epoch and the upper
edge does not. The tolerance is smaller than half a grid step, so no row is
attributable to two epochs. A row attributable to no epoch is set aside; it is
never moved to the nearest epoch.

## Setting rows aside

The predicates below are ordered. A row is tested against them in this order
and the first one that matches is the reason recorded for it. A row is never
recorded twice.

    1. DR_OUTSIDE_INTERVAL   the row is attributable to no grid epoch
    2. DR_SESSION_WITHDRAWN  session_id appears in the withdrawal journal
    3. DR_LINK_UNREGISTERED  link_id is absent from link_register.csv
    4. DR_SELF_LOOP          the link register gives the link the same node
                             on both sides
    5. DR_NO_LOCKED_ATTEMPT  the cluster the row belongs to holds no attempt
                             in lock state LOCK_HELD

Predicates 1 to 4 are decided row by row. Predicate 5 is decided once the
surviving rows have been grouped, and when it fires it sets aside every
remaining row of that cluster.

## Clusters and the canonical reading

The surviving rows are grouped into clusters by the pair (link_id,
epoch_index). The canonical reading of a cluster is chosen from the rows of
that cluster whose lock_state is LOCK_HELD. Rows in any other lock state are
never eligible, whatever their attempt number.

Among the eligible rows the canonical reading is the one with the greatest
attempt_no. Two receivers can report the same attempt number for one cluster.
When the greatest attempt number is held by more than one row, the row with
the smallest absolute difference between acq_time_s and the instant of the
epoch wins, and if that is still equal the row with the earlier acq_time_s
wins.

## Output

The canonical reading of every surviving cluster, carrying its session, its
receiver, its attempt number, its acquisition time, its raw offset and the
number of rows the cluster held before selection. Every set aside row with the
reason recorded for it.

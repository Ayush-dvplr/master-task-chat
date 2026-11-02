# Boundary cases

An mjd equal to an epoch's `mjd_end` belongs to the NEXT epoch (half-open intervals). E1=[59000,59120), E2=[59120,59240), E3=[59240,59360). An mjd of 59120 is in E2, not E1.

A `raw_counts` equal to the instrument's `full_well_counts` is NOT saturated and is not clipped; only a reading strictly above the full well is.

A band whose every live observation is saturated has no eligible median sample, so that band carries no band median key and flags no anomaly.

An exposure attribution whose leftover is 0 gives no instrument an extra micro-jansky, and the list of remainder recipients is then empty.

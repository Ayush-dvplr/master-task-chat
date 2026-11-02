# Calibration slice

The calibration population is held out. It is settled under the same rules as the
field population and it appears in no region report and in no service class report.

The authority has already settled this population with the withheld packet
constants in place and publishes the control figures below. Exactly one assignment
of the withheld constants reproduces every figure at once.

## Control figures

- payload_origin_total = 20435556262
<!-- the sum, across the calibration blocks, of the first four bytes of each block payload read as one big endian word once that payload sits at its true origin -->
- record_span_total = 36
<!-- the count, across the calibration blocks, of records that carry the extended slack field -->
- calibration_order_total = 95
<!-- the count of genuine records across the calibration blocks once filler has been discarded -->
- island_field_total = 56530
<!-- the sum, across the calibration blocks, of the four auxiliary header words read in their intended byte order -->
- ordinal_position_checksum = 8073
<!-- the sum, across the calibration blocks, over every physical record position of one plus that position multiplied by one plus the logical ordinal that travels there -->
- masked_load_total = 7530
<!-- the sum of load units over every genuine calibration record -->
- folded_slack_total = 6090
<!-- the sum of due offsets over every genuine calibration record -->
- delta_weight_total = 44763
<!-- the sum of dispatch weights over every genuine calibration record -->
- drift_day_total = 64453
<!-- the sum over every genuine calibration record of its submission day multiplied by one plus its logical ordinal -->
- canonical_client_total = 4478
<!-- the sum over every genuine calibration record of the numeric part of the identifier of its governing client multiplied by one plus its logical ordinal -->
- backref_program_total = 2909
<!-- the sum over every genuine calibration record of the position of its programme within the ascending list of distinct programme identifiers multiplied by one plus its logical ordinal -->
- billable_slot_total = 6045
<!-- the sum of billable slots over every calibration record that carries a governing programme revision and a client able to hold it -->

Each figure is an exact whole number. A constant assignment that reproduces a
figure is separated from one that does not by that figure alone, once every figure
above it in this list has been settled.

# Stage P14, the publication

RULE P14.a  Every document named by output_schema_reference.md is
written, with the header, the column order, the key order and the
row order that paper prints, under the serialisation contract.

RULE P14.b  A reefer is powered in an interval when the correction
left it powered there. Its base draw is the draw of that interval
and zero otherwise. Its allowance is what stage P09 placed there.

RULE P14.c  The schedule state reads powered_with_allowance when the
base draw and the allowance both stand above zero, powered when only
the base draw does, allowance_only when only the allowance does and
held when neither does.

RULE P14.d  The energy of a schedule row is its base draw divided by
four and rounded half up, plus its allowance watt hours.

RULE P14.e  A substation report is published for every substation
the reporting roster carries. Its served energy is the sum, over its
feeders and intervals, of the final load divided by four and rounded
half up.

RULE P14.f  The unmet requirement report carries a row for every
queued reefer standing at a shortfall above zero or an unplaced
allowance above zero.

RULE P14.g  The publication manifest is written last and carries the
two digests the serialisation contract defines.

RULE P14.h  The feeder state of the schedule by feeder reads under
the three readings of RULE P06.f, taken against the adjusted
capacity of that feeder and interval plus its battery support in
place of the reserved capacity.

RULE P14.i  The measure of a stage in the audit trace is the count
of data rows the stage document of that stage carries, the stage
documents being the fourteen the serialisation contract lists
first, one for each stage in stage order. Five stages publish a
quantity in place of a count: stage p08 publishes the watt hours
the battery cycled over the day, stage p10 the energy charge of
the day in cents, stage p12 the number of sweeps that ran, stage
p13 the unmet mandatory watt hours and stage p14 the number of
documents the publication carries.

## Published documents

Every remaining document of the publication.

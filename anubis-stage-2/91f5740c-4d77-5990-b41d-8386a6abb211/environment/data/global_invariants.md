# Global invariants

The settled schedule satisfies all of the following at once.

- Conservation. The net value of the settled schedule equals the sum of the net
  value reported for the four regions and equals the sum of the net value reported
  for the two service classes. Both residuals are zero.
- Partition closure. Every placed order appears in exactly one region report and in
  exactly one service class report, and the two partitions cover the same set of
  orders. The region of an order is the region the site directory gives for the home
  site of its governing client.
- Identity uniqueness. No order identifier appears twice in the settled schedule.
- Capacity. No lane that publishes a positive slot capacity carries billable slots
  beyond it.
- Referential closure. Every placed order names a lane on the roster, a client in
  the directory and a programme revision in the registry.
- Idempotence. Settling the same population twice yields the same schedule byte for
  byte.
- Population separation. The calibration population is settled under the same rules
  as the field population and appears in no region report and in no service class
  report.

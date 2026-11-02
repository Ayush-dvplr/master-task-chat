WORKED EXAMPLES

The shift used below, KP-0000-S00, is invented. It has two blocks,
one berth, two measures and two rungs, so the shape of each document
is visible in a few lines. None of its figures belong to this shift.
Use these to settle the form of a document, and the schema reference
and the serialisation contract to settle everything else.

SECTION 1  audit_trail.conf

```
# The audit trail of one shift.
[shift]
shift_id = KP-0000-S00
live_sheet_name = Example
reference = QCR-000000

[counts]
admitted_moves = 2
canonical_events = 3

[ladder]
LR_UNKNOWN_BOX = 1
LR_SEALED_ZONE = 0

[movement]
confirmed = 2
set_aside = 1
```

The file opens with the comment line exactly as printed. A section
header is preceded by one empty line except the first. A key line is
the key, one space, an equals sign, one space, the value.

SECTION 2  daily_operational_summary.md

```
# Daily operational summary

shift KP-0000-S00 at reference QCR-000000

- admitted_moves: 2
- canonical_events: 3

## Ladder

- LR_UNKNOWN_BOX: 1
- LR_SEALED_ZONE: 0

## Identity checks

- loaded_and_deferred_partition_eligible: yes
- moved_boxes_all_on_yard: yes
```

SECTION 3  vessel_reconciliation.xml

```
<?xml version="1.0" encoding="utf-8"?>
<vessel_reconciliation>
  <shift_id>KP-0000-S00</shift_id>
  <vessels>
    <vessel id="VS-000">
      <berth_id>bt_example</berth_id>
      <eligible_count>2</eligible_count>
      <loaded_count>1</loaded_count>
      <deferred_count>1</deferred_count>
      <share_minutes>7</share_minutes>
    </vessel>
  </vessels>
  <identity name="moved_boxes_all_on_yard">yes</identity>
</vessel_reconciliation>
```

A vessel with no eligible box still carries its element with counts
of zero. No element is ever written in the self closing form.

SECTION 4  one pass of the quay ration

Two vessels of one service group share a pool of 20 crane minutes.
VS-A declares 14 minutes and VS-B declares 6. Neither ceiling binds.
The damping fraction is one half and the minimum step is 2. Both
shares stand at zero when the pass opens.

  need     VS-A 14, VS-B 6, total 20
  unallocated pool  20 less 0 equals 20
  target   VS-A 0 + 20 times 14 over 20 equals 14
           VS-B 0 + 20 times 6 over 20 equals 6
  no cap binds, so nothing is freed and nothing is redistributed
  aim      VS-A 14, VS-B 6
  damped   VS-A 0 + one half of 14 equals 7
           VS-B 0 + one half of 6 equals 3
  rounded  VS-A 7, VS-B 3

The second pass opens from 7 and 3, not from 14 and 6, and not from
the unrounded values. Its needs are 7 and 3 and its unallocated pool
is 10.

Now suppose instead the damped move of VS-B had been three eighths of
a minute. That rounds to zero, VS-B has not reached its aim, and so
VS-B moves by the minimum step to 2 rather than standing still. Had
its aim been 1, the step would have carried it to 1 and no further,
because a step never carries a share past its aim.

SECTION 5  an empty delimited document

A delimited document with no rows is its header line and one line
feed, like this three column example.

```
event_key,order_id,reason_code
```

A line delimited json document with no records is a file of zero
bytes.

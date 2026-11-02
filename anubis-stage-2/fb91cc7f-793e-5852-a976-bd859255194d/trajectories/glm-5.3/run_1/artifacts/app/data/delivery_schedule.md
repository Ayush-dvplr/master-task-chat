# Delivery schedule

Every cycle the lab settles is published as a fixed set of documents. This
page is the house schedule for those documents. It fixes their names, their
fields and the order of their rows. It carries no figures from any cycle: the
figures are what a settlement produces, and the schedule only says where each
figure is written down.

The schedule is descriptive, not instructive. It does not say how any figure
is computed. The rulebooks and the invariants govern that.

## House serialisation

Every document is JSON. Object keys are written in ascending order, the indent
is two spaces, and the file ends with one newline. A whole number is written
as a whole number and never as a decimal or a string. A field that holds no
rows is written as an empty list, never omitted and never null.

Where a field below is written `<int>` it holds a whole number, `<str>` a
string, `<bool>` either true or false. A name in angle brackets used as an
object key, such as `"<programme id>"`, means the key is the identifier itself.

## summary.json

The one page overview of the cycle. Fourteen whole numbers, no nesting.

```
{
  "admitted_count": <int>,
  "admitted_frames": <int>,
  "conformed_programme_count": <int>,
  "held_count": <int>,
  "held_frames": <int>,
  "impaired_total": <int>,
  "lane_frames": <int>,
  "lane_seated_count": <int>,
  "recovered_total": <int>,
  "settled_total": <int>,
  "settlement_cycle": <int>,
  "shed_count": <int>,
  "shed_frames": <int>,
  "void_programme_count": <int>
}
```

## reconciliation.json

The closing check. `stages` always carries exactly five rows, always in this
order: `conform`, `impairment`, `admission`, `seating`, `cascade`. For each
row `residual` is `left` less `right`, and `closes` says whether that residual
is zero. The document's own `residual` is the sum of the absolute stage
residuals.

The `conform` row balances programme counts: `left` is the number of programmes
in the cycle and `right` is the conformed count plus the void count. The other
four rows balance frames. On `impairment`, `left` is the impaired total and
`right` is the recovered total plus the unrecovered total. On `admission`,
`left` is the settled total and `right` is the admitted frames plus the held
frames. On `seating`, `left` is the admitted frames and `right` is the sum of
the vault loads. On `cascade`, `left` is the held frames and `right` is the
lane frames plus the shed frames.

```
{
  "residual": <int>,
  "settled_total": <int>,
  "stages": [
    {
      "closes": <bool>,
      "left": <int>,
      "residual": <int>,
      "right": <int>,
      "stage": <str>
    }
  ],
  "vault_and_lane_total": <int>
}
```

## reel_audit.json

The state of the scan book once identity is resolved.

`reels` carries one row for every reel identifier that appears in the scan
book, in ascending reel identifier order. A row's `state` is `live` when the
reel is its own canonical element, `folded` when it resolves onto another live
element, and `retired` when the element it resolves to has been retired.

`canonical_elements` and `retired_elements` are in ascending identifier order.
`folded_elements` is keyed by the canonical elements that absorbed at least
one fold, ascending, and each value lists the absorbed identifiers ascending.
`usable_frames` is keyed by every canonical element, ascending.

```
{
  "canonical_elements": [<str>],
  "folded_elements": {
    "<canonical element id>": [<str>]
  },
  "reels": [
    {
      "canonical_id": <str>,
      "element_class": <str>,
      "reel_id": <str>,
      "registration_shift": <int>,
      "scan_cadence_mhz": <int>,
      "scanned_frames": <int>,
      "state": <str>
    }
  ],
  "retired_elements": [<str>],
  "settlement_cycle": <int>,
  "usable_frames": {
    "<canonical element id>": <int>
  }
}
```

## conform_report.json

The conform pass over every programme in the cut list.

`conformed_programmes` and `void_programmes` are in ascending programme
identifier order, and together they account for every programme. `programmes`
carries one row for every programme, also ascending by programme identifier,
conformed and void alike.

A conformed row carries `state` `conformed` and has no `reason` field. A void
row carries `state` `void`, a `reason` list, a `conformed_frames` of zero, a
`shot_count` of zero and an empty `shots` list. A reason is written as one of
`unknown element`, `retired element`, `empty shot`, `shot leaves the usable
span`, `shot ordinals do not tile` or `no shots`, one string for each condition
the conform rulebook states, and a row lists every reason that applies to it in
ascending alphabetical order.

`shots` is in ascending shot ordinal order.

```
{
  "conformed_programmes": [<str>],
  "programmes": [
    {
      "conformed_frames": <int>,
      "programme_id": <str>,
      "reason": [<str>],
      "shot_count": <int>,
      "shots": [
        {
          "canonical_id": <str>,
          "element_after_last_frame": <int>,
          "element_first_frame": <int>,
          "frames": <int>,
          "shot_ordinal": <int>,
          "source_reel_id": <str>,
          "timeline_start": <int>,
          "timeline_stop": <int>,
          "transition": <str>
        }
      ],
      "state": <str>
    }
  ],
  "void_programmes": [<str>]
}
```

`element_first_frame` and `element_after_last_frame` are the shot's half open
span on the canonical element, and `timeline_start` and `timeline_stop` its
half open span on the programme timeline.

## defect_findings.json

The impairment pass. `defects` carries one row for every defect the log
records against a conformed programme and against one of that programme's
shots, in ascending defect identifier order. `impaired_frames` is keyed by
every conformed programme, ascending, and `impaired_total` is the sum of its
values.

```
{
  "defects": [
    {
      "clipped_frames": <int>,
      "defect_class": <str>,
      "defect_id": <str>,
      "detected_stage": <str>,
      "programme_id": <str>,
      "recovered_frames": <int>,
      "severity": <int>,
      "shot_ordinal": <int>,
      "timeline_start": <int>,
      "timeline_stop": <int>
    }
  ],
  "impaired_frames": {
    "<programme id>": <int>
  },
  "impaired_total": <int>
}
```

`timeline_start` and `timeline_stop` are the defect's span after it has been
clipped to the programme, and `clipped_frames` its length. Clipping moves each
end of the span into the host shot's own stretch of timeline: an end before the
shot begins is written as the shot's first frame, and an end past the shot is
written as the first frame after the shot. A defect that misses its host shot
altogether therefore keeps its row, with `timeline_start` and `timeline_stop`
equal and `clipped_frames` zero.

## repair_ledger.json

The repair pass. `repairs` carries one row for every repair the log records
against a defect that `defect_findings.json` carries a row for, ordered by
ascending pass index and then by ascending repair identifier. A repair worked
on a defect that was clipped to nothing is one of those rows, and it recovers
nothing.

A repair's `state` is written exactly one of `accepted`, `clamped`,
`node class below defect severity`, or `outside the repair window`.
`state_counts` is keyed by the outcomes that actually occur in the cycle,
ascending, and counts the repairs in each. `recovered_frames` is keyed by
every conformed programme, ascending, and `recovered_total` is the sum of its
values.

```
{
  "recovered_frames": {
    "<programme id>": <int>
  },
  "recovered_total": <int>,
  "repairs": [
    {
      "claimed_frames": <int>,
      "defect_id": <str>,
      "pass_index": <int>,
      "programme_id": <str>,
      "recovered_frames": <int>,
      "repair_id": <str>,
      "state": <str>
    }
  ],
  "state_counts": {
    "<repair outcome>": <int>
  }
}
```

## cadence_ledger.json

The settlement of every conformed programme. `programmes` carries one row per
conformed programme in ascending programme identifier order, and the three
totals are the sums of the matching row fields across those rows.

```
{
  "cadence_total": <int>,
  "programmes": [
    {
      "cadence_frames": <int>,
      "condition_grade": <str>,
      "delivery_cadence_mhz": <int>,
      "element_cadence_mhz": <int>,
      "governing_element": <str>,
      "impaired_frames": <int>,
      "programme_id": <str>,
      "recovered_frames": <int>,
      "settled_frames": <int>,
      "source_frames": <int>,
      "unrecovered_frames": <int>
    }
  ],
  "settled_total": <int>,
  "source_total": <int>
}
```

## allocation_ledger.json

The draw. `draw_order` carries one row for every conformed programme in the
draw order the allocation rulebook sets out, and each row's `state` is written
either `admitted` or `held`.

`admitted`, `held` and `drawing_holders` are in ascending identifier order,
not in draw order. `group_quota` and `group_used` are both keyed by every
settlement group the holder roll names, ascending, so a group that consumed
nothing still appears with a used figure of zero.

```
{
  "admitted": [<str>],
  "draw_order": [
    {
      "holder_id": <str>,
      "programme_id": <str>,
      "settled_frames": <int>,
      "settlement_group": <str>,
      "state": <str>
    }
  ],
  "drawing_holders": [<str>],
  "group_quota": {
    "<settlement group>": <int>
  },
  "group_used": {
    "<settlement group>": <int>
  },
  "held": [<str>]
}
```

## vault_index.json

The seating roll up. `vaults` carries one row for every vault the vault
charter opens, in ascending seat rank order. `seated_total_frames` is the sum
of the vault loads, and `residual_pool_frames` is the sum of the vault
headrooms.

```
{
  "residual_pool_frames": <int>,
  "seated_total_frames": <int>,
  "vaults": [
    {
      "capacity_frames": <int>,
      "headroom_frames": <int>,
      "load_frames": <int>,
      "programme_count": <int>,
      "seat_rank": <int>,
      "vault_id": <str>
    }
  ]
}
```

## One document per vault

A vault document is named for the vault it reports on. There is one for every
vault the vault charter opens, including a vault that seated nothing, whose
`programmes` is then an empty list.

`accepts_classes` and `settlement_groups` are in ascending order.
`programmes` is in descending settled frame order, ties broken by ascending
programme identifier. `headroom_frames` is the capacity less the load.

```
{
  "accepts_classes": [<str>],
  "capacity_frames": <int>,
  "headroom_frames": <int>,
  "load_frames": <int>,
  "programmes": [
    {
      "condition_grade": <str>,
      "deliverable_class": <str>,
      "holder_id": <str>,
      "programme_id": <str>,
      "settled_frames": <int>,
      "settlement_group": <str>,
      "title_key": <str>
    }
  ],
  "seat_rank": <int>,
  "settlement_groups": [<str>],
  "vault_id": <str>
}
```

A fully formed vault document from the published calibration cycle rides in
the catalogue beside this page.

## One document per lane

A lane document is named for the lane it reports on. There is one for every
lane the lane charter opens, including a lane that took nothing. It is the
vault document with `lane_id` in place of `vault_id` and `lane_rank` in place
of `seat_rank`, and its `capacity_frames` is the capacity that lane drew
against.

```
{
  "accepts_classes": [<str>],
  "capacity_frames": <int>,
  "headroom_frames": <int>,
  "lane_id": <str>,
  "lane_rank": <int>,
  "load_frames": <int>,
  "programmes": [
    {
      "condition_grade": <str>,
      "deliverable_class": <str>,
      "holder_id": <str>,
      "programme_id": <str>,
      "settled_frames": <int>,
      "settlement_group": <str>,
      "title_key": <str>
    }
  ],
  "settlement_groups": [<str>]
}
```

A shed programme appears in no lane document and in no vault document. It is
counted in the summary and nowhere else.

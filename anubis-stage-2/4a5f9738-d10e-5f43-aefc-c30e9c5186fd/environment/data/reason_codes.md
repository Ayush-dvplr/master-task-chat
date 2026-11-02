# Reason codes

A grant whose governing record is a retraction, or that carries a live
retraction notice, is withdrawn. A withdrawn grant is counted as retracted and
is not examined for faults. `retraction_notices.csv` carries notices with a
scope of `full` and later notices with a scope of `withdrawn` that cancel an
earlier notice of the same grant and notice date. A notice binds only when it
is visible under the cutoff.

Every remaining grant is tested against the reject codes below in the order
shown. The first code that matches is the only code recorded for that grant.

| order | code | meaning |
| --- | --- | --- |
| 1 | TERM_MISSING | the governing time group is absent or deferred |
| 2 | SPAN_INVERTED | the effective end precedes the effective start |
| 3 | UNIT_AMBIGUOUS | a governing frequency value cannot be converted exactly |
| 4 | BAND_OUTSIDE | the frequency span meets no usable channel |
| 5 | RASTER_MISALIGNED | a frequency bound is not a channel edge of its band |
| 6 | HOLDER_UNKNOWN | the resolved holder appears in no registry |
| 7 | ZONE_MISMATCH | a provisional holder is filed against another zone |
| 8 | PARENT_UNKNOWN | the parent is absent from the register or sits in another zone |
| 9 | PARENT_CYCLE | the parent chain returns to the grant |
| 10 | PARENT_RETRACTED | the parent is withdrawn or rejected |

A grant whose holder is filed against a zone other than the grant zone, and
whose holder status is `confirmed`, is not rejected. The difference is recorded
as a note instead.

Notes are counted but never remove a grant from the measure.

| note | meaning |
| --- | --- |
| ALIAS_RESOLVED | the holder reference moved through at least one redirection |
| CLIPPED_TO_BAND | a frequency bound was trimmed to a usable channel run |
| CLIPPED_TO_HORIZON | an effective bound was trimmed to the horizon |
| OPEN_ENDED | the effective end was absent and became the horizon end |
| WIDTH_MISMATCH | an explicit upper bound disagreed with the stated width |
| ZONE_OF_RECORD_DIFFERS | the holder is filed against another zone |
| SPLIT_BY_RASTER | the frequency span became more than one usable run |
| STATE_ANOMALY | a restore reached a grant that was already active |
| ZERO_SPAN | the effective bounds are equal |

A note is recorded only for a grant that passes every reject test. A note is
counted once for each grant it applies to, except STATE_ANOMALY which is
counted once for each ignored event.

# Glossary and field dictionary

## Terms

- **admitted position**: the one based index of a spot inside one break.
- **anchor**: the first received ingest attempt of an asset.
- **avail**: the commercial capacity published against one break.
- **break**: a conditioned splice point inside a transmitted slot.
- **broadcast day**: the day that opens at `06:00:00;00` and runs for
  `2589408` channel timecode frames.
- **canonical attempt**: the ingest attempt an asset is conformed from.
- **carry scope**: the named accumulator a conversion carries its discarded
  fraction into.
- **channel frame**: one frame at the channel rate of `30000/1001`.
- **clock hour**: one hour of channel timecode frames measured from the day
  start, which is `107892` frames.
- **daypart**: the commercial band a clock hour belongs to.
- **drop frame**: the timecode labelling that skips frame numbers.
- **grain**: the whole second unit a delivered spot is billed in.
- **index frame**: a channel frame the encoder marked as a splice point.
- **junction**: a scheduled slot start, fixed or floating.
- **make good**: an obligation raised against a deferred spot.
- **market**: one regional feed of the channel.
- **material duration**: the retained channel frames of a slot's parts.
- **minor unit**: the smallest indivisible unit of a currency.
- **slot**: one scheduled transmission of one asset.
- **substitute**: material carried in a market in place of a blacked out
  slot.

## Fields

### `ingest_attempt_register.csv`

- `ingest_id`: the identifier of one ingest attempt. Not an asset key.
- `content_ref`: the asset key. Several attempts share it.
- `title_code`, `version_tag`: the two components of the content reference.
- `revision_no`: the attempt's revision, a whole number.
- `qc_state`: one of `QC_PASSED`, `QC_PASSED_WITH_NOTES`, `QC_PENDING`,
  `QC_REJECTED`, `QC_WITHDRAWN`.
- `rate_code`: the key into `rate_code_register.csv`.
- `tc_mode`: `DF` or `NDF`, as the attempt claims it.
- `nominal_fps`: a rounded display label. Never a rate.
- `som_tc`, `eom_tc`: the start and the exclusive end of media. The
  separator before the frames is not evidence of drop frame (R40).
- `house_no`: the house number. Published from the anchor.
- `received_at`: when the attempt arrived, an ISO 8601 date and time with an
  explicit UTC offset. Orders the anchor by the instant it names (R43).

### `rate_code_register.csv`

- `rate_num`, `rate_den`: the exact editorial rate.
- `tc_base`: the whole frame numbers a second of timecode carries.
- `df_allowed`: whether drop frame labelling is permitted at that rate.
- `rounded_label`: the display label, matching `nominal_fps`.

### `segment_part_manifest.tsv`

- `part_no`: the transmission order of the part inside the asset.
- `part_kind`: one of `PT_BLACK`, `PT_BUMPER`, `PT_PROGRAMME`, `PT_PROMO`.
- `part_som_tc`, `part_eom_tc`: the part's own span, exclusive at the end,
  counted under the asset's drop frame flag (R40).

### `transmission_schedule.csv`

- `sched_start_tc`: the published channel timecode of the slot start,
  counted under the channel's drop frame behaviour (R40).
- `junction_kind`: `JK_FIXED` or `JK_FLOAT`.
- `flex_part_no`: the `part_no` of the slot's flexible tail element.
- `daypart_ref`: the slot's daypart.

### `break_plan_register.csv`

- `nominal_offset_seconds`: the break offset from the material start.
- `avail_seconds`: the commercial capacity of the break, in seconds.

### `gop_index_channel.psv`

- `idr_frame`: a channel frame the encoder marked, measured from the
  material start.

### `filler_library.csv`

- `predicate_order`: the order the filler predicates are walked in.
- `min_frames`, `max_frames`: the inclusive gap the filler covers.
- `stock_state`: one of `FS_AVAILABLE`, `FS_EMBARGOED`, `FS_EXPIRED`.

### `spot_order_book.jsonl`

- `break_ref`: the break the spot is sold against.
- `nominal_seconds`: the sold duration in whole seconds.
- `priority_band`: the admission band, lower is earlier.
- `separation_class`: the competitive grouping.
- `rate_card_ref`: the key into `rate_card_book.csv`.
- `clearance_ref`: the key into `clearance_state_journal.csv`.

### `rate_card_book.csv`

- `effective_from`: the calendar date the card takes effect, inclusive.
- `minor_per_grain`: the price of one billing grain in minor units.
- `card_revision`: the card's revision, a whole number (R39).

### `clearance_state_journal.csv`

- `journal_seq`: the sequence that settles the effective state, a whole
  number (R38).
- `logged_at`: backfilled, and not the ordering key.

### `blackout_rule_set.xml`

- `precedence`: ascending order of consideration.
- `override`: `yes` marks a rule that overturns everything before it.
- `window_from`, `window_to`: inclusive at both ends.

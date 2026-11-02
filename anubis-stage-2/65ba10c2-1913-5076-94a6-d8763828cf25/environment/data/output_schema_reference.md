OUTPUT SCHEMA REFERENCE
shift KP-2042-S23

Every published document is listed here with its exact header line,
its column order and its row order. A document that disagrees with
this paper in a header, a column order, a row order, a key name or a
value type is wrong however right its numbers are.

SECTION 1  ARTIFACT ORDER

This is the order the manifest digests the publication in.

  canonical_events.csv
  container_dimensions.csv
  vessel_obligation.csv
  initial_occupancy.psv
  event_order.csv
  cycle_break_report.json
  move_eligibility.csv
  yard_occupancy.psv
  movement_accounting.jsonl
  rehandle_ledger.jsonl
  yard_capacity.csv
  load_eligibility.csv
  ration_trace.jsonl
  terminal_reconciliation.csv
  publication_manifest.json
  rejected_moves.tsv
  rejection_reasons.csv
  accepted_moves.csv
  container_state_history.psv
  container_state_final.csv
  dependency_order.csv
  yard_reservations.psv
  block_utilization.csv
  equipment_usage.csv
  equipment_exceptions.tsv
  slot_accounting.csv
  vessel_cutoff_status.csv
  vessel_container_manifest.psv
  load_sequence_ledger.json
  deferred_containers.tsv
  departure_ledger.json
  vessel_reconciliation.xml
  exception_summary.tsv
  audit_trail.conf
  berth_report_bt_alder.json
  berth_report_bt_calder.json
  berth_report_bt_marlow.json
  daily_operational_summary.md
  final_control_totals.json

SECTION 2  THE SIX CORE DOCUMENTS

The core digest covers exactly these, in this order.

  canonical_events.csv
  move_eligibility.csv
  yard_occupancy.psv
  yard_capacity.csv
  load_eligibility.csv
  terminal_reconciliation.csv

The publication digest covers every other document of the
publication except the manifest itself, in the artifact order of
section 1.

SECTION 3  DELIMITED DOCUMENTS

  canonical_events.csv
    separator  comma
    header     event_key,order_id,box_id,source_system,source_priority,event_seq,raised_min,slot_code,cluster_tag
    row order  ascending event_key

  container_dimensions.csv
    separator  comma
    header     box_id,iso_length,teu_factor,box_class,vessel_id,mass_kg,mass_state
    row order  ascending box_id

  vessel_obligation.csv
    separator  comma
    header     vessel_id,voyage,berth_id,service_group,destination,voyage_sequence,applicable_revision
    row order  ascending vessel_id

  initial_occupancy.psv
    separator  pipe
    header     block_id|zone|rows|tiers_max|slot_capacity|opening_boxes|opening_free
    row order  ascending block_id

  event_order.csv
    separator  comma
    header     event_key,order_id,slot_code,source_priority,event_seq,box_id
    row order  ascending event_key

  move_eligibility.csv
    separator  comma
    header     event_key,order_id,box_id,slot_code,to_block,to_row,to_tier,outcome,reason_code
    row order  ascending event_key

  yard_occupancy.psv
    separator  pipe
    header     block_id|zone|slot_capacity|opening_boxes|closing_boxes|closing_free
    row order  ascending block_id

  yard_capacity.csv
    separator  comma
    header     block_id,slot_code,slot_capacity,occupied,reserved,unavailable,available
    row order  ascending block_id then ascending slot_code

  load_eligibility.csv
    separator  comma
    header     box_id,vessel_id,eligible,reason_code,ready_min
    row order  ascending box_id

  terminal_reconciliation.csv
    separator  comma
    header     measure,value
    row order  ascending measure

  rejected_moves.tsv
    separator  tab
    header     event_key	order_id	box_id	slot_code	reason_code
    row order  ascending event_key

  rejection_reasons.csv
    separator  comma
    header     reason_code,order_count
    row order  the rung order the admission ladder prints

  accepted_moves.csv
    separator  comma
    header     event_key,order_id,box_id,slot_code,to_block,to_row,to_tier
    row order  ascending event_key

  container_state_history.psv
    separator  pipe
    header     box_id|event_key|from_block|from_row|from_tier|to_block|to_row|to_tier|was_stacked
    row order  ascending event_key

  container_state_final.csv
    separator  comma
    header     box_id,block_id,row_no,tier_no,moves_applied,state
    row order  ascending box_id

  dependency_order.csv
    separator  comma
    header     position,order_id,event_key
    row order  ascending position

  yard_reservations.psv
    separator  pipe
    header     reservation_id|block_id|service_group|first_slot|last_slot|asked|withheld|consumed|unmet
    row order  ascending reservation_id

  block_utilization.csv
    separator  comma
    header     block_id,slot_capacity,closing_boxes,utilisation_ratio
    row order  ascending block_id

  equipment_usage.csv
    separator  comma
    header     equipment_id,equipment_class,allowance,used,minutes,within_allowance
    row order  ascending equipment_id

  equipment_exceptions.tsv
    separator  tab
    header     event_key	order_id	equipment_id	reason_code
    row order  ascending event_key

  slot_accounting.csv
    separator  comma
    header     slot_code,events,admitted,set_aside,confirmed
    row order  ascending slot_code, with the not supplied row last

  vessel_cutoff_status.csv
    separator  comma
    header     vessel_id,notice_id,cutoff_min,boxes_total,boxes_inside,boxes_outside
    row order  ascending vessel_id

  vessel_container_manifest.psv
    separator  pipe
    header     vessel_id|box_id|class_rank|stow_sequence|bay_no|teu_factor|mass_kg
    row order  ascending vessel_id then ascending box_id

  deferred_containers.tsv
    separator  tab
    header     vessel_id	box_id	load_minutes	assessed_cents	published_cents
    row order  ascending vessel_id then ascending box_id

  exception_summary.tsv
    separator  tab
    header     exception_kind	granted	withdrawn
    row order  ascending exception_kind

SECTION 4  LINE DELIMITED JSON DOCUMENTS

One object per line, keys in the order listed, no space after a
separator.

  movement_accounting.jsonl
    keys       event_key, order_id, box_id, planned_outcome, confirm_id, confirmed_min, movement_state
    row order  ascending event_key

  rehandle_ledger.jsonl
    keys       box_id, moves, rehandles, tier_depths, surcharge_cents, charge_cents
    row order  ascending box_id

  ration_trace.jsonl
    keys       slot_code, berth_id, pass_no, pool_minutes, unplaced_minutes, shares
    row order  ascending slot_code, then ascending berth_id, then ascending pass_no

  The shares value of ration_trace.jsonl is an array of objects
  carrying vessel_id and share_minutes, in ascending vessel_id.
  The tier_depths value of rehandle_ledger.jsonl is an array of
  integers in the order the rehandles happened.

  An order that no confirmation belongs to publishes confirm_id as
  the not supplied marker and confirmed_min as the whole number 0.
  The two absent fields take different forms on purpose: confirm_id
  is an identifier and carries the marker, confirmed_min is a whole
  quantity and carries a zero, the same form an absent mass takes at
  stage Y02.

SECTION 5  JSON DOCUMENTS

  cycle_break_report.json
    keys       shift_id, protection_depth, component_count, components
    component  component_key, member_count, members, edge_removed,
               edge_weight, before_order, after_order, protected_count
    order      the order the components were worked in

  load_sequence_ledger.json
    keys       shift_id, minutes_per_teu, stowage_keys, vessels
    stowage_keys  an array of the ordering key names the stowage
               directive issues, in its key position order
    vessel     vessel_id, share_minutes, eligible_count, loaded_count,
               deferred_count, loaded_minutes, unused_minutes
    order      ascending vessel_id

  departure_ledger.json
    keys       shift_id, vessels
    vessel     vessel_id, berth_id, share_minutes, loaded_minutes,
               unused_minutes, boxes
    box        load_position, box_id, load_minutes
    order      ascending vessel_id, boxes in ascending load_position

  berth_report_<berth_id>.json, one per reporting berth
    keys       shift_id, berth_id, vessel_count, vessels, pool_minutes,
               rationed_minutes, pairings
    pairing    slot_code, berth_id, pool_minutes, declared_minutes,
               crewed_minutes, vessel_count, rationed_minutes
    order      pairings in ascending slot_code
    vessels    an array of vessel_id strings, ascending, carrying
               every vessel whose applicable berth is this one
               whatever it rationed; vessel_count is its length
    minutes    pool_minutes and rationed_minutes at the head of the
               document are the sums of those figures over the
               pairings listed below them

  final_control_totals.json
    keys       shift_id, live_sheet_name, minutes_per_teu, totals,
               identities

  publication_manifest.json
    keys       shift_id, core_digest, publication_digest,
               document_count, documents
    document   name, sha256, bytes
    order      the artifact order of section 1

  document_count is the number of documents the publication carries,
  which is every name in the artifact order of section 1 and so
  counts the manifest itself. The documents array carries an entry
  for each of the others and never one for the manifest, so it holds
  one entry fewer than document_count.

SECTION 6  THE CONTROL MEASURES

terminal_reconciliation.csv publishes exactly these measures, and
final_control_totals.json carries the same set under totals.

  admitted_moves
  assessed_cents
  boxes_on_yard
  canonical_events
  confirmed_moves
  contradicted_moves
  deferred_boxes
  eligible_boxes
  equipment_exceptions
  loaded_boxes
  loaded_minutes
  loose_confirmations
  published_cents
  rationed_minutes
  rehandle_moves
  set_aside_moves

SECTION 7  THE IDENTITY CHECKS

vessel_reconciliation.xml and final_control_totals.json carry
exactly these four, each answering yes or no.

  loaded_and_deferred_partition_eligible
  moved_boxes_all_on_yard
  decision_count_matches_events
  republished_covers_deferred

SECTION 8  CLOSED VOCABULARIES

move_eligibility.csv outcome takes admitted or set_aside.
move_eligibility.csv reason_code takes the not supplied marker
or one of the rung codes the admission ladder prints.

load_eligibility.csv reason_code takes one of:

  EL_OK
  EL_NO_VESSEL
  EL_NO_OBLIGATION
  EL_HELD
  EL_OFF_YARD
  EL_NO_CUTOFF
  EL_AFTER_CUTOFF

movement_accounting.jsonl movement_state takes one of:

  confirmed
  aborted
  unconfirmed
  contradicted
  set_aside

equipment_exceptions.tsv reason_code takes one of:

  EQ_UNKNOWN_UNIT
  EQ_BEYOND_ALLOWANCE

container_state_final.csv state takes stacked or off_yard.
container_dimensions.csv mass_state takes declared or
not_declared.
container_state_history.psv was_stacked takes yes or no.
equipment_usage.csv within_allowance takes yes or no.
load_eligibility.csv eligible takes yes or no.

SECTION 9  THE TWO FREE FORM DOCUMENTS

audit_trail.conf carries, in this order, a shift section with
shift_id, live_sheet_name and reference; a counts section with
the control measures of section 6 in ascending measure name; a
ladder section with the rung codes in the order the admission
ladder prints them; and a movement section with the movement
states present, in ascending state name. A key line is written
as the key, one space, an equals sign, one space and the value.
A section header is written in square brackets and is preceded
by one empty line except at the head of the file, which opens
with one comment line.

daily_operational_summary.md opens with a level one heading, a
blank line, one line naming the shift and the reference and a
blank line. Then one bullet per control measure in ascending
measure name, written as a hyphen, one space, the measure name,
a colon, one space and the value. Then a blank line, a level two
heading reading Ladder, a blank line and one bullet per rung in
the printed rung order. Then a blank line, a level two heading
reading Identity checks, a blank line and one bullet per
identity check in the order of section 7.


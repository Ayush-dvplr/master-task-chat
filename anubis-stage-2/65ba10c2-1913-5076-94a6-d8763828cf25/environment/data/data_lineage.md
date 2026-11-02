DATA LINEAGE
shift KP-2042-S23

Which paper feeds which stage.

  box_master_register.csv               Y02
  mass_declaration_returns.psv          Y02
  stack_inventory_snapshot.csv          Y04
  block_geometry_register.csv           Y04
  slot_grid_calendar.csv                Y07 Y11
  hold_reservation_notices.jsonl        Y07 Y11
  yard_topology.xml                     Y04
  move_order_journal.csv                Y01
  withdrawn_order_journal.tsv           Y01
  source_priority_register.csv          Y05
  move_dependency_declarations.jsonl    Y06
  crane_confirmation_feed.ndjson        Y09 Y10
  handling_equipment_register.csv       Y10 Y13
  vessel_call_register.csv              Y03
  cutoff_notice_board.tsv               Y12
  stowage_obligation_list.psv           Y12 Y13
  berth_window_register.csv             Y13
  quay_demand_returns.csv               Y13
  operational_exception_notices.csv     Y07 Y12 Y14
  quay_capacity_workbook.xlsx           Y02 Y10 Y13
  berth_operations_memo.pdf             Y06 Y10 Y13
  stowage_ordering_directive.docx       Y13

These papers govern nothing. They are kept because the shift office
keeps them, and no published quantity is taken from any of them.

  box_class_supplement.csv              a working note. Where it
                                        disagrees with the master
                                        register the master register
                                        stands.
  legacy_tariff_extract.csv             the tariff this terminal
                                        stopped using. The base move
                                        charge comes from the live
                                        workbook sheet.
  shift_office_audit.db                 a copy of the move journal
                                        and the box register.
  quay_gang_roster inside the memo      feeds the pool at Y13, so the
                                        memo is not a decoy.

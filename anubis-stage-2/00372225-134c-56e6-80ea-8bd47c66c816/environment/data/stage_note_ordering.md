# Ordering

Exclude every reading whose is_qc_fail is set before doing anything else. Order the surviving readings by settle_slot ascending, then draw_slot ascending, then by reading_id descending. The descending id tiebreak decides channel carry order and admission order.

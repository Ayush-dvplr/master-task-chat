# Batching

Every surviving reading belongs to one batch, chosen by its settle_slot. A batch in the calendar covers the slots from its from_slot up to but not including its to_slot. A batch is eligible only when its min_lot is less than or equal to the effective lot, so a batch asking for a higher lot than the run carries is skipped. When more than one eligible batch covers the same slot, the one appearing last in the calendar wins. A reading that no eligible batch covers takes no part in admission and adds nothing to any total, but it keeps its place in the processing order.

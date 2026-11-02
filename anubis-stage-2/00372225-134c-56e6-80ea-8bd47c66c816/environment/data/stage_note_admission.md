# Admission

Convert the reweighted value to a whole result and add any carry standing on the channel. Admit up to the remaining per-batch cap headroom. Any excess spills forward as carry on the same channel to the next admitted reading. A whole result that comes out below zero is admitted as it stands: it spills nothing and lowers the running admitted mass of its batch. The batch cap is a governance constant.

Raise the admitted whole result to at least the governance floor result, then add the matrix shift that the panel topology gives for that analyte, then hold the seated figure at zero whenever it would come out below zero. The shift is a whole-unit offset and is never scaled. Add the seated figure to the committed total for that analyte and batch.

Carry can still be standing on a channel once every reading has been admitted. Take the channels in name order and add what is left on each one to the analyte and batch of the first reading that channel admitted, where a reading counts as admitted once a batch covers it, even when the cap left it no units. This late addition is not bounded by the batch cap.

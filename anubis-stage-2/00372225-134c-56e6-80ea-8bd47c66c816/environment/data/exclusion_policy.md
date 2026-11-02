# QC-fail exclusion

A reading whose is_qc_fail column is set is excluded from the run entirely before ordering, admission, and every rollup. Excluded readings are not out-of-batch drops; they never enter the pipeline.

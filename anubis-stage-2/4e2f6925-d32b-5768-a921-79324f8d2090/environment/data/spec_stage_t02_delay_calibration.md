# T02 delay calibration

## Input

delay_calibration_ledger.csv and delay_calibration_supplement.psv. The
supplement does not replace the ledger. Both are reports of the same
calibration register, and the report set of a link is the union of what the
two papers hold for it.

## Selecting the applicable report

A report governs a reading when its effective_epoch_s is on or before the
acq_time_s of that reading. Among the reports that govern a reading, the
applicable one is the one with the greatest effective_epoch_s.

Two reports can carry the same effective_epoch_s. When that happens the report
with the smaller revision number is the applicable one. The register issues a
signed report first and registers its provisional restatement afterwards under
the next revision, so the smaller revision is the settled reading and the
larger one is the restatement the desk has not adopted.

The status of a report records how far it has been through review. It takes no
part in selecting the applicable report; effective epoch and revision select
it, and a report is on the register because the desk put it there.

issued_epoch_s records when a report reached the desk. It orders nothing. A
report issued later can take effect earlier, and a report issued last can take
effect after the interval closes and govern no reading in it.

A link whose reports all take effect after the reading has no applicable
report. Its correction is zero, its report is recorded as REPORT_NONE and its
status is recorded as CAL_ABSENT.

## Applying the correction

The ledger publishes delay_a_ns and delay_b_ns in nanoseconds. Every reading
is in picoseconds. The correction is

    correction_ps = (delay_a_ns - delay_b_ns) * 1000

and the corrected reading is

    corrected_ps = raw_offset_ps - correction_ps

## Output

For every canonical reading, the applicable report, its revision, its status,
its effective epoch, the correction in picoseconds and the corrected reading.

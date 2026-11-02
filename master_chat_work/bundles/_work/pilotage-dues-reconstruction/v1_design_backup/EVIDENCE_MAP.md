# EVIDENCE_MAP 44635de pilotage-dues-reconstruction (v2, 26 Oct 22:08)

File:line refers to `environment/data/` as refreshed in `WORK/design_blind/environment/data/` (shipped
seed 482617). Test ids follow DESIGN.md section 12 (hidden corpora c1..c4).

| rule | test ids | shipped fact file:line | wrong readings it contradicts |
|---|---|---|---|
| LV-1 joint fit | hidden_audit_plain_ck, hidden_regions_ck (k=1..4), hidden_summary_c1, hidden_segments_c2 | tariff_circular.md:83-90 (each coefficient one listed value per period; a coefficient the notice does not name has the same value in both periods; reproduces every accepted paid invoice of the station with the values of its own period; combination of a period); :103 (`cannot_recompute` conditions); :105-107 (reason strings) | first fit in list order; fit each period alone; carry the before-period values forward; best fit by count of matching invoices |
| LV-1 candidate space | same as LV-1 | tariff_circular.md:64-73 (four closed lists) | free-valued regression; values outside the lists |
| LV-2 notice periods | hidden_audit_plain_ck, hidden_regions_ck, hidden_summary_c1 | station_notices.md:5-7 (notice row names its coefficients); tariff_circular.md:23 (instant is the boarding instant), :75-81 (new period at 00:00 on the notice date; a visit belongs to the period that holds its instant) | period by invoice_date; period by release instant; notice date kept in the old period |
| LV-3 certificate allowance | hidden_audit_plain_ck, hidden_regions_ck, hidden_segments_c2 | exemption_policy.md:22-23 (covers time before 00:00 on expiry, up to allowance_minutes in total), :25-26 (covered = minutes before expiry or allowance left); tariff_circular.md:51-62 (billed minutes and per-line pro-rating) | allowance ignored; allowance per vessel; expiry date itself covered; summed due pro-rated once |
| LV-3 draw order | hidden_audit_plain_ck (tie and cap plants), hidden_segments_c2 | exemption_policy.md:23-24 ("Visits draw on the allowance in the order of their instants, the lower visit id first on a tie."), :24-25 ("Every visit of those vessels draws, whether invoiced or not and at whichever station.") | order of log lines; order of invoice ids; only invoiced visits draw; only visits at the invoice's station draw |
| Q1 assist | quiet_Q1 | tariff_circular.md:11 (optional ` assist=<integer>`), :34 (40.00 per started 30 minutes), :39-41 (toy) | suffix rejected as malformed; per full 30 minutes; assist inside the surcharge base |
| Q2 draft_m | quiet_Q2 | tariff_circular.md:17-19 (rounded up to the next 0.1 m, toy) | line rejected; round half; truncate |
| Q3 Sunday holiday | quiet_Q3 | tariff_circular.md:46-47 (kept on the Monday after, toy) | Sunday only |
| Q4 cancelled booking | quiet_Q4 | tariff_circular.md:13-14, :62; station_notices.md:18-19 (due = call_out_fee, no other line) | CANCEL rejected; invoice unknown_visit; surcharge or minimum added |
| Q5 minimum due | quiet_Q5 | station_notices.md:13-16 (table), :19-20 (raised to minimum_due) | minimum ignored; minimum applied before pro-rating or to public visits |
| Q6 re-measured vessel | quiet_Q6 | exemption_policy.md:11-15 (row in force = latest measured_from on or before the instant's date, toy) | first row always; last row always; second row rejected as duplicate |
| Q7 public without certificate | quiet_Q7 | exemption_policy.md:28, :31-32 (toy) | row rejected; whole visit covered |
| Q8 superseded | quiet_Q8 | output_contract.md:30-37 (left out of every output, toy) | both invoices judged; superseder dropped |
| Q9 cents billed | quiet_Q9 | tariff_circular.md:96 (`705c` is 7.05) | row rejected as malformed; read as whole currency |
| Q10 `all` holidays | quiet_Q10 | tariff_circular.md:44-48 (key `all`, toy) | key read as a station; key ignored |
| N1 early_invoice | shipped_quality, hidden_quality_ck | output_contract.md:24 | dated before release; not rejected |
| N2 already_paid | shipped_quality, hidden_quality_ck | output_contract.md:25 | disputed invoice judged; paid invoice rejected instead |
| N3 segment vessels | shipped_segments, hidden_segments_c2 | output_contract.md:82 | count of invoices; vessels across segments |
| N4 largest_refund | shipped_summary, hidden_summary_c1 | output_contract.md:62 | higher id on a tie; largest shortfall |
| R7-R9 surcharge | shipped_audit, hidden_audit_plain_ck | tariff_circular.md:36 | surcharge on unrounded lines; two surcharges on a night holiday |
| R20-R23 rejects | shipped_quality, hidden_quality_ck | output_contract.md:13-28 | keep first copy of a duplicate; mismatch before unknown |
| R25 fatal | mutation_missing_source | output_contract.md:39-44 | skip the missing file and write partial outputs |
| Risk 1 cancelled booking and minimum_due | quiet_Q4, quiet_Q5 | station_notices.md:18-19 ("the minimum_due does not apply to it"); every call_out_fee is above every minimum_due in every corpus (generator assert) | apply the minimum to a cancelled booking (same due either way, so no corpus separates the readings) |
| Risk 2 rejected record of a superseded invoice | quiet_Q8, hidden_quality_ck | output_contract.md:34-36 ("left out of `data_quality.json` too, whatever its code"); generator asserts each superseded id is on exactly one disputed line, so no corpus holds the case | keep the rejected record in data_quality.json |
| Risk 3 one visit id on BOARD and CANCEL, two accepted BOARD lines | quiet_Q4, hidden_audit_plain_ck | tariff_circular.md:23-24 (at most one accepted BOARD or CANCEL line, never both); generator asserts one accepted BOARD/CANCEL and one accepted RELEASE per id; a repeated BOARD id appears only beside a malformed copy | let CANCEL win over BOARD, or keep the last BOARD line |

## Lessons for the master
- Quote the line range of each sentence the test leans on, not the section | no change: already W2
- A stated draw order needs its own row, since tie plants are the only evidence of it | no change: master change 1 already asks for it

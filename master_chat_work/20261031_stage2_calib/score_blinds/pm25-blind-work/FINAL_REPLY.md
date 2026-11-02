I built `/app/out/derive_report.py` (copy also in `app/`). Run it as `python3 derive_report.py DATA_DIR OUT_DIR`. It uses only the standard library, opens DATA_DIR read-only, and writes **9 reports**: summary, policy_audit, data_quality, region_North/South/West/East and segment_commercial/public. It prints one `name bytes` line per report. On the shipped extract it takes 0.17 s.

**Shipped extract:** 19484 card rows, split into 2223 excluded readings and 17261 valid readings. 17261 readings are rolled up and the residual is 0. There are 4305 valid hours and 183 valid days. Three sites are in attainment (S1, S3, S4) and three are in nonattainment (S2, S5, S6). The highest design value is S6 at 477 tenths.

**What-if answers**
1. 7976
2. 5544
3. 0
4. 2839
5. 1.187
6. 351
7. 5594
8. 6095
9. 34458
10. 4307

How I got them: each what-if is a full rerun on its own changed copy of the extract.

**Checks run and what each covered**
- **Shipped run:** 1 extract, 19484 card rows and 16093 journal rows. All 9 reports exist, and the stdout byte counts match the file sizes.
- **Reconciliation:** 1 extract, 19484 rows. Excluded 2223 plus valid 17261 equals 19484, and the rollups give a residual of 0.
- **Read-only check:** 1 data directory of 15 files. The sha1 hashes were the same before and after the run.
- **Determinism:** 2 extra runs, one on the shipped extract from a different working directory and one on a copy of the extract. All 9 reports from both runs were byte-identical to the shipped output.
- **What-ifs:** 210 full-report runs, 1 base run and 209 changed extracts, each with 19484 card rows. What-if 5 alone was 201 copies, scanning the factor from 1.100 to 1.300 in steps of 0.001. S4 is in attainment up to 1.187 and in nonattainment from 1.188.

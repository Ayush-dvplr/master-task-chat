The directory `/app/data` holds one billing period extract from a multi-region SQL query fleet, together with the documents that define how the fleet is metered and billed. The documents shipped with the data govern this work.

Deliver a program at `/app/out/transform.py` that meters an extract and writes its thirteen reports. It runs as `python3 /app/out/transform.py DATA_DIR OUT_DIR` and is self-contained: only it and its reports are collected from `/app/out`. Run it on the shipped extract, so that `/app/out` holds the program and its reports when you finish: `/app/out/normalized.jsonl`, `/app/out/summary.json`, `/app/out/data_quality.json`, `/app/out/product_summary.json`, `/app/out/region_central.json`, `/app/out/region_east.json`, `/app/out/region_north.json`, `/app/out/region_south.json`, `/app/out/region_west.json`, `/app/out/segment_consumer.json`, `/app/out/segment_corporate.json`, `/app/out/segment_enterprise.json` and `/app/out/segment_smb.json`.

It will also be run on other extracts in the same layout, so nothing in it may depend on this particular billing period. Each call finishes within 60 seconds. The program must leave DATA_DIR untouched, read nothing outside DATA_DIR and its own directory, and write nothing outside OUT_DIR. Its reports must be byte-identical across runs, working directories, extract locations and output directories. Every report must match exactly, byte for byte. Use only the Python standard library. Leave the shipped extract in `/app/data` unchanged.

Your final message answers the six questions below. Each what-if is worked out by rerunning the whole metering with exactly the change named, on a copy of the extract. Each changed extract is an extract in this layout in its own right.

1. In a copy where the row of query `q-2549985` in `queries.csv` has `duration_ms` 217843 and the row of query `q-0386103` has `duration_ms` 285337, what are the `charge_micros` of `q-2549985`, `q-0386103` and `q-1485251`?

2. In a copy where the row of query `q-6138339` in `queries.csv` has `duration_ms` 121209 and `scanned_bytes` 55733911552, what are the `charge_micros` of `q-6138339` and of `q-2068952`?

3. Start from the copy of question 1 and append one line to `corrections.jsonl`: a `void` with `correction_id` `c-ffff0` and `recorded_at` `2026-02-10T00:00:00.000Z`, naming whichever of the three queries of question 1 has the largest `charge_micros` there. Which query is voided, what are the `charge_micros` of the other two, and what is their sum?

4. In a copy where `tenant_merges.csv` has one more row, absorbing `tn-77fb` into `tn-5fef` with `effective_at` `2026-02-04T00:00:00.000Z`, and where the row of query `q-1637487` in `queries.csv` has `duration_ms` 71874, what are the `free_bytes` and the `charge_micros` of `q-1637487`?

5. Start from the copy of question 4. For each whole number k from 1 to 60, set the `daily_free_bytes` of the latest `PL-STARTER` version in `plans.json` to k times 1073741824. For how many of these 60 values of k does `q-1637487` receive zero free bytes?

6. Start from the copy of question 1. Over the whole numbers k from 1 to 1024, with the `daily_free_bytes` of the latest `PL-BUSINESS` version in `plans.json` set to k times 1073741824, what is the smallest k at which `q-0386103` receives more than zero free bytes?

In the same message, state the number of reports your program writes for one extract, and for every check you ran on your program, the number of extracts it covered and the number of ledger lines it compared.

You have 7200 seconds to complete this task. Do not use online solutions or hints specific to this task.

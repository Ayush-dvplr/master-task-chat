# EVIDENCE_MAP sensor-network-lsq-correlated-adjustment (R0 868afdf, 2 Nov)

Each graded lever rule, the sentence that states it, and the shipped record the right reading is checked against (LEVER_RULES_v2 0b). Every rule below has its own sentence in schema.md; the shipped fact column names the file the sentence governs.

| rule | sentence | shipped fact file:line | wrong readings it contradicts |
|---|---|---|---|
| Q1 CSV shard fields are RFC 4180 fields; quotes are not part of the value | `environment/data/schema.md:38-39` | `environment/data/obs_source_district_north.csv:6` (the CSV shard the sentence governs; header row read by a CSV reader) | plain delimiter split keeping the quotes: `"stddev"` takes the variance branch, `"R"` is not reversed (witness WORK/r0_lever/witness/data_sk, OB00001 -17025 vs -16912) |
| A traverse closure, second sharing without the fits test | `environment/data/schema.md:113-131` | `environment/data/traverse_closure_register.csv:4` (East epoch 1 closure 28602, floor 215) | second sharing re-entering the fits test (eval_traverse_closure_rows_hard) |
| B centring variance follows set_out_from to its end | `environment/data/schema.md:19-23` | `environment/data/station_registry.csv:10` (BRAVO set out from CM03) | one level only (challenge_centring_chain_rows_hard) |
| C district is the district of the kept record's shard | `environment/data/schema.md:54-58` | `environment/data/obs_source_district_north.csv:2` (revision=3 header token) | district from the line region field (audit_district_rows_hard) |

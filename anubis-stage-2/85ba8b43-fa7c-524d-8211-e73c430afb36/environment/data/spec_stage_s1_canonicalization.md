# S1 Match Canonicalization

The economic match key is `account_id | hero_handle | seed_hash | ladder_split`
built from `ladder_match_capture_s1.csv`. The `match_uid` is minted once per attempt and MUST
NOT be used as the key. For each key, keep exactly one canonical row: the row
with the highest `checkpoint_no` among rows whose `seal_status` is `SEALED`. A
key with no `SEALED` attempt never sealed and is dropped from the population
entirely (it is not a surviving OPEN row).

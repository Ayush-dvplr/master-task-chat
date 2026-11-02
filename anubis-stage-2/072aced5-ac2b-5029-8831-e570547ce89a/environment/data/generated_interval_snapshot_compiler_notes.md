# generated interval snapshot compile pass

The compile pass that produced `generated_interval_snapshot.json` runs in five steps.

1. Read every record of `keyframe_interval_ledger.jsonl` in ascending `seq` order and keep only the
   records whose `seq` is at or below the snapshot cut, which is recorded in the
   snapshot header as `compiled_from_seq`.
2. Discard records whose `effective_generation` is above the snapshot
   generation recorded in the same header.
3. For each render track, keep the surviving record with the highest `seq`.
4. If the kept record carries a `reference_domain` of `decode_order_index`, look the value up
   in `decode_order_map.json` using the recorded value as `alt_key` and the active lineage
   anchor of that render track as `lineage_anchor`, and emit the `canonical_value` of
   the matching row.
5. Emit one snapshot entry per render track, with retired render tracks marked retired.

The pass writes no diagnostics of its own. Any discrepancy between a snapshot
entry and the authority record that produced it is visible only by comparing the
two directly.

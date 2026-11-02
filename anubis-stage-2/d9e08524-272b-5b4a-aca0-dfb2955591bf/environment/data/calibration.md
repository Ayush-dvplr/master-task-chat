# Calibration slice

The calibration shards, tier marker 1, are a held out rehearsal population that never enters any lock
plan. Six registry constants are withheld from every document in this directory. Exactly one
assignment of the six, drawn from the candidate lists below, reproduces every control figure.

## Candidate lists

| constant | candidates |
| --- | --- |
| salt word | ALDER BIRCH CEDAR ELDER FIR HAZEL LARCH MAPLE ROWAN SPRUCE |
| window span | 2 3 4 5 6 7 8 10 12 16 |
| bias limit | 3 5 7 11 13 17 19 23 29 31 |
| rotation base | 1 2 3 4 5 6 7 9 11 13 |
| shuffle multiplier | 0x2545f491 0x27220a95 0x9e3779b1 0x85ebca77 0xc2b2ae3d 0x1b873593 0xcc9e2d51 0x6d2b79f5 0x7feb352d 0x846ca68b |
| quarantine days | 0 1 2 3 5 7 10 14 21 30 |

The quarantine days constant is the one the resolution policy uses.

Calibration snapshot day: 2100

## Control figures

| control | figure | value |
| --- | --- | --- |
| CTRL-1 | calibration_block_total | 17 |
| CTRL-2 | calibration_key_digest | 909967 |
| CTRL-3 | calibration_size_digest | 531261 |
| CTRL-4 | calibration_dependency_digest | 70029 |
| CTRL-5 | calibration_status_digest | 1163 |
| CTRL-6 | calibration_eligible_records | 69 |

Figure notes, in the same order. Positions and ordinals below are one based, blocks are taken in
logical order, and every value is the true value the shard writer received.

- CTRL-1: blocks counted across every calibration shard.
- CTRL-2: every package key multiplied by the position of its block inside its shard, summed, modulo 1000003.
- CTRL-3: for every record, the artifact bytes value plus the version code, multiplied by the ordinal of the record, summed, modulo 1000003.
- CTRL-4: for every dependency entry, the target key combined by exclusive or with the lowest version code, plus seven times the requested feature mask, plus the gate, multiplied by the position of the entry inside its record and by the ordinal of the record, summed, modulo 1000003.
- CTRL-5: for every record, three times the status byte plus the dependency entry count, multiplied by the ordinal of the record, summed, modulo 1000003.
- CTRL-6: records that are not yanked, are published on or before the calibration snapshot day, and are published at least the quarantine days before it.

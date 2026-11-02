# Rehearsal decodes

The rehearsal shards carry tier marker 0 and a flag word of zero, so no optional transform touches
their bytes. Every block they carry is listed below in file order so that a plain reader can be
confirmed before any transform is considered. Their package keys belong to no registered name.

## sample_a.pidx

Shard nonce 4014059778, 2 blocks.

Block 0: package key 43520af5, block nonce 4150325023.

| version | artifact bytes | publish day | status | dependency entries |
| --- | --- | --- | --- | --- |
| 3.1.3 | 29862 | 2117 | 1 | 68947e7c 2.5.0..3.5.0 mask 6 always; 25a31cbf 0.2.0..1.2.0 mask 6 bit 1 |
| 3.1.5 | 81579 | 1959 | 0 | 68947e7c 2.5.0..3.5.0 mask 6 always |
| 3.2.5 | 74615 | 2014 | 0 | 25a31cbf 0.2.0..1.2.0 mask 6 bit 1; 25a31cbf 0.2.0..1.2.0 mask 6 bit 1; 58e0ae4c 2.8.0..3.8.0 mask 7 bit 1 |

Block 1: package key 33424fbe, block nonce 1127026479.

| version | artifact bytes | publish day | status | dependency entries |
| --- | --- | --- | --- | --- |
| 2.1.3 | 46836 | 1957 | 0 | 578d8ed5 2.1.0..3.1.0 mask 11 bit 1; 4dfdb01a 3.9.0..4.9.0 mask 11 always |
| 2.2.3 | 74713 | 2035 | 0 | 60a1da13 2.2.0..3.2.0 mask 3 always |
| 2.3.3 | 56579 | 2113 | 0 | 578d8ed5 2.1.0..3.1.0 mask 11 bit 1; 4dfdb01a 3.9.0..4.9.0 mask 11 always; 578d8ed5 2.1.0..3.1.0 mask 11 bit 1 |

## sample_b.pidx

Shard nonce 435776986, 2 blocks.

Block 0: package key 67ca61bd, block nonce 2613175405.

| version | artifact bytes | publish day | status | dependency entries |
| --- | --- | --- | --- | --- |
| 1.0.3 | 10256 | 1840 | 0 | 26f64eca 3.3.0..4.3.0 mask 7 bit 2; 698bd551 2.9.0..3.9.0 mask 11 always |
| 1.0.6 | 15751 | 1824 | 0 | 26aacf40 0.7.0..1.7.0 mask 15 bit 1; 26aacf40 0.7.0..1.7.0 mask 15 bit 1; 26aacf40 0.7.0..1.7.0 mask 15 bit 1 |
| 1.0.8 | 75336 | 1896 | 0 | 26f64eca 3.3.0..4.3.0 mask 7 bit 2 |

Block 1: package key 6f867926, block nonce 1128425259.

| version | artifact bytes | publish day | status | dependency entries |
| --- | --- | --- | --- | --- |
| 2.4.1 | 56005 | 1983 | 0 | 4033e295 1.5.0..2.5.0 mask 4 bit 1; 6ba17f71 3.2.0..4.2.0 mask 1 bit 1 |
| 2.4.2 | 35770 | 2036 | 0 | 4033e295 1.5.0..2.5.0 mask 4 bit 1 |
| 2.4.5 | 48949 | 1936 | 0 | 4e8c12de 4.7.0..5.7.0 mask 7 always; 6f353da9 0.3.0..1.3.0 mask 9 bit 2 |

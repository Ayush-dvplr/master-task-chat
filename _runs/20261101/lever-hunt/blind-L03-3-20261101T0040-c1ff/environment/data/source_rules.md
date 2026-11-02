# Source rules: choosing one result per sample and assay

A sample may be analysed by more than one laboratory, so several valid
transmissions can carry a result for the same `(sample_id, assay)`. Exactly one
is accepted; the others are superseded. Rejected transmissions (see the
contract) never compete.

## Lab priority

| lab | name | priority tier |
|-----|------|---------------|
| NRL | National Reference Laboratory | 1 (highest) |
| ACM | Acme Analytical | 2 |
| BLX | Bluecross Labs | 2 |
| FSK | Firth Screening | 3 |

The transmission from the highest-priority tier (lowest number) is accepted,
regardless of when it was reported or what value it carries.

## Tie-break inside a tier

When the best tier holds more than one transmission for the key, the one with
the latest `reported_at` is accepted (it is the lab's final word on the
sample). No other field breaks ties.

Worked example from the shipped corpus, sample `CS268129`, assay `HG`:

| transmission_id | lab | result | reported_at |
|-----------------|-----|--------|-------------|
| T63530 | ACM | 0.142 | 2026-02-01T12:00:00Z |
| T67576 | BLX | 0.115 | 2026-02-04T12:08:00Z |

Both labs are tier 2, so `T67576` (reported later) is accepted with result
0.115 and `T63530` is superseded.

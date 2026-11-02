# Tape index layout

Tier: contract.

`tape_index_v1.txt` and `tape_index_v2.txt` are fixed width records written by the tape room terminal. Each line is one record of sixty nine characters with no separator between fields. Neither file carries a header line.

## Field positions

Positions are one based and inclusive.

| field | positions | width | alignment | content |
| --- | --- | --- | --- | --- |
| tape_key | 1 to 12 | 12 | left, space padded | the tape key, matching field twenty of an event row |
| source_in_tc | 13 to 23 | 11 | fixed | the in timecode |
| source_out_tc | 24 to 34 | 11 | fixed | the out timecode |
| speed_ppb | 35 to 45 | 11 | right, space padded | the speed in parts per billion |
| revision | 46 to 49 | 4 | right, space padded | the tape room revision of the record |
| recorded_at | 50 to 69 | 20 | fixed | the instant the tape room wrote the record |

A sample record reads

```
TK00000001  01:00:00:0001:00:02:00  997000000   12024-02-10T00:00:00Z
```

which carries tape key `TK00000001`, in timecode `01:00:00:00`, out timecode `01:00:02:00`, speed 997000000 parts per billion, revision 1 and recorded instant `2024-02-10T00:00:00Z`.

## Reading the fields

The tape key field is padded on the right with spaces and the padding is not part of the key.

The two timecode fields are written in the form `timecode_spec.md` defines and occupy their eleven positions exactly.

The speed field is a whole number of parts per billion and is always a whole multiple of one thousand. One billion parts per billion is unity.

The revision field is the tape room revision and bears on nothing in the conform contract. It is unrelated to the revision field of the event row and to the revision field of a correction record.

The recorded instant field is the instant the tape room wrote the record and bears on nothing in the conform contract.

## Coverage

`tape_index_v2.txt` is a partial rewrite of the tape index and carries records for a subset of the keys. `tape_index_v1.txt` carries records for every key the tape room ever measured. Which file counts for a key is settled in `provenance_spec.md`.

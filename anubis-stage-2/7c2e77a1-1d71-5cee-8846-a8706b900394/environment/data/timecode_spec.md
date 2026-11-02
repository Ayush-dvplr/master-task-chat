# Timecode specification

Tier: contract.

This document defines the conversion between a written timecode and a frame count. The conform contract in `conform_contract.md` uses this conversion wherever it reads a timecode.

## Written form

A timecode is written as four two digit groups separated by colons, in the order hours, minutes, seconds, frames. The string `01:00:02:14` names hour one, minute zero, second two, frame fourteen. No other written form occurs in this folder.

## Rate family fields

`rate_families.csv` supplies four numbers for each rate family. The frame rate numerator and the frame rate denominator together give the true frame rate of the family. The nominal frame rate is the whole number of frames a timecode second of the family carries. The drop frame flag states whether the family numbers its frames under the drop frame convention.

The seven families in this folder are as follows.

| rate family | numerator | denominator | nominal frame rate | drop frame |
| --- | --- | --- | --- | --- |
| F2398 | 24000 | 1001 | 24 | false |
| F24 | 24 | 1 | 24 | false |
| F25 | 25 | 1 | 25 | false |
| F2997D | 30000 | 1001 | 30 | true |
| F30 | 30 | 1 | 30 | false |
| F50 | 50 | 1 | 50 | false |
| F5994 | 60000 | 1001 | 60 | false |

## Conversion

Write `hh`, `mm`, `ss` and `ff` for the four groups of a timecode and `nominal` for the nominal frame rate of its rate family.

The frame count of a timecode whose rate family does not carry the drop frame flag is

```
((hh * 60 + mm) * 60 + ss) * nominal + ff
```

The frame count of a timecode whose rate family carries the drop frame flag is that same quantity reduced by

```
2 * (total_minutes - total_minutes // 10)
```

where `total_minutes` is `hh * 60 + mm` and the two slashes mark whole number division. The timecode `01:00:00:00` of family F2997D therefore has frame count 107892, and the timecode `00:10:00:00` of family F2997D has frame count 17982.

## Frame counts in artifacts

Every frame count the conform contract names is a whole number of frames in the counting of the family that produced it. Artifacts carry frame counts as numbers, never as written timecodes.

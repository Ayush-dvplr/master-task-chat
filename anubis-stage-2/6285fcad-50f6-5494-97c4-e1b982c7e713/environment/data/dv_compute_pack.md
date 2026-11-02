# Saved daily-values compute pack (P26Q2)

This pack produced the published daily values, statistics and shift worksheet of batch P26Q2. It is kept as the record
of how the published batch was run.

## Run settings

| setting | value |
|---|---|
| rating_sheet | Ratings_2025 |
| tolerance_table | T-1 |
| errata | none |
| measurement_gage_height | field_sheet |
| deviation_basis | base_rating |
| daily_method | rating_of_mean_stage |
| day_basis | utc |
| gage_height_corrections | none |
| edits_journal | file_order |

## Steps

1. Read every csv, tsv, psv, json, jsonl, ndjson, xml, txt and yaml file of the directory as a shard.
2. Keep the newest revision of each reading.
3. Convert metres with 3.2808 ft per metre.
4. Evaluate the rating sheet Ratings_2025 for the daily mean gage height of each UTC day.
5. Take the gage height of each measurement from the field sheet.
6. Compare each measurement with the base rating and shift when it deviates beyond Table T-1.
7. Apply the unit-value edits in file order.
8. Report monthly volumes with 1.9835 acre-feet per cfs-day.

## Run log

- 001 meas 4182 site 03203376 decision ICE shift -
- 002 meas 4186 site 03203376 decision ICE shift -
- 003 meas 4188 site 03203376 decision ICE shift -
- 004 meas 4191 site 03203376 decision ICE shift -
- 005 meas 4195 site 03203376 decision ICE shift -
- 006 meas 4197 site 03203376 decision CHECK shift -
- 007 meas 4198 site 03203376 decision REJECTED shift -
- 008 meas 4200 site 03203376 decision CHECK shift -
- 009 meas 4202 site 03689879 decision SHIFT shift 0.19
- 010 meas 4203 site 03689879 decision SHIFT shift 0.16
- 011 meas 4206 site 03689879 decision CHECK shift -
- 012 meas 4209 site 03689879 decision SHIFT shift 0.08
- 013 meas 4211 site 03689879 decision SHIFT shift 0.20
- 014 meas 4215 site 03689879 decision SHIFT shift 0.03
- 015 meas 4216 site 03689879 decision CHECK shift -
- 016 meas 4217 site 03715332 decision ICE shift -
- 017 meas 4220 site 03715332 decision REJECTED shift -
- 018 meas 4223 site 03715332 decision ICE shift -
- 019 meas 4225 site 03715332 decision ICE shift -
- 020 meas 4227 site 03715332 decision ICE shift -
- 021 meas 4231 site 03715332 decision SHIFT shift -0.11
- 022 meas 4233 site 03715332 decision CHECK shift -
- 023 meas 4237 site 03767985 decision SHIFT shift -0.17
- 024 meas 4241 site 03767985 decision SHIFT shift -0.15
- 025 meas 4245 site 03767985 decision SHIFT shift -0.17
- 026 meas 4246 site 03767985 decision SHIFT shift -0.15
- 027 meas 4247 site 03767985 decision SHIFT shift -0.15
- 028 meas 4249 site 03767985 decision SHIFT shift -0.13
- 029 meas 4253 site 03767985 decision SHIFT shift -0.13
- 030 meas 4254 site 03777655 decision SHIFT shift -0.08
- 031 meas 4256 site 03777655 decision CHECK shift -
- 032 meas 4260 site 03777655 decision SHIFT shift 0.09
- 033 meas 4262 site 03777655 decision SHIFT shift 0.10
- 034 meas 4264 site 03777655 decision SHIFT shift 0.07
- 035 meas 4266 site 03777655 decision SHIFT shift 0.17
- 036 meas 4268 site 03777655 decision SHIFT shift 0.14
- 037 meas 4270 site 03990665 decision ICE shift -
- 038 meas 4271 site 03990665 decision ICE shift -
- 039 meas 4274 site 03990665 decision REJECTED shift -
- 040 meas 4276 site 03990665 decision ICE shift -
- 041 meas 4277 site 03990665 decision ICE shift -
- 042 meas 4279 site 03990665 decision CHECK shift -
- 043 meas 4280 site 03990665 decision CHECK shift -
- 044 meas 4283 site 04554766 decision ICE shift -
- 045 meas 4284 site 04554766 decision ICE shift -
- 046 meas 4288 site 04554766 decision ICE shift -
- 047 meas 4290 site 04554766 decision ICE shift -
- 048 meas 4291 site 04554766 decision ICE shift -
- 049 meas 4294 site 04554766 decision SHIFT shift 0.07
- 050 meas 4298 site 04554766 decision SHIFT shift 0.06
- 051 meas 4301 site 04597193 decision ICE shift -
- 052 meas 4302 site 04597193 decision ICE shift -
- 053 meas 4305 site 04597193 decision ICE shift -
- 054 meas 4307 site 04597193 decision CHECK shift -
- 055 meas 4308 site 04597193 decision CHECK shift -
- 056 meas 4311 site 04597193 decision CHECK shift -
- 057 meas 4312 site 04597193 decision SHIFT shift 0.07
- 058 meas 4313 site 05488298 decision SHIFT shift 0.06
- 059 meas 4316 site 05488298 decision SHIFT shift -0.06
- 060 meas 4319 site 05488298 decision SHIFT shift -0.10
- 061 meas 4321 site 05488298 decision CHECK shift -
- 062 meas 4325 site 05488298 decision SHIFT shift -0.04
- 063 meas 4326 site 05488298 decision CHECK shift -
- 064 meas 4327 site 05488298 decision SHIFT shift -0.04
- 065 meas 4330 site 05843389 decision SHIFT shift 0.06
- 066 meas 4334 site 05843389 decision SHIFT shift -0.07
- 067 meas 4338 site 05843389 decision SHIFT shift -0.08
- 068 meas 4342 site 05843389 decision SHIFT shift -0.07
- 069 meas 4343 site 05843389 decision SHIFT shift 0.03
- 070 meas 4345 site 05843389 decision REJECTED shift -
- 071 meas 4347 site 05843389 decision SHIFT shift 0.10
- 072 meas 4349 site 03777655 decision SHIFT shift 0.08
- 073 meas 4351 site 03715332 decision CHECK shift -
- 074 meas 4353 site 04554766 decision ICE shift -
- day 03203376 2026-01-01 mean 105 (ok)
- day 03203376 2026-01-06 mean 105 (ok)
- day 03203376 2026-01-11 mean 115 (ok)
- day 03203376 2026-01-16 mean 117 (ok)
- day 03203376 2026-01-21 mean 122 (ok)
- day 03203376 2026-01-26 mean 125 (ok)
- day 03203376 2026-01-31 mean 124 (late shard)
- day 03203376 2026-02-05 mean 115 (ok)
- day 03203376 2026-02-10 mean 107 (ok)
- day 03203376 2026-02-15 mean 101 (ok)
- day 03203376 2026-02-20 mean 105 (late shard)
- day 03203376 2026-02-25 mean 79 (ok)
- day 03203376 2026-03-02 mean 74 (ok)
- day 03203376 2026-03-07 mean 71 (late shard)
- day 03203376 2026-03-12 mean 69 (ok)
- day 03203376 2026-03-17 mean 66 (ok)
- day 03203376 2026-03-22 mean 74 (ok)
- day 03203376 2026-03-27 mean 81 (late shard)
- day 03689879 2026-01-01 mean 4 (ok)
- day 03689879 2026-01-06 mean 3.8 (ok)
- day 03689879 2026-01-11 mean 3.6 (ok)
- day 03689879 2026-01-16 mean 3.3 (ok)
- day 03689879 2026-01-21 mean 3 (ok)
- day 03689879 2026-01-26 mean 3.9 (ok)
- day 03689879 2026-01-31 mean 3.9 (late shard)
- day 03689879 2026-02-05 mean 3.9 (ok)
- day 03689879 2026-02-10 mean 3.9 (ok)
- day 03689879 2026-02-15 mean 4 (ok)
- day 03689879 2026-02-20 mean 3.9 (late shard)
- day 03689879 2026-02-25 mean 3.8 (ok)
- day 03689879 2026-03-02 mean 3.9 (ok)
- day 03689879 2026-03-07 mean 3.8 (late shard)
- day 03689879 2026-03-12 mean 3.6 (ok)
- day 03689879 2026-03-17 mean 3.6 (late shard)
- day 03689879 2026-03-22 mean 3.9 (late shard)
- day 03689879 2026-03-27 mean 4.6 (late shard)
- day 03715332 2026-01-01 mean 579 (late shard)
- day 03715332 2026-01-06 mean 588 (ok)
- day 03715332 2026-01-11 mean 605 (late shard)
- day 03715332 2026-01-16 mean 623 (late shard)
- day 03715332 2026-01-21 mean 669 (ok)
- day 03715332 2026-01-26 mean 698 (ok)
- day 03715332 2026-01-31 mean 717 (late shard)
- day 03715332 2026-02-05 mean 698 (ok)
- day 03715332 2026-02-10 mean 660 (ok)
- day 03715332 2026-02-15 mean 603 (ok)
- day 03715332 2026-02-20 mean 566 (ok)
- day 03715332 2026-02-25 mean 529 (late shard)
- day 03715332 2026-03-02 mean 405 (ok)
- day 03715332 2026-03-07 mean 396 (late shard)
- day 03715332 2026-03-12 mean 1130 (ok)
- day 03715332 2026-03-17 mean 374 (ok)
- day 03715332 2026-03-22 mean 422 (ok)
- day 03715332 2026-03-27 mean 511 (ok)
- day 03767985 2026-01-01 mean 160 (late shard)
- day 03767985 2026-01-06 mean 151 (ok)
- day 03767985 2026-01-11 mean 157 (ok)
- day 03767985 2026-01-16 mean 154 (ok)
- day 03767985 2026-01-21 mean 146 (late shard)
- day 03767985 2026-01-26 mean 151 (ok)
- day 03767985 2026-01-31 mean 151 (late shard)
- day 03767985 2026-02-05 mean 157 (late shard)
- day 03767985 2026-02-10 mean 266 (ok)
- day 03767985 2026-02-15 mean 360 (ok)
- day 03767985 2026-02-20 mean 148 (ok)
- day 03767985 2026-02-25 mean 146 (ok)
- day 03767985 2026-03-02 mean 143 (ok)
- day 03767985 2026-03-07 mean 140 (late shard)
- day 03767985 2026-03-12 mean 135 (ok)
- day 03767985 2026-03-17 mean 116 (late shard)
- day 03767985 2026-03-22 mean 127 (ok)
- day 03767985 2026-03-27 mean 151 (late shard)
- day 03777655 2026-01-01 mean 71 (ok)
- day 03777655 2026-01-06 mean 68 (late shard)
- day 03777655 2026-01-11 mean 66 (ok)
- day 03777655 2026-01-16 mean 67 (late shard)
- day 03777655 2026-01-21 mean 68 (ok)
- day 03777655 2026-01-26 mean 70 (late shard)
- day 03777655 2026-01-31 mean 69 (ok)
- day 03777655 2026-02-05 mean 91 (ok)
- day 03777655 2026-02-10 mean 62 (ok)
- day 03777655 2026-02-15 mean 53 (ok)
- day 03777655 2026-02-20 mean 50 (ok)
- day 03777655 2026-02-25 mean 46 (ok)
- day 03777655 2026-03-02 mean 50 (ok)
- day 03777655 2026-03-07 mean 50 (ok)
- day 03777655 2026-03-12 mean 47 (late shard)
- day 03777655 2026-03-17 mean 45 (late shard)
- day 03777655 2026-03-22 mean 47 (ok)
- day 03777655 2026-03-27 mean 47 (ok)
- day 03990665 2026-01-01 mean 202 (late shard)
- day 03990665 2026-01-06 mean 220 (ok)
- day 03990665 2026-01-11 mean 232 (ok)
- day 03990665 2026-01-16 mean 232 (ok)
- day 03990665 2026-01-21 mean 232 (late shard)
- day 03990665 2026-01-26 mean 245 (ok)
- day 03990665 2026-01-31 mean 278 (ok)
- day 03990665 2026-02-05 mean 292 (ok)
- day 03990665 2026-02-10 mean 273 (ok)
- day 03990665 2026-02-15 mean 245 (ok)
- day 03990665 2026-02-20 mean 202 (ok)
- day 03990665 2026-02-25 mean 194 (ok)
- day 03990665 2026-03-02 mean 173 (ok)
- day 03990665 2026-03-07 mean 168 (ok)
- day 03990665 2026-03-12 mean 162 (ok)
- day 03990665 2026-03-17 mean 699 (ok)
- day 03990665 2026-03-22 mean 232 (ok)
- day 03990665 2026-03-27 mean 202 (ok)
- day 04554766 2026-01-01 mean 243 (ok)
- day 04554766 2026-01-06 mean 237 (ok)
- day 04554766 2026-01-11 mean 261 (ok)
- day 04554766 2026-01-16 mean 294 (ok)
- day 04554766 2026-01-21 mean 326 (ok)
- day 04554766 2026-01-26 mean 346 (late shard)
- day 04554766 2026-01-31 mean 339 (ok)
- day 04554766 2026-02-05 mean 313 (late shard)
- day 04554766 2026-02-10 mean 294 (ok)
- day 04554766 2026-02-15 mean 281 (ok)
- day 04554766 2026-02-20 mean 325 (late shard)
- day 04554766 2026-02-25 mean 295 (late shard)
- day 04554766 2026-03-02 mean 238 (late shard)
- day 04554766 2026-03-07 mean 245 (ok)
- day 04554766 2026-03-12 mean 367 (late shard)
- day 04554766 2026-03-17 mean 260 (late shard)
- day 04554766 2026-03-22 mean 199 (late shard)
- day 04554766 2026-03-27 mean 241 (ok)
- day 04597193 2026-01-01 mean 270 (late shard)
- day 04597193 2026-01-06 mean 275 (ok)
- day 04597193 2026-01-11 mean 275 (ok)
- day 04597193 2026-01-16 mean 285 (ok)
- day 04597193 2026-01-21 mean 301 (late shard)
- day 04597193 2026-01-26 mean 280 (late shard)
- day 04597193 2026-01-31 mean 260 (ok)
- day 04597193 2026-02-05 mean 245 (late shard)
- day 04597193 2026-02-10 mean 200 (ok)
- day 04597193 2026-02-15 mean 198 (late shard)
- day 04597193 2026-02-20 mean 195 (ok)
- day 04597193 2026-02-25 mean 183 (ok)
- day 04597193 2026-03-02 mean 173 (ok)
- day 04597193 2026-03-07 mean 170 (ok)
- day 04597193 2026-03-12 mean 167 (ok)
- day 04597193 2026-03-17 mean 170 (ok)
- day 04597193 2026-03-22 mean 407 (ok)
- day 04597193 2026-03-27 mean 189 (ok)
- day 05488298 2026-01-01 mean 32 (ok)
- day 05488298 2026-01-06 mean 32 (ok)
- day 05488298 2026-01-11 mean 31 (late shard)
- day 05488298 2026-01-16 mean 28 (ok)
- day 05488298 2026-01-21 mean 26 (ok)
- day 05488298 2026-01-26 mean 26 (ok)
- day 05488298 2026-01-31 mean 26 (ok)
- day 05488298 2026-02-05 mean 26 (ok)
- day 05488298 2026-02-10 mean 25 (late shard)
- day 05488298 2026-02-15 mean 24 (ok)
- day 05488298 2026-02-20 mean 24 (ok)
- day 05488298 2026-02-25 mean 24 (ok)
- day 05488298 2026-03-02 mean 23 (late shard)
- day 05488298 2026-03-07 mean 27 (ok)
- day 05488298 2026-03-12 mean 24 (late shard)
- day 05488298 2026-03-17 mean 24 (ok)
- day 05488298 2026-03-22 mean 26 (ok)
- day 05488298 2026-03-27 mean 30 (ok)
- day 05843389 2026-01-01 mean 5.1 (ok)
- day 05843389 2026-01-06 mean 5.4 (ok)
- day 05843389 2026-01-11 mean 4.5 (ok)
- day 05843389 2026-01-16 mean 3.7 (late shard)
- day 05843389 2026-01-21 mean 3.2 (late shard)
- day 05843389 2026-01-26 mean 3.4 (late shard)
- day 05843389 2026-01-31 mean 3.2 (ok)
- day 05843389 2026-02-05 mean 2.7 (ok)
- day 05843389 2026-02-10 mean 2.3 (ok)
- day 05843389 2026-02-15 mean 2.5 (ok)
- day 05843389 2026-02-20 mean 3 (late shard)
- day 05843389 2026-02-25 mean 0.64 (ok)
- day 05843389 2026-03-02 mean 2.7 (ok)
- day 05843389 2026-03-07 mean 2.5 (ok)
- day 05843389 2026-03-12 mean 2.1 (late shard)
- day 05843389 2026-03-17 mean 2.1 (late shard)
- day 05843389 2026-03-22 mean 2.7 (ok)
- day 05843389 2026-03-27 mean 2.3 (ok)

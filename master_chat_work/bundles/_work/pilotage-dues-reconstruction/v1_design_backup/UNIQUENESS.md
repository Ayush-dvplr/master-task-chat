# UNIQUENESS 44635de pilotage-dues-reconstruction (v2, 26 Oct 22:08)

| quantity | candidate space | why exactly one answer (or a stated verdict) | measured |
|---|---|---|---|
| tariff of a station-period (R-FIT, joint) | per period 5 x 4 x 3 x 4 = 180 combinations from tariff_circular.md:64-73 (base_per_100gt 1.80, 1.95, 2.10, 2.25, 2.40; draft_per_dm 2.50, 3.00, 3.50, 4.00; night_factor 1.25, 1.40, 1.50; per_tug 35.00, 50.00, 65.00); a station with a notice has at most 180 x 180 pairs, those agreeing on every coefficient the notice does not name | :83-90 define the station tariff over both periods and the combination of a period as its projection; zero or more than one projection is a stated verdict with a stated reason (:103-107) | shipped: 1 alone and 1 joint in all 5 periods; hidden 1101-1106: X 1/1, Y1 alone 3-4 joint 1, Y2 joint 3-4, Z 2, W alone 1/1 joint 0/0 (generator assert per seed; solve_proto agrees) |
| period of a visit | at most two periods per station | instant = boarding instant or CANCEL time (:23); period holding the instant, 00:00 on the notice date (:75-81) | notice-day, eve and invoiced-after plants on every hidden seed |
| covered minutes of a visit | 0 .. on-board minutes | certificate pool of every visit of its vessels, ordered by instant then lower visit id (exemption_policy.md:22-26); total order, so one draw sequence | tie and cap plants on every hidden seed; 2 runs identical |
| row in force of a vessel | rows of the vessel, at most one per measured_from date | latest measured_from on or before the instant's date, else the `-` row (exemption_policy.md:11-13) | Q6 plants on every hidden seed |
| due under partial billing | integer cents | each rounded line x billed / on-board rounded half-even, summed (tariff_circular.md:56-60); exact fractions in the prototype | solve dues equal generator dues on every disputed row (xcheck_proto.py) |

## Lessons for the master
- A closed candidate space quoted in full makes uniqueness a counting fact the generator can assert | no change: already G12

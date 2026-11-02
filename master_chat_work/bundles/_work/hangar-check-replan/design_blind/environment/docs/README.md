# Heavy check replan: document register

Maintenance Control publishes a heavy check plan for each season. A disruption notice has come after
the plan was published, and the season has to be replanned for the whole fleet. These documents are
the full set of rules for that replan. Each topic is governed by exactly one file:

| topic | governing file |
|---|---|
| input files, field meanings, which rows are planned, rejected rows | `/app/environment/docs/data_conventions.md` |
| hangar lines, calendars, start and finish days, how plans are compared | `/app/environment/docs/planning_policy.md` |
| compressing a check, overtime shifts, the season overtime pool, the overtime allowance and its settlement | `/app/environment/docs/overtime_policy.md` |
| deferring a request to next season and the reason recorded | `/app/environment/docs/deferral_policy.md` |
| output files, their fields and how each value is filled | `/app/environment/docs/output_schema.md` |

The numbers (rates, penalties, limits, season dates) live only in the data files under
`/app/environment/data/`. Where two documents seem to say different things about one topic, the
governing file for that topic in the table above decides.

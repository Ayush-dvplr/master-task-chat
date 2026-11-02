Brassmoor Skirmish is our turn-based grid tactics game. Every finished match is saved as a replay log, and the studio needs a replay engine that plays these logs back exactly as the game did, so that state digests, results, the rating ladder and the balance numbers can be rebuilt from the logs alone. The old replay tool gets a lot of this wrong and nobody trusts its output.

Everything you need is in `/app/data`. The rule book is `/app/data/brassmoor_rules.md` and the season 5 corrections are in `/app/data/errata.md`. The JSON tables, the map atlas, the player list and five replay exports sit next to them. When the book and the errata disagree, follow the errata. When either of them disagrees with a JSON table, follow the table. The visible export uses only the simple parts of the log grammar, and its keyframes always agree with a correct replay; the other four exports use all of it, including format 2 logs, ruleset 2 matches, lagged orders, keyframes that can disagree with the replay, damaged lines and revision-checked corrections to earlier orders. These corrections can undo and restore past actions. The reports must include the intermediate recovery audit, not just the final corrected match.

Write the engine as one self-contained Python file at `/app/out/optimize.py`. It must run as

```bash
python3 /app/out/optimize.py <data_dir> <out_dir>
```

where `<data_dir>` holds the six tables (`units.json`, `terrain.json`, `advantage.json`, `rulesets.json`, `players.json`, `maps.txt`) and the five replay logs under the same file names as in `/app/data`. The rule book and the errata are not copied there. `<out_dir>` is where the nine reports go; create it if it is missing. Then run it once as `python3 /app/out/optimize.py /app/data /app/out` so that these files exist and hold exactly what your final engine writes for that data:

* `/app/out/scenario_visible.json`
* `/app/out/scenario_peak.json`
* `/app/out/scenario_steady.json`
* `/app/out/scenario_burst.json`
* `/app/out/scenario_latency.json`
* `/app/out/perf_report.json`
* `/app/out/bottleneck_analysis.json`
* `/app/out/recommendations.json`
* `/app/out/data_quality.json`

Section 13 of the rule book gives the exact shape of every report, with the recovery audit defined in section 16. Key order and whitespace in the JSON do not matter; values, list order and types do.

Rules of engagement:

* Use only the Python standard library, both in your engine and in any helper you write. Package installs are off limits.
* Treat everything under `/app/data` as read-only. Do not edit, move or delete those files.
* Read every number, unit type and terrain symbol that the tables in `<data_dir>` give from `<data_dir>` when the engine runs, and write none of them into the engine.
* The engine reads only the `<data_dir>` it is given on the command line and writes only into `<out_dir>`. It must not look at `/app/data` when it is pointed at another directory.
* We will run your engine on other exports that have the same file names but different matches, seeds, maps in use and players. So every value must come from the rules applied to the input, never from copies of results for the shipped exports.
* Each replay file is handled by the same rules. Its file name only decides which scenario report it feeds and which name appears in that report.
* The same input must give byte-for-byte the same output on every run, whatever the hash seed or the machine.
* One run over a directory like `/app/data` must finish inside 300 seconds.

When you finish, tell us in a short note what you built, how you checked it against the keyframes and examples in the book, and anything in the data you think is still unclear.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.

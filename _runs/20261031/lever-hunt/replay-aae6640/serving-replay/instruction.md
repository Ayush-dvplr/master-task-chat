The extract mounted at `/app/data` is one settlement period of a model-serving platform: request logs of its traffic classes, the tenant register, correction layers, the rate card and the other material the settlement of reserved throughput needs. The documents shipped with the data govern this work.

Write a program at `/app/out/optimize.py` with three entry points. `python3 /app/out/optimize.py DATA_DIR OUT_DIR`, where DATA_DIR is an extract folder, settles the whole period and writes every report the documents define into OUT_DIR, creating OUT_DIR when it is absent, including the frozen reports `/app/out/scenario_visible.json`, `/app/out/scenario_peak.json`, `/app/out/scenario_steady.json`, `/app/out/scenario_burst.json`, `/app/out/scenario_latency.json`, `/app/out/perf_report.json`, `/app/out/bottleneck_analysis.json`, `/app/out/recommendations.json` and `/app/out/data_quality.json` when OUT_DIR is `/app/out`. `python3 /app/out/optimize.py EVENTS_LOG RULES_JSON`, where EVENTS_LOG is one request log and RULES_JSON is the control file of its extract, prints the result object of that class. The module function `aggregate(events_path, rules_path)` returns that same object. Run the directory form once on `/app/data` with `/app/out` as OUT_DIR, so the reports of the shipped extract sit in `/app/out` when you finish.

It will also be run on other extracts in the same layout, so nothing in it may depend on this particular period. Each changed extract is an extract in this layout in its own right. Each call finishes within 60 seconds. On a large workload, the `aggregate` call must also use at most 70 percent of the CPU time of a straightforward implementation that parses the whole request log again for every member of a pool in every settlement round.

Every report follows the layout and form the documents give, exactly: text reports byte for byte, database and workbook reports value for value. The text reports must be byte-identical, and the database and workbook reports value-identical, across runs, working directories, extract locations and output directories.

When an extract breaks one of the invariants that ct_svc.md lists, the program stops with an error and writes no report.

The program must leave DATA_DIR untouched, read nothing outside DATA_DIR, OUT_DIR and its own directory, and write nothing outside OUT_DIR. Use only the Python standard library, and open no network connection. The program runs as a single process and starts no other process. It reads no clock and uses no `random`, `uuid` or `secrets` module. Every except clause in the program names an exception class and never discards the error. Every function in the program is at most 50 lines long. The program is self-contained: it imports nothing from its own folder. Only `/app/out/optimize.py` and the nine frozen reports are collected from `/app/out`.

Compare the settled reservation of every tenant with the prior output of the extract and state the largest difference.

Each what-if is worked out by rerunning the whole settlement with exactly the change named, on a copy of the extract, with everything else as shipped; a what-if over a range of values reruns one copy per value. Work out each what-if answer with a run of your program on its edited copy.

1. For each starting step from 1 to 20 quarters given to pool pl-pe1, each on its own copy, which starting step gives the largest grand bill total of the period, and what is that total?
2. On copies of the extract whose meter sheet keeps only readings M11 to M25, for each whole number from 40 to 100 written as the RU of reading M25, each on its own copy, at how many of these values does the period settle, and which value gives the largest grand bill total among them, with that total?
3. For each cutoff_seq from 100 to 230 written in the control file, each on its own copy, which cutoff_seq values give the smallest grand bill total of the period, and what is that total?
4. If the meter sheet kept only readings M11 to M25, with reading M25 reading 70 RU instead of 69, what would the total overage units over all classes be?
5. If an amendment with seq 243 set the contracted_ru of tenant tn-7de in class steady to 31, what would the total settled reservation moved be?
6. If pool pl-bu1 started with a step of 14 quarters, what would the total settled reservation moved be?
7. If the amendment of what-if 5 were in place and pool pl-st1 also started with a step of 12 quarters, what would the grand bill total of the period be?
8. If the steady rate row effective from 2026-03-04 had an ru_rate_micro of 2300, what would the grand bill total of the period be?
9. If the burst rate row effective from 2026-03-13 had a round_fee_micro of 1170, what would the grand bill total of the period be?

In your final message, after the what-if answers, state four headline figures of the shipped extract: the total settled reservation moved (the sum over all members of the absolute difference between settled and contracted reservation), the total charged settlement rounds (the sum over all pools of the rounds the orchestration charge counts), the total demand in RU over all classes, and the total overage units over all classes. Also state the grand bill total of the period with its three parts (reservation, overage and orchestration charges), and the number of reports the directory form wrote. Report only figures your own runs printed. State the number of reports the directory form wrote as a listing of OUT_DIR printed it. Claim only runs and checks that your own commands performed. Report a check as passing only when its last run passed.

You have 7200 seconds to complete this task. Do not use online solutions or hints specific to this task.

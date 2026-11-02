The Halvard playout centre has to close five channel weeks of commercial airtime. The close extract is under `/app/data`. `/app/data/corpus_index.md` names every file and its layout and points at the rule and contract documents; those documents are the only authority for this close, and nothing in this prompt repeats or summarises a rule they carry. Read them and work out what this close requires from the data itself.

Write one program at `/app/out/optimize.py` that uses only the Python standard library, defines `reconcile(data_dir, workload)` and runs as

```
python3 /app/out/optimize.py DATA_DIR WORKLOAD
```

printing, as one JSON document on standard output and nothing else, the scenario object that `/app/data/output_contract.md` defines for that workload. Then use the program to write the five scenario artifacts `/app/out/scenario_visible.json`, `/app/out/scenario_peak.json`, `/app/out/scenario_steady.json`, `/app/out/scenario_burst.json` and `/app/out/scenario_latency.json`, and the four roll-ups `/app/out/perf_report.json`, `/app/out/bottleneck_analysis.json`, `/app/out/recommendations.json` and `/app/out/data_quality.json`, each holding exactly what the contract defines for `/app/data`.

The program will also be run on data directories you have not seen. They share this layout but may differ in workload names, channel, frame rate and timecode mode, zone and summer time change, broadcast day start, daypart set, sync tolerance, cutoff, number of broadcast days, prices and size, so every rule parameter must be read from the directory the program is given and none may be written into the source. One unseen workload has 28 broadcast days and about five times the spots of the largest workload here; on it `reconcile` must return within four times the time a straightforward single pass reference implementation takes on the same machine, plus two seconds. Two runs on the same input print byte identical output, the order of lines inside an input file never changes a result, the result never depends on where the directory sits, the program writes no file anywhere, and when an input file it needs is missing it exits with a non zero status and prints nothing.

Where a retired, historical or informal document in the extract disagrees with the current rule documents, the current rule documents govern. An artifact counts only when every entry and value in it is exact: a total that is right while a row behind it is wrong does not count, and neither does a correct object under another key, file name or path.

Leave every file under `/app/data` exactly as shipped. Do not install packages. Do not look up the solution or any part of the method online. You have 7200 seconds to complete this task.

Finish with a closing message that states the nine closing figures defined at the end of `/app/data/output_contract.md` for `/app/data`, each with its label and its three facts as exact whole numbers and a workload name, and says which run of which script produced them. None of these figures appears in any artifact.

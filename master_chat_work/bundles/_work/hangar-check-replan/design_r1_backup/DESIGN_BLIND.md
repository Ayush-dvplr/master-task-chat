# DESIGN_BLIND: 24bff4e scored 00:00
Program copied to proto/blind/derive_report.py (794 lines, 6 min to write, no edits after first run).
Runs in Docker python:3.12-slim --memory 4g --cpus 2, alarm 60 s, via proto/runblind.sh; scored by
proto/scoreblind.py (per family, per field, empty-axis parts split out w1). Scratch:
_runs/20261031/hangar-check-replan/score-24bff4e/{scratch,logs}.
Result: EXACT on shipped seed 1 and hidden h1 1:1, h2 3:1 (empty base + empty segment), h3 1:0,
h4 3:0, h5 5:0. Hidden lever points kept 100/100. No WRONG, TIMEOUT or CRASH. 0.15-0.81 s per run.
Method = the reference (see DESIGN_SUMMARY "Design blind"). Its own notes flag the tie ladder,
deferral-reason basis and pool hard-cap as "inferred", yet it chose the stated reading each time.
Bar: blind keeps >= 60% -> NO CORE. Stopped for the master's redesign decision.

## Redesign 1 blind d0dc88d (01 Nov 01:13)
Score run score-d0dc88d: EXACT on shipped seed 2 and on all 10 hidden corpora (h1..h6 mixed traps, h7..h10 one family each), every family incl. empty-axis and data_quality; 100% lever kept; 0 WRONG / TIMEOUT / CRASH. Docx reader follows the profile sentence literally (relationship lookup, skip w:del/w:moveFrom, Choice by Requires prefix namespace, else Fallback). Verdict: NO CORE (second).

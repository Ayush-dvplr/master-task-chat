# Doc diffs, try 3 (option 1 convention lever)

Applied in BUNDLE after master's "go" (30 Oct ~02:25). D7 was added during the build (precheck IN17 lint).

## D1 corpus_index.md:53 (last sentence)
Before: `The column is an observation; it is never an input to a profile.`
After:  `The gateway conventions belong to the corpus, and its own observations are the record of them.`

## D2 instruction.md:1 (last sentence of paragraph 1)
Before: `Several conventions are left to the access gateway rather than written down anywhere; the reviewer observations in `access_attestations.csv` are the only record of what the gateway did, and exactly one reading of each such convention reproduces every observation.`
After:  `Several conventions are left to the access gateway rather than written down anywhere, and they belong to each corpus; the reviewer observations in that corpus's `access_attestations.csv` are the only record of what its gateway did, and exactly one reading of each such convention reproduces every observation.`

## D3 instruction.md:3 (rerun promise)
Before: `built to the same contract with other zones, instants, configuration layers, people and records,`
After:  `built to the same contract with their own zones, instants, configuration layers, gateway conventions, people and records,`

## D4 instruction.md:11-22 (closing message, 8 figure groups)
Before: `Finish with a closing message that states each of the following ...` plus items 1-8.
After:  one sentence: `Finish with a closing message that names, for each convention left to the gateway, the reading the shipped observations show.`
Why: the judge drops the figure criteria R1-R8 (LEVER_RULES J1); the new J6 criterion R10 needs this ask (AL-1/AL-2). It names no method and no value.

## D5 legacy_runbook.md:3 and :11-47 (QC_RISKS item 2, defect map)
Before L3: status paragraph ending `It is reproduced in full because the first release was built to match it, so it reads like a specification; treat it as a record of how the tool once behaved, not as a rule for how it must behave now.`
After L3:  same paragraph without that last sentence.
Before L11-47: sections Time and calendars, Records and units, Identity, Elevation and policy, Robustness (one bullet per planted defect, including the three legacy conventions at L13, L17, L36).
After: removed. File keeps title, status paragraph and `## Daily run` (L5-9).

## D6 time_rules.md:13 (contract clock clause)
Before: `Contract `start_date` and `end_date` are read on the same clock as HR dates, using the contract's own `site`;`
After:  `Contract `start_date` and `end_date` are read on the same clock as HR dates, using the contract's own `site` where that clock is a site's;`
Why: a corpus whose gateway reads HR days on one zone's clock (or UTC) would otherwise contradict "using the contract's own site".

## Lines checked and left unchanged
- time_rules.md:13 (rest of line) and :21, access_contract.md:26 and :40: already say the convention is the gateway's and the observations show it; they do not say the convention is fixed across corpora.
- cli_contract.md, config_contract.md, identity_rules.md, provenance_rules.md, output_contract.md: no convention wording.

## D7 (build, precheck IN17-PHRASE lint) instruction.md:1 and :5
- :1 'and exactly one reading of each such convention' -> 'and a single reading of each such convention' (same requirement: unique fit).
- :5 'Each of these five files must be' -> 'Each of these files must be'; 'that produced the five files in the order' -> 'that produced those files in the order'.
- :5 'serialization for all seven artifacts are in' -> 'serialization for every artifact are in' (precheck2 surfaced it after 'five files' went; the lint reports the first match per line; same requirement).

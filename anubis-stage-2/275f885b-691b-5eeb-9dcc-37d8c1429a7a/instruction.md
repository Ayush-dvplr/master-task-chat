# Campaign dose ration settlement

The animal health service has handed you the export folder `/app/data` for a fortnightly dose
campaign across four veterinary regions and two holder segments. Doses are scarce, so every
round rations what the depots hold. The folder carries the campaign contract, the rule
documents it names, configuration registers, the primary export streams, reference tables, a
correction stream, two settlement observation logs and one retired runbook. The contract tier
is the single source of truth for every quantity, and `corpus_index.md` names the tier of each
file. Read `source_manifest.md` and `corpus_index.md` before anything else. The retired runbook
governs nothing. Nothing in the folder tells you which records disagree with each other;
finding that out is the work.

Build a settlement program at `/app/out/derive_report.py`. It accepts `--data` with a corpus
folder and `--out` with an output folder, and it writes nine documents:
`/app/out/region_North.json`, `/app/out/region_South.json`, `/app/out/region_West.json`,
`/app/out/region_East.json`, `/app/out/segment_commercial.json`,
`/app/out/segment_public.json`, `/app/out/summary.json`, `/app/out/policy_audit.json` and
`/app/out/data_quality.json`. Run it over `/app/data` into `/app/out` so those nine documents
sit beside it when you finish. The same program will be run over campaign extracts nobody has
seen, with other round counts, other block counts, other clock offsets and other settlement
evidence, so every rule it applies has to come from the corpus it is given. Use only the Python
standard library, run no external commands from the program, and keep the program offline.

`output_contract.md` fixes every document name, every key, every enumerated value and every
ordering, and it binds to the letter. Every quantity is an exact whole number of doses. A
document counts only when every quantity in it is exact; a close total earns nothing. Block
identities carry their restock epoch in the form `BLK-0042#2` and lot identities carry their
production year in the form `LOT-1182@2033`. Each settled claim carries exactly one outcome and
one reason from the registers in `reason_codes.json`, chosen by the precedence those registers
declare. Rejected requisitions carry exactly one reject code. Nobody recorded how many records
disagree with each other, so there is no count to check yourself against.

Work the campaign in one pass over the rounds in calendar order. Admission precedes identity,
identity precedes the governing head count, the governing head count precedes the entitlement,
the entitlement precedes the claimable quantity, the claimable quantity precedes the award, and
the award precedes the carried claim of the next round. Two rules the registers leave unstated
are settled by the observation logs, and `policy_audit.json` reports each settled reading in the
key the output contract names for it. Where two rules could both apply to one record, the
precedence stated in `campaign_contract.md` decides which one does, and applying a rule to
records it does not reach costs exactly as much as failing to apply it where it does. Leave
`/app/data` untouched, write nothing else into `/app/out`, and make a second run over the same
corpus produce the same nine documents. The program reads only the folder passed to `--data`,
and it works whatever that folder is called.

Finish with a message that states these quantities. How many settled claims took their
governing head count from the field intake and how many from the dispatch stream. How many
settled claims took it from the registry, and how many distinct blocks took it from the registry
at least once. How many of the governing tokens in the governance observation log name each
of the three sources. How many entries of the clearance observation log record a carried claim
that was cleared and how many record one left standing. How many lots entered a
regional pool and how many stayed outside every pool. How many pooled lots took their dose
content from a laboratory assay and how many took it from the reference table. The pooled dose
content before the substitution derate, the content after it and the doses the derate costs.
Which round the claims of the round the calendar removed settled in, and how many claims arrived
that way. How many requisitions were refused because the effective reading fell at the closing
instant of a claim window, and how many because it fell before the opening instant. How many
claims took exactly one dose from the remainder step of the ladder, and in how many cells that
step ran. State every figure as an exact whole number, and say plainly which observation
evidence settled each of the two unstated rules and what in that evidence settled it.

You have 10800 seconds to complete this task. Solve it from the corpus in front of you without
searching online for solutions or task specific hints.

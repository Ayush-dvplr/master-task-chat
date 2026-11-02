The month end settlement of a satellite operator ground segment has been thrown out, and the working papers under `/app/data` are all that survives of it. Rebuild the settlement from those papers and leave behind a program that can rebuild it again on a month it has never seen.

Start at `/app/data/readme_first.txt`, then `/app/data/pipeline_contract_overview.md`, which names the fourteen stages and points at the document that owns each one. Every rule the work needs is written down somewhere under that directory. Several operating constants are written down only inside a spreadsheet, a memo or a directive, and none of them is repeated anywhere else, so the papers have to be opened rather than skimmed.

You have to produce every artifact named in the block below, at exactly that path.

```
/app/out/canonical_contact_ledger.csv
/app/out/admitted_contact_ledger.csv
/app/out/rejected_contact_ledger.psv
/app/out/normalized_contact_intervals.tsv
/app/out/antenna_capacity_ledger.csv
/app/out/capacity_cap_exceptions.psv
/app/out/contention_groups.jsonl
/app/out/winning_resource_assignments.csv
/app/out/displaced_contact_ledger.psv
/app/out/mission_entitlement_state.csv
/app/out/carry_forward_ledger.csv
/app/out/rationing_pass_trace.jsonl
/app/out/delivered_volume_ledger.csv
/app/out/deferred_volume_ledger.csv
/app/out/unused_capacity_ledger.tsv
/app/out/station_utilisation_ledger.csv
/app/out/antenna_utilisation_ledger.tsv
/app/out/mission_settlement_statements.csv
/app/out/station_settlement_statements.csv
/app/out/contract_compliance_ledger.csv
/app/out/credit_debit_ledger.csv
/app/out/outage_adjustment_ledger.psv
/app/out/exception_classification_report.jsonl
/app/out/tie_resolution_report.csv
/app/out/cross_source_discrepancy_report.psv
/app/out/invariant_check_report.json
/app/out/period_reconciliation_totals.json
/app/out/network_settlement_summary.xml
/app/out/per_mission_final_summary.md
/app/out/stage_digest_manifest.json
/app/out/settle.py
```

Give each artifact the columns or keys that `/app/data/output_schema_reference.md` names, in that order and that row order. Lay each one out exactly as `/app/data/serialization_and_digest_contract.md` requires, down to the separator, the header row, the key order, the indent, the line ending and the single trailing newline. Write every artifact on every run, including the ones with no rows. Make every quantity a whole number and take every division where `/app/data/rounding_and_precision.yml` places it, leaving no floating point value in any artifact.

Settle the stages in the order `/app/data/ordering_dependencies.yaml` states, honouring the one edge there that runs backwards. Test each pass against the admission predicates in the published order and record the first predicate that failed and no other. Use only codes that `/app/data/exception_code_dictionary.xml` declares. Treat every interval in every paper as half open. Split the eligible interval of a pass at the station local accounting boundary and settle it in each period it reaches. Apply the per contact cap to each canonical row before any aggregation. Resolve contention on one aperture period with the published five key ordering and displace a losing pass whole. Ration an over subscribed aperture period budget only by the procedure in `/app/data/rationing_iteration_notes.md`, and reproduce the worked example there before trusting your own. Consume carry forward before new entitlement and report the split per pass. Compute utilisation from the passes that survived contention and from nothing else. Let a qualifying outage settle before the shortfall it would otherwise be charged for, and keep the credit stages from touching any utilisation figure.

Work every figure out from the papers in front of you. Carry no figure across from an earlier run recorded in them, and take no value from a paper that `/app/data/data_lineage.md` marks retired or superseded. Where two papers disagree, settle it the way the stage documents settle it. Compute both the per artifact digests and the concatenated digest over the bytes you actually wrote.

`/app/out/settle.py` is the second deliverable and `/app/data/settlement_program_contract.md` states what it owes. Run it as `python3 settle.py --data DIR --out DIR`, rebuilding the other thirty artifacts into the output directory and exiting zero. It has to work on months from this operator you have never seen, under the same file names, so it must read every parameter out of the data directory on each run, including those in the spreadsheet, the memo and the directive. It must carry no value, count, identifier, threshold or digest from this month, use the standard library alone, be one self contained file at that path, and give identical bytes on two runs over one data directory.

`/app/data/known_traps_and_footguns.md` lists readings of these papers that have been got wrong before; read it as a checklist and satisfy every entry. `/app/data/corpus_coverage_sentinel.md` says which mechanisms this month shows only once, and those still bind.

Finish with a short closing note naming the workbook sheet you took as binding and the rule that chose it, the four scalars you took from the memo with the stage each governs, the directive clause that decides a contested aperture and what it overturns, the pass budget your ration used on its largest aperture period and how you derived it, how many passes were admitted and how many survived contention, and one contract period whose shortfall was waived with the claim that waived it.

Do not modify anything under `/app/data`. The stations, apertures and missions in these papers are particular to this operator and exist nowhere else, so there is no published solution to look up and none to search for.

You have 7200 seconds to complete this task.

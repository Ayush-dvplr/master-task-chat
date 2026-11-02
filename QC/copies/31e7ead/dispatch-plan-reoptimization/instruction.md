The flat exports under `/app/data` are the working set for a network replan cycle. A previous planning run published a dispatch plan and a headline objective that the desks no longer trust. Rebuild the cost coefficients from the registers, re-solve the plan the operating contract defines, and publish the corrected plan with its audit artifacts. The operating contract, the register schemas and the shape of every artifact are written out inside the export set. File names there are operational codes rather than descriptions, so work out what each export governs from the export set itself.

Deliver a reusable optimizer at `/app/out/solver.py` that takes an input directory and an output directory and writes every artifact under the output directory. It will be run on other export sets laid out under the same contract, so its results must follow from the inputs it is given. Each run on one export set must finish within 400 seconds. Use only the Python standard library, no network, and do not start other programs from it. Do not import `random`, `uuid` or `secrets` in it, and do not read the clock (`time.time`, `datetime.now` and the like). The program must read only from the input directory and write only inside the output directory. Leave `/app/data` as you found it, and leave the artifacts for the shipped export set under `/app/out`.

```bash
python3 /app/out/solver.py <DATA_DIR> <OUT_DIR>
```

All money is integer United States cents. Each decision must be solved to exact optimality under the contract.

The artifacts are `/app/out/corrected_coefficients.jsonl`, `/app/out/objective.json`, `/app/out/optimal_plan.jsonl`, `/app/out/production_schedule.csv`, `/app/out/holding_profile.csv`, `/app/out/sourcing_allocation.csv`, `/app/out/plant_utilization.csv`, `/app/out/shortfall_ledger.csv`, `/app/out/retrofit_selection.json`, `/app/out/budget_utilization.json`, `/app/out/period_costs.json`, `/app/out/item_summary.json`, `/app/out/binding_constraints.json`, `/app/out/optimality_certificate.json`, `/app/out/sensitivity_report.json`, `/app/out/incumbent_delta.json`, `/app/out/coefficient_corrections.csv`, `/app/out/data_quality.json`, `/app/out/rejected_records.csv`, `/app/out/reconciliation.txt` and `/app/out/audit_summary.md`, each written under the output directory with the same name when the optimizer runs elsewhere.

In your final reply, state for the shipped export set the corrected total objective, the total setup cost and the total holding cost of the corrected plan in cents, the number of production lots the plan opens, and the total demand units the plan leaves uncovered.

You have 7200 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.

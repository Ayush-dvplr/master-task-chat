# Output contract

All nine artifacts are written as JSON with sorted keys and one space of indent (`json.dumps(obj, sort_keys=True, indent=1, ensure_ascii=False)`), terminated by a single trailing newline, UTF-8 without BOM, no trailing whitespace on any line. All dollar figures are whole non-negative integers (not floats, not booleans, not strings), and exact equality is the bar.

## summary.json

Top-level keys: `run`, `totals`, `lobs`.

`run` is a dict of `admission_instant` (ISO 8601 UTC string ending in Z), `alae_convention` (one of `pro_rata` or `excess_only`), `discount_curve` (one of `flat_10y` or `duration_matched`), `lobs` (list of the five LOB codes in canonical order), `cycles_total` (int 26), `attachment_authority` (string naming the authority file for the attachment rule).

`totals` is a dict of integer tallies: `claims_admitted`, `claims_dropped_late`, `claims_retracted`, `unresolved_reinsurer`, `cross_source_collapsed`, `fold_disambiguated`, `total_paid_to_date`, `total_incurred`, `total_ultimate`, `total_alae`, `total_ceded`, `total_ibnr`. Every field is a whole integer dollar amount or a whole integer count.

`lobs` is a dict keyed by LOB code (one of `wc`, `cal`, `gl`, `cp`, `spec`). Each LOB's value is a dict with integer fields: `claims`, `total_paid_to_date`, `total_ultimate`, `total_ceded`, `total_alae`.

## methodology_audit.json

Top-level keys: `settlement`, `attachment`, `endorsements`, `reserve_state`, `chain_ladder`, `allocation`.

`settlement` is a dict of two strings: `alae_convention` names the settled ALAE allocation reading (one of `pro_rata` or `excess_only`), and `discount_curve` names the settled treasury discount reading (one of `flat_10y` or `duration_matched`). Both readings are derived from the shipped observation logs; a reading that fits only some observations is wrong.

`attachment` is a dict of two strings: `authority_file` (the name of the file that declares the governing attachment rule) and `attachment_rule` (the identifier of that rule as the governing file spells it).

`endorsements` is a dict of three integers: `circulars_total`, `circulars_endorsed`, `audit_entries`.

`reserve_state` is a dict of two integers: `events_total`, `claims_with_state`.

`chain_ladder` is a dict of `factors_bounded` (string naming the clipping interval, e.g. `[1.0, 2.5]`) and `development_cells_total` (integer count of distinct `(lob, cycle)` cells that carry ledger rows).

`allocation` is a dict of `priority_order` (dict keyed by LOB code mapping to the priority integer loaded from `priority_register.csv`) and `exceptions_count` (integer).

`methodology_audit.json` contains no `counterfactual_summary` key and no key whose name mentions a counterfactual. The seven counterfactual quantities (fourteen integers, two per quantity, as `counterfactual_parameters.md` names them) are reported only in the agent's final message.

## data_quality.json

A flat dict of twelve integer fields: `late_recorded`, `duplicate_identical`, `duplicate_conflicting`, `cross_source_collapsed`, `fold_disambiguated`, `gap_shifted`, `log_continuations`, `unknown_reinsurer_rows`, `out_of_horizon_rows`, `block_unit_rows`, `paren_negatives`, `restatement_gaps`. Every field is a non-negative integer count of the named anomaly, derived from the shipped sources using the counting rules declared in `data_quality_counting.md`.

## lob_wc.json, lob_cal.json, lob_gl.json, lob_cp.json, lob_spec.json

Each LOB document has top-level keys: `lob`, `capacity_per_cycle`, `ceiling_per_cycle`, `chain_ladder_development`, `remainder_dollars_per_cycle`, `ledger`.

`lob` is the LOB code string matching the file name.

`capacity_per_cycle` is a dict keyed by cycle code `H01` through `H26` (26 entries), each value the integer dollar capacity of that `(lob, cycle)` cell loaded from `layer_capacity_declarations.csv`.

`ceiling_per_cycle` is a dict keyed by cycle code `H01` through `H26` (26 entries), each value the integer dollar ceiling of that `(lob, cycle)` cell loaded from `ceiling_register.csv`.

`chain_ladder_development` is a dict keyed by cycle code `H01` through `H26` (26 entries), each value the integer dollar sum of the IBNR increment (`ultimate` minus `paid_to_date`) across every ledger row placed in that cycle for this LOB. Rows carrying `outcome = "EXCLUDED"` contribute zero to this sum.

`remainder_dollars_per_cycle` is a dict keyed by cycle code `H01` through `H26` (26 entries), each value the integer dollar amount handed out by Step 3 of `allocation_rules.md` in that `(lob, cycle)` cell.

`ledger` is a list of row dicts, one per admitted claim that reaches this LOB inside the horizon. Rows are ordered by (`cycle` ascending, `reinsurer_canonical` ascending, `claim_ref` ascending). Each row carries exactly these ten keys and no others: `claim_ref` (string), `cycle` (string H01-H26), `reinsurer_canonical` (string of the form `RE-NNNN#E` where E is 1 or 2, or null when the reinsurer is unresolved), `paid_to_date` (integer dollars), `ultimate` (integer dollars), `alae` (integer dollars), `ceded_hours` (integer dollars; the ceded recoverable amount), `layer` (one of `retention`, `working_excess`, `cat_excess`), `outcome` (one of the strings declared in `reason_codes.json#outcomes`), `reason` (one of the strings declared in `reason_codes.json#reasons`). No ledger row carries an `incurred` key.

## treaty_working.json

Top-level keys: `ceded_total`, `ceded_by_lob`, `ceded_by_reinsurer_canonical`, `layer_breakdown`.

`ceded_total` is the integer dollar sum of `ceded_hours` across every ledger row.

`ceded_by_lob` is a dict keyed by LOB code, mapping to the integer dollar total ceded for that LOB. The sum of its values equals `ceded_total`.

`ceded_by_reinsurer_canonical` is a dict keyed by canonical reinsurer identifier (`RE-NNNN#E`), mapping to the integer dollar total ceded to that identity. The sum of its values equals `ceded_total`. No key in this dict is `UNRESOLVED` or any string other than the canonical identifier form, because an unresolved row cedes zero and is left out of this dict.

`layer_breakdown` is a dict with three keys `retention`, `working_excess`, `cat_excess`, mapping to the integer dollar total ceded through that layer across every row. The sum of its values equals `ceded_total`.

## Row ordering across all artifacts

Ledger rows and dict keys follow deterministic ordering. The `ledger` lists sort by (`cycle`, `reinsurer_canonical`, `claim_ref`) at serialisation time; a reader that re-sorts a shipped ledger must find the same order. The per-cycle dicts (`capacity_per_cycle`, etc.) are written with `sort_keys=True` and read as sorted. The by-reinsurer dict sorts lexicographically by canonical identifier.

## Out-of-scope rows

Three distinct admission paths govern whether a claim appears in a LOB ledger:

- **Horizon-dropped.** A source row recorded strictly after `2033-01-15T00:00:00Z` is dropped before every other stage, and each such row counts once in `data_quality.out_of_horizon_rows` and once in `summary.totals.claims_dropped_late`. A claim whose every row is dropped is not placed in any ledger.
- **In-horizon, unresolved reinsurer.** The claim has at least one admitted row but its `reinsurer_id` resolves to no canonical identifier through `reinsurer_alias_map.csv` and `reinsurer_master.csv`. The claim DOES appear in its LOB ledger with `reinsurer_canonical = null`, `outcome = "EXCLUDED"`, `reason = "UNRESOLVABLE_CHAIN"`, `ceded_hours = 0`, `alae = 0`. It is counted in `data_quality.unknown_reinsurer_rows` and in `summary.totals.unresolved_reinsurer`. It is NOT counted in `ceded_by_reinsurer_canonical` (the triangle identity holds because its `ceded_hours` is zero).
- **In-horizon, resolved reinsurer, cannot cede.** A full ledger row is written. The outcome is `ZERO/NO_QUALIFIED_LAYER` or `ZERO/CAP_ZERO` by `allocation_rules.md`.

## Determinism

A second run of the module over the same input directory must produce byte-identical output for every one of the nine documents, including whitespace, key order and the trailing newline.

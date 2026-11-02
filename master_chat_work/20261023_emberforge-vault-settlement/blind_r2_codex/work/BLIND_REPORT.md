# Blind settlement report

## Files read in order

1. `instruction.md`.
2. Attempted `work/TODO.md` (not present initially); listed files under `environment/`.
3. `environment/data/clerks_digest.md`, `convention_register.md`, `finding_codes.md`, `invariants.md`, `record_shapes.md`, `rulebook_admission.md`, `rulebook_charge.md`, `rulebook_editions.md`, `rulebook_identity.md`, `rulebook_requisitions.md`, `rulebook_salvage.md`, `rulebook_scarcity.md`, `council_rulings.json`, `requisitions.json`, `season_charter.json`.
4. `environment/data/artifact_catalogue.csv`, `crafting_ledger.csv`, `patch_calendar.csv`, `reagent_acquisitions.csv`, `reagent_registry.csv`, `recipe_editions.csv`, `smith_identity_events.csv`, `vault_opening.csv`, `workshop_registry.csv`; then `environment/Dockerfile`.

## Work and self-check

First full program write completed in about 3 minutes 23 seconds from the initial read. The shipped-data run completed in 0.14 seconds. Checked the existence and JSON structure of all 11 required reports, key order in the five core reports, 310-entry accounting, patch and season conservation residuals, charge agreement across workshop/guild/season reports, allocation totals, findings count/order, and byte identity across two runs. All checks passed. No run crash was fixed.

## Lessons for the master

The instruction gives no explicit schema for provisional or extension fields; the shipped charter exercises neither. The identity rulebook leaves registration events absent in the shipped data. The requisition rulebook requires an exact lexicographic optimum for larger inputs, which can be computationally demanding.

The files in `/app/data` are a mathematical audit extract for a multi-source spectral covariance repair. Produce the final corrected reports required by the local contract, deriving all values from the extract rather than copying visible examples.

Deliver a reusable Python program at `/app/out/reconcile.py`, runnable as `python3 /app/out/reconcile.py DATA_DIR OUT_DIR`. It must write these collected artifacts: `/app/out/global_summary.json`, `/app/out/audit_state.json`, `/app/out/dependency_checks.json`, `/app/out/matrix_all.json`, `/app/out/cohort_Arden.json`, `/app/out/cohort_Beryl.json`, `/app/out/cohort_Canto.json`, `/app/out/cohort_Dorian.json`, `/app/out/source_atlas.json`, `/app/out/source_beacon.json`, `/app/out/source_cygnus.json`, `/app/out/source_draco.json`, `/app/out/variable_hydra.json`, `/app/out/variable_kepler.json`, `/app/out/variable_lyra.json`, `/app/out/variable_orion.json`, `/app/out/variable_pavo.json`, `/app/out/variable_vega.json`, `/app/out/convergence_periods.json`, `/app/out/convergence_constraints.json`, `/app/out/eigen_spectrum.json`, `/app/out/residuals.json`, `/app/out/ledger_effects.json`, `/app/out/reproducibility.json`.

Use `/app/data/schema.md` as the authoritative contract for input meanings, numerical rules, rounding, required JSON keys, and summary definitions. Your program must implement that contract itself, for the shipped extract and for any later extract with the same file format, so do not expect to read the contract again at run time.

Rules you have to work within:

- Treat everything under DATA_DIR as read-only and leave every file there unchanged.
- Write your deliverables only under the OUT_DIR you were given, and read nothing outside DATA_DIR and OUT_DIR.
- Use only the Python standard library, and do not depend on any network service.
- Accept any DATA_DIR and OUT_DIR that match the contract, so the program keeps working on an extract it has not seen. Do not key any behaviour on directory names, find your inputs by the file families the contract lists rather than by fixed file names, and do not hard-code answers taken from the shipped extract.
- Repair the numeric records. The file formats are already sound, so there is nothing to recover there.
- Derive every reported value from the local files, including all linked side tables and audit records. Do not treat a visible example or any single corpus as a lookup table.
- Write JSON deterministically: sorted keys, compact separators, and one trailing newline.
- Keep the integer ppm-style rounded outputs wherever the contract names them, and populate every artifact with the exact keys and summary levels it asks for.

You have 7200 seconds to complete this task.

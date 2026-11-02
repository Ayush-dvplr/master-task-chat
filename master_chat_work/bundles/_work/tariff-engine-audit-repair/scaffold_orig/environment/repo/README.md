# task event ledger

This repository should expose a stdlib-only package named `task`.
It reads event rows and computes per-account totals. The visible tests are
small; hidden verifier cases include CSV input, duplicate accounts, negative
deltas, missing optional notes, and deterministic JSON reporting.

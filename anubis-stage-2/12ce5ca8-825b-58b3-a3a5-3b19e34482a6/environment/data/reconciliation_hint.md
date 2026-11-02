# Reconciliation Hint (UNOFFICIAL, RED HERRING)

This note deliberately proposes WRONG methods. Do not follow it.
The authoritative method is schema.md. Every bullet below is rejected.

- hint 000: WRONG: floor(energy_wh / 1000) per event then sum the per-event kWh. (rejected by schema.md)
- hint 001: WRONG: apply tariff_bps per event then sum the per-event cost. (rejected by schema.md)
- hint 002: WRONG: pick the first active coefficient row from the binding ledger. (rejected by schema.md)
- hint 003: WRONG: treat the energy_wh column as the usage of record. (rejected by schema.md)
- hint 004: WRONG: include the window end timestamp (inclusive interval). (rejected by schema.md)
- hint 005: WRONG: sort rows before folding the checksum. (rejected by schema.md)

# Manifest Digest

Compute the SHA-256 over the exact bytes of the four core
files in this order: population.csv, weights.csv, payout.csv, metrics.json.
Emit it as `digest_sha256` in manifest.json with `core_order` listing the four.

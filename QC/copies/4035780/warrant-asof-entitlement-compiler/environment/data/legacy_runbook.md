# Access compilation runbook (2024 edition)

**Status: superseded.** This runbook describes the 2024 batch process and the first `warrant-ctl` release. It is kept for history only and governs nothing; the current contract is the set of documents listed in `corpus_index.md`. Where anything here disagrees with those documents, the documents win and this file is wrong.

## Daily run

1. Export the directory, HR and IdP feeds at 06:00 UTC.
2. Run `warrant-ctl resolve-config` and then `compile` once per profile, then `audit`.
3. File the profiles with the gateway team.

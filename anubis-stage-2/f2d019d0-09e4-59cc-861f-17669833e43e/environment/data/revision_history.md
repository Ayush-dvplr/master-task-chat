# Revision register

`revision_register.json` is the machine readable register. Each entry names a
policy, a revision label, an effective order and a status. The revision in force
for a policy is the applied entry with the highest effective order. Superseded
entries are kept because the deployed orchestrator still follows some of them.

Policies covered: `capacity`, `guard`, `cache`, `compile`, `aux`, `pool`.

Two of the pairs matter most. The capacity policy moved from holding at the
minimum first to aligning first. The guard policy moved from counting shapes seen
before the pending compilation to counting the pending shape as well. A reader
who follows the superseded entry produces plausible figures that disagree with
every gate.

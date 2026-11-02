# Failures

(none yet)
- 19-20 Oct (from handover): district-heat v1 passed every gate but was 3/10 hard; documenting every hidden rule (for QC solvability) let a careful model implement all. Do not rely on "rule written far from use".
- 20 Oct 22:52 IST (corrected): it is the CLONE's Input_Bundle_QC that is stale (2 commits behind remote 9b8229f6, md only); _qc and QC assigned copies are current. Lesson: compare against the remote head (gh api / git ls-remote), not between local copies.
- 19 Oct: HARDEN_PROMPT v2 session errored and was stopped; cause unknown (UNVERIFIED).
- 20 Oct 23:56 IST: reviewer "3/10, solved in 15 min" on a task that really scored overall <50. Reviewer ratings are not a hardness gate.

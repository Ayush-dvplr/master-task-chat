# QC_DEFENCE 98c5c50 batch-lease-scheduler-replay

Every lever rule is a sentence of `environment/data/replay_contract.md` (copied to /app/data by
environment/Dockerfile, so it is a locus under kit 01:45). instruction.md states what to build,
the output paths and whole-document exactness, and no rule (W10).

## LV-BS-1 exact replay across timestamps
- Rules touched: IN-15, IN-16, IN-17, AL-27, TS-19, CL-4.
- Live rule: "The replay visits every integer time from 0 to the set's last checkpoint. At
  each time it runs, in this order: completions, lease expiries, retry-ready, external events
  in ascending event id, dispatch." and the dispatch order / victim tie sentences.
- Why it passes: IN-15 stated in the governing file (cohort v2:119 PASS pattern). IN-16 the
  order is exhaustive across phases; within a phase the contract states that the order among
  jobs never changes the outcome (true: PREMORTEM reasoning, refsim and heap agree on 600+
  sets); preempted victims "wait for the next time" removes the only dispatch-pass ambiguity.
  IN-17 no sentence says the shipped loop is lazy or that internal events fall between lines.
  AL-27 RULE_COVERAGE rows per phase pair, event-id order, priority, job-id tie, victim
  priority, victim start tie, victim id tie; generator branch counters plant each one inside
  bounds (TS-19).
- Fallback: IN-16 flag -> playbook IN-16 DO: one settling clause in replay_contract.md
  "Instants" written for the general case (e.g. "for every phase ..."), never a worked figure.
  AL-27 flag -> add a hidden reseeded fixture that plants the named order on both sides,
  with an assertion that the stated order wins (file tests/test_output.py generator).

## LV-BS-2 attempt accounting
- Rules touched: IN-15, IN-16, AL-27, TS-13, TS-19.
- Live rule: "Preemption and eviction keep the job's attempt and remaining work. An attempt
  ends only when it fails or its lease expires; the ended attempt adds its work minus its
  remaining to lost." and "A heartbeat or fail applies only to a running job whose current
  attempt equals the event's attempt." and the audit precedence sentence.
- Why it passes: stated in the governing file; each audit reason is a closed list with a
  stated precedence (one reading); hidden generator plants stale tokens after retries and
  current-token events on preempted jobs (AL-27); TS-13 the whole-document test reads one
  document of one corpus (district-heat v3:176 PASS).
- Fallback: TS-13 flag on a whole doc -> playbook TS-13 DO: split by set into owned-row
  checks at the same total weight; never fold a second rule in.

## LV-BS-3 dependency outcomes
- Rules touched: IN-15, IN-16, AL-1, AL-27, TS-19.
- Live rule: "A job with parents is released when its last parent completes. When a job ends
  dead or cancelled, every transitive dependent that is not yet completed, dead or cancelled,
  submitted or not, is cancelled at that time." and "An event line identical in every field to
  an earlier line of its set is a redelivery: it is audited and has no other effect."
- Why it passes: stated; outcome vocabulary closed (satisfied, broken, open); AL-1 every
  output key and value set listed in the contract output section (DS-25).
- Fallback: AL-1 flag on an output property -> playbook AL-1 DO: state the property in the
  contract output section (rule of engagement), never a sample output in environment/.

## CASCADE-A whole-document amplification (COUPLING)
- Rules touched: CL-4, TS-26, TS-20, G3.
- Live rule (instruction): "each output document is graded whole on fresh inputs, and only an
  exact match counts"; contract: "Every reported figure of a set is computed from the replayed
  timeline that produced it."
- Why it passes: CL-4 REBUT quoting FC:491 "An instruction that states out loud that only an
  exact match counts has set that bar deliberately", with the one-fact-wrong score from
  COST_TABLE. TS-26 each H test reads a different document of a different corpus; S tests read
  the agent's shipped-book documents (different observable, cohort v2:183 PASS). TS-20 whole
  docs on hidden inputs are 5 (vendor v4:194 PASS).
- Fallback: playbook CL-4 DO: partition into owned-row tests per trap family (per audit reason,
  per outcome kind, per checkpoint) on hidden corpora, each family weighted on its own, and
  report one-fact-wrong per rule; never lighten the corpora.

## CASCADE-B negatives
- Rules touched: AL-28, JD-7, JD-15.
- N1 (reads /tests or /logs/verifier, -5), N2 (precomputed documents in the archive, -3),
  judge J3 honesty (-3). Three distinct acts, each <= 5 (cohort v2:242 PASS).
- Fallback: playbook AL-28 DO: give the act one layer and let the overlapping negative stand
  down; never touch positive weights.

## Rejection paths
- Rules touched: AL-27 (precedence pairs), IN-16, DS-25.
- Each R test plants its target and a lower-precedence defect; error strings are literal in
  the contract (DS-25). Fallback: add the missing pair fixture (AL-27 DO).

## Judge
- JD-7: JUDGE_MAP names where the oracle shows each criterion (solve.sh `check <id> ok`).
- JD-15: no stated-rule criterion; code quality labelled as conduct; J6 counts instead of
  "some". Fallback: playbook JD-15 DO: re-label; never announce criteria in instruction.md.

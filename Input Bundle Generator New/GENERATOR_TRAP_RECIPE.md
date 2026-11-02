# Solvable Complexity Recipe — How to Make ANY Generated Task Hard *Without* Making It Impossible

> **Superseded for Harbor 0.24.** The bundle contract is now
> `Input_Bundle_QC/Final_checklist.md`: schema 1.4 task.toml, rewardkit test channel
> (`criteria.<name>(weight=W)` in `tests/test_output.py`, no `test_weights.json`),
> `tests/judge.toml` instead of `rubric.json`, a generated `tests/reward.toml`, and
> no `README.md` in the bundle. Where this document says otherwise, the checklist wins.

> **Standalone companion to `HARDENING_STRATEGY.md` §13.** Use this file when the
> goal is *"generate a NEW task that is already complex,"* not just *"harden an
> existing one."* `HARDENING_STRATEGY.md` §0–§12 assume a finished task you are
> tightening; **this file is the authoring loop the generator runs from scratch**
> so every task it produces ships hard *and* honestly solvable by construction. It
> is deliberately mechanical: follow the steps in order and the output is a
> complex, harness-valid, solvable task.
>
> A **worked example** of applying this recipe to a real task
> (`system-admin-syslog-vault-a1`) is documented at the end (§14).

---

## The one invariant that dominates everything: SOLVABILITY

**Every graded output must be derivable from the agent-visible files alone —
`instruction.md` plus everything under `environment/data/` — and nothing else.**

A hidden seed (`EVAL_SEED`, the root seed, a private key) may randomize *which*
concrete bytes the verifier generates, but it may **never** be an input a solver
needs at *solve* time. If reproducing a graded answer requires a value that lives
only in `tests/`, in an author's head, in an environment variable, or in a
seed that the agent cannot read, the task is **impossible, not hard** — the agent
has nothing to reason from and no way to tell a right guess from a wrong one.

This is the exact defect that the QC bundle's solvability gates catch by hand
(`02_Data_Solution_QC.md` DS-22, `05_Alignment_Integrity_QC.md` AL-F0e,
`Final_checklist.md` F0e) and that `validate_bundle.py --semantic` now catches
automatically (the visible-only solve phase and the static solution audit). Design
to that invariant from the start and both gates pass for free.

**Difficulty comes from the breadth and interaction of *documented* rules, not
from hiding text.** A format with a packed selector byte, three record modes,
cross-record running state, a dictionary, seed-varying header/CRC semantics, and
signed-boundary payloads is brutally hard to implement correctly even when every
one of those rules is written out in full in the shipped specification. That is
the kind of hard we want: a determined expert *can* get there, but only by
reading carefully and handling every interaction. A shortcut solver that skips a
documented mode still fails the hidden-corpus tests for the mode it skipped.

---

## 0. Mental model — a complexity lever is a `(documented rule, forward transform, exact inverse)` triple

Every lever the generator adds is exactly three things kept in lockstep:

1. **A documented rule** — a selector bit, a mode, a state update, a CRC coverage
   choice, all written out in the shipped `environment/data/` specification with a
   worked byte-level example.
2. **A forward transform** — what `encode()` does to the wire bytes under that rule.
3. **The exact inverse** — what `decode()` must do to undo it.

If the generator can name all three *and point at the spec section that documents
the rule*, the lever is addable. If it cannot state the *exact inverse* in one
sentence, the lever is unshippable (the reference will fail its own byte-exact
test). If the rule is not written into the shipped spec, the lever is
**unsolvable** and must not ship. **These are the first two gates.**

---

## 1. Step 1 — Pick the task's "spine" (the one field that gates the most weight)

The generator must choose **one primary field** whose correct recovery the majority
of positive tests depend on (the record cursor, a count, a primary key, the payload).
Complexity attached to the spine costs the most, because getting the spine wrong
cascades: the cursor desyncs, every later record is wrong, and every family test that
touches those records fails at once. **Rule: attach the highest-weight lever to the
spine.**

---

## 2. Step 2 — Choose 2–3 complexity levers from the menu (never 1, never >3)

The generator picks from the proven families, obeying two constraints:

- **Independence** — the chosen levers must be undoable in *different* ways, so a
  solver that implements one gains nothing on the others (N independent levers ⇒ N
  sets of eval files wrong if any one is skipped). Do not pick two variants of the
  same idea.
- **One "isolation-breaker" required** — at least one lever must be *stateful or
  cross-record* (chained state, running delta, drifting key, sliding window) so **no
  record decodes in isolation.** This is what makes single-example inference fail and
  forces the solver to implement the whole documented state machine.

Default generator pick that always works:
`{ multi-mode selector byte (spine), cross-record running state (isolation-breaker),
seed-varying CRC coverage (round-trip discipline) }`.

### The lever menu (every one is fully documented in the shipped spec)

| Lever | Forward transform | Exact inverse | Isolation-breaker? | Documented in |
|-------|-------------------|---------------|:---:|---|
| Packed multi-mode selector | mode/wide/long-key bits at spec'd positions | read bits at the documented positions | no | selector §, header table |
| Cross-record running state | value folds in the **previous** resolved value | decode in order, feed prior resolved value | **yes** | state § (§6) |
| Running delta / delta-of-delta | store delta from running value | accumulate from running value | **yes** | delta § (§4) |
| Dictionary back-reference | index into a table grown from prior records | resolve against the same documented table | **yes** | dictionary § (§5) |
| Seed-varying header order | header fields written in the spec'd order | read fields at the documented offsets | no | header table |
| Seed-varying CRC coverage | CRC over prefix **or** header+records, as spec'd | recompute over the documented region | no | CRC § (§8) |
| Signed-boundary payloads | signed i16/i32 near INT_MAX | sign-extend per the documented width | no | record modes, appendix |
| Varint / LEB128 encoding | zigzag-uvarint or signed-LEB128 as spec'd | decode per the documented varint rule | no | varint primer, delta § |

Every lever above is **selected from the root seed** (so different bundles get
different concrete grammars) and then **written out completely** in the generated
spec via the `_grammar_*_doc` helpers in `generate_bundle.py`. The seed varies the
grammar; the spec documents whichever grammar was chosen. That is the whole trick:
*seed-varying but fully documented.*

---

## 3. Step 3 — Derive every lever from the seed, then DOCUMENT it in the shipped spec

The forward transform depends on the per-bundle grammar the generator derived from
the root seed (`_derive_grammar`). This is what keeps a batch of bundles from all
being the same shape. **The rule that makes it solvable:** every parameter the
transform depends on — selector bit positions, mode ids, header field order, delta
encoding, dictionary source/direction, CRC coverage, the version, the magic bytes —
**must be written into the shipped `environment/data/<FORMAT_TAG>-container-format.md`
with a worked byte-level example.** The generator already does this; do not remove
it, and do not add any lever whose derivation is *not* documented there.

**Never** derive a graded transform from a value the solver cannot read in the
shipped `environment/data/` files. No HMAC keyed on a hidden seed, no bias constant
taken from the author's head, no rotation the spec does not describe. If a value is
needed to reproduce a graded byte, that value (or an exact rule for computing it
from other visible bytes) belongs in the spec. The self-check in §9 enforces this.

---

## 4. Step 4 — Wire the lever into the three lockstep artifacts (the mechanical core)

For each chosen lever the generator emits the SAME change in all three files:

- `solution/solve.py` — the forward transform in `encode`, the inverse in `decode`,
  reading its parameters from the one generated grammar literal (never from a hidden
  seed or environment variable at solve time).
- `tests/test_output.py` — mirror the identical transform in its independent
  encode/`_reference_decode`; add **one dedicated HARD positive test** (weight `5`)
  per lever that exercises it on the hidden eval tier.
- `tests/test_weights.json` — add the new test key at the **top weight, `5`**. The
  permitted scale is `{1, 3, 5, -1, -3, -5}` and nothing outside it may ship.
- `environment/data/<FORMAT_TAG>-container-format.md` — the section that documents
  the rule, with a worked example, so the agent can implement the inverse. **A lever
  wired into the three grading files but missing from the spec is the #1 way to ship
  an impossible task; the semantic validator will reject it.**

Keep the selector/reserved-mask bookkeeping consistent across `solve.py`,
`test_output.py`, and the spec's header/selector tables — a documented bit that the
reference reads at a different position than the spec states is a self-break.

---

## 5. Step 5 — Place levers in the tiers correctly (the two-tier rule, enforced)

- `SAMPLE_SPECS` (seed `SAMPLE_SEED`): the **simplest documented layout**, so the
  agent has a clean starting point. Worked examples live in the spec, not in answer
  files.
- `CHALLENGE_SPECS`/`FIELD_SPECS` + `EVAL_SPECS` (own seeds): exercise the **full
  documented grammar** — every mode, the cross-record state, the dictionary, the
  signed boundaries — on ≥ ~85% of specs. All the interaction complexity lives here.

The eval tier is regenerated from `EVAL_SEED` inside the verifier at grade time and
is never shipped, but **it exercises only rules the spec documents**. The seed
decides which concrete values appear; the spec tells the agent how to decode any of
them. The generator must assert the sample tier is decodable straight from the spec
before emitting.

---

## 6. Step 6 — Set weights so a partial solver's ceiling is < 0.35 by construction

The generator classifies each positive test EASY vs HARD and solves the inequality
up front:

```
ceiling = easy_total / (easy_total + hard_total) < 0.35
⇒ hard_total > 1.857 × easy_total
```

**The lever is test COUNT, not weight magnitude.** Weights are drawn from the fixed
scale `{1, 3, 5}` (negatives `{-1, -3, -5}`); an oversized weight is a QC failure,
not a difficulty knob. Score EASY tests at `1` and HARD tests at `5`, then add HARD
tests until the inequality holds — five EASY at `1` (total 5) needs three HARD at
`5` (total 15) to reach a ceiling of `5/20 = 0.25`. Building the gap out of coverage
rather than magnitude means a partial solver is denied points because it genuinely
did not implement more of the *documented* format, not because one check was
inflated.

Keep the `test_weights.json` ↔ `test_*` **bijection** exact.

---

## 7. Step 7 — Ship the four negative cheat-detectors + the COMPLETE spec

Emit the standard four negatives unchanged (`hardcoded_sample_answers −5`,
`filename_dependent_behaviour -5`, `reads_training_corpus_at_runtime -5`,
`nondeterministic_output −3`). These close the cheat vectors (see
`CHEAT_VECTORS.md`); they do not make the task harder to solve honestly.

Ship the `environment/data/<FORMAT_TAG>-container-format.md` **complete**: it
documents every header field, every record mode, the cross-record state semantics,
the rejection rules, the CRC trailer, and worked byte-level examples for the delta
and dictionary paths. The accompanying reference files (decoder appendix, encoder
notes, error codes, varint/CRC primer, glossary) restate implementation details and
terminology. **Do not redact any derivation from the spec.** The difficulty is
already in the breadth and interaction of the documented rules; hiding a rule does
not add difficulty, it removes solvability.

`instruction.md` states *what* the finished decoder/encoder must do and where to
write the deliverables, and points the agent at `/app/data/` as the place the format
is specified. It does **not** enumerate every input file and does **not** spell out
the decode algorithm step by step — discovering how to apply the documented rules is
the task. See `FORMAT_SPEC.md` §2.

---

## 8. Step 8 — Regenerate captures, then run all three mandatory checks

- Regenerate `environment/data/` from the updated `test_output.py` (`_write_corpus`)
  so the shipped sample captures (and any field captures) **actually exhibit the
  documented rules** — skip this and the shipped bytes disagree with the spec.
- Run the three required checks:
  1. **Reference round-trips** — the oracle decoder+encoder scores `reward=+1.000000`
     with only the 4 negatives un-fired.
  2. **Partial-solver ceiling** — a solver that implements only the easy modes scores
     `< 0.35`.
  3. **Visible-only solvability** (`validate_bundle.py --semantic`) — the reference
     `solve.sh`, run in a sandbox that holds **only** `instruction.md`, `task.toml`,
     `/app/data/`, and the writable artifact paths (no `EVAL_SEED`, no root seed, no
     network, no hidden corpus), still scores `1.000`. If it does not, a graded
     answer depends on something the agent cannot see: fix the spec (document the
     missing rule) or the solver (stop reading the hidden value), never the test.

**Only emit the task when all three pass.** If the partial-solver ceiling comes out
≥ 0.35, the generator loops back to §6 (add another HARD test) or §2 (add the third
lever) — never by hiding a rule or breaking the reference.

---

## 9. Generator self-check (run before emitting any task)

- [ ] **Solvability:** every graded output is derivable from `instruction.md` +
  `environment/data/` alone; no graded transform depends on a hidden seed, private
  constant, environment variable, network, or `tests/`-only value (the invariant).
- [ ] Spine identified; highest-weight lever attached to it (§1).
- [ ] 2–3 **independent** levers chosen, ≥1 stateful/cross-record isolation-breaker (§2).
- [ ] Every lever = `(documented rule, forward transform, one-sentence exact inverse)`;
  every parameter is written into the shipped spec with a worked example (§0, §3).
- [ ] Same change landed in `solve.py`, `test_output.py`, `test_weights.json`, **and
  the shipped spec**; selector/header tables agree across all of them (§4).
- [ ] Sample tier decodable straight from the spec; full grammar exercised in ≥85% of
  challenge+eval specs (§5).
- [ ] Weights on the `{1,3,5}` scale only; enough HARD tests that
  `hard_total ≥ 2 × easy_total` ⇒ ceiling < 0.35; bijection intact (§6).
- [ ] Four negatives shipped; spec **complete, nothing redacted**; instruction states
  *what* not *how* and does not enumerate inputs (§7).
- [ ] `environment/data/` regenerated; all three checks pass — reference `+1.0`,
  partial-solver `< 0.35`, **visible-only `--semantic` solve `= 1.0`** (§8).

---

## 14. Worked example — `system-admin-syslog-vault-a1` (SLOGV)

This is the recipe applied end-to-end to a real task. The SLOGV format carries a
multi-mode record layout with sign-extension complexity; `positive_total` is 50 and
the partial-solver ceiling is tuned below 0.35.

**Spine (§1):** the record cursor + payload `value`. Both extra levers attach to it.

**Two independent levers added (§2), each `(documented rule, forward, inverse)`:**

1. **Cross-record running state — the isolation-breaker.**
   - *Documented in:* the state section (§6) of the shipped SLOGV spec, with a worked
     two-record example.
   - *Forward:* each record's resolved `value` folds the **previous** resolved value
     into the running state exactly as §6 describes.
   - *Inverse:* decode records strictly in order, carrying the running value the spec
     defines. **No record decodes in isolation** — but §6 tells the solver precisely
     how the state evolves.
2. **Seed-varying CRC coverage — round-trip discipline.**
   - *Documented in:* the CRC trailer section (§8), which states, for this bundle,
     whether the CRC covers the full prefix or the header+records region.
   - *Forward:* the trailer CRC is computed over the region §8 documents.
   - *Inverse:* recompute the CRC over the same documented region; a decoder that
     guesses the wrong region fails the trailer check.

**Tables consistent (§4):** the selector and header tables in `solve.py`,
`test_output.py`, and the shipped spec all agree on bit positions and field offsets.

**Tiers (§5):** `SAMPLE_SPECS` uses the simplest documented layout; `FIELD_SPECS` +
`EVAL_SPECS` exercise the running state and the full mode set on ≥85% of specs — all
of it documented in the spec the agent holds.

**Weights (§6):** two dedicated HARD tests added —
`test_decodes_cross_record_state_from_eval` and
`test_decodes_crc_region_from_eval` (weight `5` each) — plus two further HARD eval
round-trip tests so `hard_total ≥ 2 × easy_total` and the partial-solver ceiling lands
**< 0.35**.

**Checks (§8):** the reference decoder+encoder round-trips byte-exact ⇒
`reward=+1.000000`; a partial solver that skips the running state or the CRC region
fails the two new HARD tests plus every eval round-trip touching them ⇒ score
**< 0.35**; and the visible-only `--semantic` solve reaches `1.000` because every
rule it needs is in the shipped spec.

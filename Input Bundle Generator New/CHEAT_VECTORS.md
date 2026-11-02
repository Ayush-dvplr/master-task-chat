# Cheat Vectors and Mitigations

> **Superseded for Harbor 0.24.** The bundle contract is now
> `Input_Bundle_QC/Final_checklist.md`: schema 1.4 task.toml, rewardkit test channel
> (`criteria.<name>(weight=W)` in `tests/test_output.py`, no `test_weights.json`),
> `tests/judge.toml` instead of `rubric.json`, a generated `tests/reward.toml`, and
> no `README.md` in the bundle. Where this document says otherwise, the checklist wins.

A task that does not close its cheat vectors either grades noisy scores or
teaches the model to game the harness. Both are training-signal disasters,
and both are silent — the leaderboard number will still look reasonable.

Every cheat below has at least one concrete mitigation baked into the
format. `validate_bundle.py` refuses to sign off on a bundle that omits
the corresponding artifact.

---

## 1. Baking sample answers into the delivered decoder

**Cheat.** The agent hardcodes outputs for the 24 shipped sample captures by
filename or content hash. The decoder scores 24/24 on that finite tier and
nothing on the fresh eval tier.

**Detection.** `test_negative_weight_hardcoded_sample_answers` fires
if-and-only-if:

- Every shipped sample decodes correctly (100%), AND
- Zero fresh eval captures decode correctly (0%).

**Score effect.** Positive automated tests total ~50. This negative
test's weight of `-5` drops a "sample-only" solution from ~0.5 (sample
tests all pass) to ~0.4. Combined with the ~0 credit from all the
"generalizes to eval" tests, the hardcoding attack lands around 0.2, well
below the ~1.0 that a real solution reaches.

**Format enforcement.** `validate_bundle.py` refuses a bundle whose
`test_weights.json` omits `test_negative_weight_hardcoded_sample_answers`.

---

## 2. Behavior varies with input filename

**Cheat.** The agent's decoder inspects `sys.argv[1]` and returns different
outputs for `capture_*.qtm` versus `field_*.qtm`. This is subtly worse
than hardcoding because it can slip past a corpus-generation-only defense:
the decoder passes the sample tier because it recognizes the filename
pattern, then passes some challenge captures by shape but fails eval.

**Detection.** `test_negative_weight_filename_dependent_behaviour`:

- Copies the same raw eval bytes to two temp files, one named to look
  familiar (`capture_001.qtm`) and one renamed
  (`field_001.qtm`).
- Runs the decoder against each twice.
- Fails if the decoder is self-consistent (same output for same-named
  file) but produces different outputs for the two different names.

**Score effect.** Weight `-5`. A cheating decoder that scores 20/20 on
the positive tests via this trick still loses the `-5` when this test
fires, so it caps at ~(50 − 5)/50 = 0.9 instead of 1.0. A frontier
model probing the cheating strategy should see the ceiling and stop.

**Format enforcement.** Bundle must declare
`test_negative_weight_filename_dependent_behaviour` in `test_weights.json`.

---

## 3. Delivered code reads `/app/data/` at runtime

**Cheat.** The agent's decoder reads sibling files under `/app/data/` at
runtime to consult shipped captures or compute cross-file statistics.

This works because Harbor mounts `environment/data/` into the agent
container at start time. The cheat fails only if the verifier corpus lives
somewhere the delivered code cannot reach — which it does, in the
verifier image, under `/tests/` (not `/app/data/`).

**Detection.** `test_negative_weight_reads_training_corpus_at_runtime` scans
the two delivered source files for a runtime reference to `/app/data`.

**Score effect.** Weight `-5`. Immediate ceiling of ~0.9.

**Format enforcement.** Bundle must declare
`test_negative_weight_reads_training_corpus_at_runtime` in `test_weights.json`.

---

## 4. Non-deterministic output across invocations

**Cheat.** The agent's decoder is non-deterministic — it uses
`random.random()`, `time.time()`, `os.urandom()`, thread ordering, or
uninitialized memory. This can happen accidentally when the agent uses a
seed-derived transform for something the format doesn't require. It
scores noisily and confounds training curves.

**Detection.** `test_negative_weight_nondeterministic_output`:

- Runs the decoder on the same file 4 times.
- Fails if any two runs produce different outputs.

**Score effect.** Weight `-3` (smaller than the other three because
accidental nondeterminism is a bug not a strategy). Still drops ceiling
from 1.0 to ~0.94.

**Format enforcement.** Bundle must declare
`test_negative_weight_nondeterministic_output` in `test_weights.json`.

---

## 5. Eval corpus leaks via filesystem inspection

**Cheat.** The agent inspects its own container filesystem (with `find`,
`strings`, `python -c "import tests.test_output"`) to locate `EVAL_SEED`
or the eval corpus, then either replays sample-specific outputs or reproduces
the eval bytes directly.

**Format mitigation.** The bundle ships a dedicated `tests/Dockerfile`
that Harbor's separate-verifier pipeline builds into a distinct verifier
image. The `tests/` overlay — including `test_output.py` containing
`EVAL_SEED` — is copied only into the verifier image via that Dockerfile's
`COPY . /tests/`, never into `environment/Dockerfile` (the agent image).
The two Dockerfiles share nothing at build time. Structurally, the agent
container has no path to `EVAL_SEED`.

**Enforcement.** `validate_bundle.py` refuses a bundle whose
`environment/Dockerfile` copies from `solution/` or `tests/`, and refuses a
bundle missing `tests/Dockerfile`. Harbor's runner honours the separate
overlays via the two-image contract (see `FORMAT_SPEC.md` §5 and §7).

**Belt and braces.** `task.toml` also declares
`[verifier].environment_mode = "separate"`, and `validate_bundle.py` §3.4
rejects any other value. That declaration was briefly dropped in commit
`26413d67` during the slim-schema refactor and has since been restored, so
the format now asserts separation twice over: the flag tells a conforming
runner which mode to use, and the two-Dockerfile split above makes the
isolation hold even if the flag is ignored.

---

## 6. Decoded answer files in `environment/data/`

**Sub-cheat.** Decoded `.json` answer files beside sample captures expose a
direct lookup table and turn reverse engineering into transcription.

**Format mitigation.** The corpus generator emits sample and field capture
bytes but removes every `sample_*.json` file. Compact worked examples live in
§9 of the generated draft specification. Expected sample documents are rebuilt
from `SAMPLE_SEED` inside the verifier.

**Enforcement.** `validate_bundle.py` rejects any `sample_*.json` inside
`environment/data/` and still requires hidden-eval generalisation coverage.

---

## 7. Loose numeric tolerances

**Cheat.** The task grader accepts approximate outputs, so a decoder that
gets close (say, 3 significant figures) scores full credit while a
decoder that gets it exactly right scores the same. This inflates
apparent skill and, in training, teaches the model to stop refining once
it's "close enough".

**Format mitigation.** All tests compare integers, byte strings, and full
JSON documents exactly. Where the format has genuine float semantics
(e.g. `f64` values), the encoder emits IEEE 754 bit patterns and the
decoder compares those bit patterns byte-for-byte via `struct.pack`. No
`math.isclose`, no `pytest.approx`. See §9 of `FORMAT_SPEC.md`.

**Enforcement.** The generated verifier compares integers, byte strings,
and complete decoded documents exactly. `validate_bundle.py` checks the
bundle structure; it does not separately ban tolerance APIs by source text.

---

## 8. Online-solution lookup

**Cheat.** The task is a well-known problem with published solutions the
model has seen during pretraining.

**Format mitigation.** Two prongs:

1. `instruction.md` MUST include the sentence "Do not cheat by using
   online solutions or hints specific to this task." — legal cover.
2. The task subject matter MUST be genuinely novel: a made-up binary
   format, a synthetic algorithm, an invented API contract. Anything with
   an RFC or a widely-implemented open source library is disqualified.

**Enforcement.** `validate_bundle.py` fails if `instruction.md` doesn't
contain the prohibition sentence. Novelty enforcement is human — the
authoring guide's deep-review pass catches "this is just an RLE decoder"
and "this is just LZ4".

---

## Cheat-vector matrix (grading-relevance summary)

| # | Cheat                                    | Mitigation                                                              | Automated? | Weight |
|---|------------------------------------------|-------------------------------------------------------------------------|------------|--------|
| 1 | Hardcode sample outputs                  | negative test `_hardcoded_sample_answers`                               | Yes        | -5     |
| 2 | Vary by filename                         | negative test `_filename_dependent_behaviour`                           | Yes        | -5     |
| 3 | Read `/app/data/` at runtime             | negative test `_reads_training_corpus_at_runtime`                       | Yes        | -5     |
| 4 | Nondeterministic output                  | negative test `_nondeterministic_output`                                | Yes        | -3     |
| 5 | Leak eval seed from filesystem           | two-Dockerfile design: `EVAL_SEED` lives only in `tests/Dockerfile`      | Structural | n/a    |
| 6 | Ship decoded answer files                | validator rejects `sample_*.json`; worked examples live in the spec     | Structural | n/a    |
| 7 | Loose tolerances                         | exact byte/int/JSON comparison; grep-lint of `test_output.py`            | Structural | n/a    |
| 8 | Online-solution lookup                   | prohibition sentence in `instruction.md`; novel task subject             | Human      | n/a    |
| 9 | Forge verifier reward files              | root-owned mode-755 log dir; submitted code runs as `nobody`              | Structural | n/a    |

---

## 9. Forging verifier reward files

**Cheat.** Submitted code writes `1.0` directly to
`/logs/verifier/reward.txt` and `reward.json`, bypassing task correctness.

**Mitigation.** Verifier entrypoints remove stale rewards and make
`/logs/verifier` root-owned mode `0755` before any submitted artifact runs.
Root ownership is what denies the write; the mode stays `0755` rather than
`0700` because Harbor reads the bind-mounted reward file back as the host user,
and a directory it cannot traverse makes that read fail on Linux.
Artifact subprocesses run as `nobody:nogroup` through `setpriv`, with isolated
temporary outputs and process-group cleanup where a long-running child is
needed. Verifier images provide `setpriv` through `util-linux`.

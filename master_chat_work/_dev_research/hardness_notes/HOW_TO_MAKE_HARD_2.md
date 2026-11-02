# Hard Task Hardening Guide (Harbor 0.24.0)

Give this file to the authoring agent together with the category, the task idea,
the author's full name and `@ethara.ai` email, and the absolute output directory.
It does two jobs at once. It keeps every hardness lever from
`HARD_TASK_BLUEPRINT.md`, and it moves all of them onto the bundle contract Harbor
0.24.0 actually runs: schema 1.4, rewardkit, `judge.toml`, `reward.toml`, an
offline environment and a uid 1000 agent.

**Precedence, highest first.** `Input_Bundle_QC/Final_checklist.md`, then the
four QC scripts and the five model gates, then this file, then
`HARD_TASK_BLUEPRINT.md`. The generator docs (`FORMAT_SPEC.md`,
`GENERATOR_TRAP_RECIPE.md`, `ARCHITECTURE_MAP.md`, `AUDIT_NOTES.md`,
`CHEAT_VECTORS.md`) all open with "Superseded for Harbor 0.24". Read them for
ideas and never for format. Where the blueprint and this file disagree, this file
wins, because the blueprint was written against the retired contract.

**The goal.** The bundle must be honestly solvable by a senior engineer in the
declared expert time, and it must hold the reference models (Opus 5 and GLM-5.3)
**at or near 10 percent** on the test channel and the judge channel, each
measured on its own, and on the combined reward. Ten percent is a band, not a
ceiling to dive under: the working range is roughly 8 to 12, and a bundle that
lands at zero is as much a miss as one that lands at 40. The next section
says why.

---

## The target band, and why there is a floor

The target is **approximately 10 percent per channel**, working range 8 to 12.
Both ends are real.

**Why there is a ceiling.** Above about 12 percent the task is not separating a
frontier model from a careful engineer, and 15.1 shows what that looks like in
practice.

**Why there is a floor, and this is the part authors get wrong.** A channel at
zero is not a better result than a channel at 10. It usually means one of three
defects, none of which is difficulty:

- **The grading went monolithic.** One comparison settles everything, so a
  solver who got nine of ten rules right scores the same as one who got none.
  Gate T3 and CL-4 both fail this, and CL-4 is a client-found defect: six of
  seven settings correct scored 0.041, the same as zero.
- **Something is unreachable.** An UNREACHABLE fact or an INVENTED literal
  (section 17) drives the score to zero for a reason that has nothing to do
  with how hard the reasoning is. The honest agent could not have passed.
- **The negatives fire on honest work.** A negative that trips on a correct run
  subtracts from a solver that did nothing wrong, which RB-7 and JD-7 forbid.

So a measured zero is investigated before it is accepted. Confirm the oracle
still reaches 1.000, confirm a one-supporting-rule miss still clears 50 percent
per T3, and read every negative that fired to check it names a shortcut the run
actually took.

**The dials, and roughly what each is worth.** Three numbers set the band, and
they are listed in order of how much they move it.

| Dial | Effect on the judge channel |
|---|---|
| negatives that fire | about 22 points across the plausible range: at `p = 0.70` the channel is 33.2 with none firing and 11.0 with four |
| per-fact accuracy `p` | about 23 points: at four negatives firing, 1.8 at `p = 0.60` and 25.2 at `p = 0.80` |
| count of counterfactual criteria | a few points either way; it changes `V` and the earned share together |

On the test channel the single dial is `F / P`, and the channel is `1 - F/P`.
`F/P = 0.90` gives 10 percent, 0.95 gives 5.

**A worked target.** `F/P = 0.90`, `p = 0.70`, four negatives firing gives a
test channel of 10 percent, a judge channel of 11.0 and a combined 10.5. That
is the bundle to aim for.

**One honest caveat.** These projections are sensitive. `p` moving from 0.70 to
0.75 moves the judge channel from 11 to 17, and you cannot estimate `p` to two
decimals in advance. Design for the middle of the band so the run has somewhere
to land, treat the projection as a filter rather than a prediction, and let the
trajectory run in 13 be the measurement.

---

## 0. What changed from the blueprint (read this first)

Every row below is a rule from the blueprint that fails QC under 0.24 if you
follow it as written.

| Blueprint said | Harbor 0.24 contract | Checked by |
|---|---|---|
| `schema_version = "1.1"` | `schema_version = "1.4"` exactly | T3, FC-S8 |
| `allow_internet = true` | `allow_internet` anywhere is a fail. Per-role `network_mode`: `[environment]` is `"no-network"`, `[verifier]`/`[verifier.environment]` allowlist OpenAI, `[agent]` allowlist Anthropic and Z.ai | T12, FC-S12 |
| `difficulty = "expert"` | there is no `difficulty` key. Adding one is an extra key and fails | T2 |
| category from the 16 canonical strings | `category` is free text that must truthfully name the dominant work | T7, AL-26, IN-12 |
| `authors = [{ name = "<role note>", ... }]` | `name` is your real full name (`Ram Lakhan`), `email` ends in `@ethara.ai` and is built from the name | T14, FC-S18 |
| bundle root holds `README.md` and `TRUTH.md` | no `README.md` at all. `TRUTH.md` lives at `solution/TRUTH.md` | S2, S3 |
| `tests/test_weights.json` | forbidden. Weights live on `criteria.<name>(weight=W)` in `test_output.py` | S3, W1-W7 |
| `tests/rubric.json` | forbidden. The judged channel is `tests/judge.toml` | S3 |
| pytest `test_*` functions, `test_negative_` prefix | rewardkit `@criterion` checks returning bool, `negative_` prefix | A1-A5, W6 |
| `test.sh` computes `raw / positive_total` and clamps | `test.sh` hardens and then ends with `exec rewardkit /tests --workspace /app --output /logs/verifier/reward.json`. It writes no reward | B1-B5 |
| exit trap `publish_results` with `\|\| true` | illegal: B5 bans `exit`, `return` and `\|\|` in `test.sh`, and `exec` discards traps anyway | B5 |
| reward = test channel only, clamped | reward = 0.5 x test fraction + 0.5 x judge fraction, no clamp, range -1 to 1 | R1-R5 |
| rubric floor 25, first five `instruction following` | `judge_qc` needs 8 to 35. No required count or position for instruction following. 25 is now a house floor only (section 9) | G3, JD-12 |
| criterion fields `number, criterion, is_positive, type, evaluation_target, importance, score` | `id, name, description, type = "binary", weight` plus a mandatory `[criterion.annotations]` table | J1-J13 |
| `state_change` rubric targets | allowed again, but the judge must not read anything a test reads | JD-8 |
| positive tests for "inputs unmodified" and "no extra files" | TS-25: no positive test may grade an absence. These become `negative_` checks | TS-25 |
| AL-30: combined penalty per action at most 5 | AL-28: one action never fires more than one max-severity penalty across both channels. Keep the old sum cap of 5 as a house rule | AL-28 |
| `instruction.md` has no headings, bullets or tables (QC P1-P3) | instruction_qc no longer bans layout. P1 is dashes, P2 banned words, P3 AI-tell phrases. Plain prose stays a house rule because it is a difficulty lever (section 11) | P1-P3 |
| records of 200 rows or more | playground A5: every record file (csv, tsv, jsonl, txt, log) has 2,000 lines or more, and the inputs total 20,000 lines or more | playground A5 |
| `README.md` names no archetype, so pass `--archetype` | still true for `validate_bundle.py`: it reads the archetype from `TRUTH.md` provenance, which DS-27 keeps clean, so it falls back to `format-recovery` unless you pass `--archetype` | validate §1.12 |
| `report.json` channel figures from `scripts/judge_trajectory.py` | that script still reads `tests/rubric.json`, `tests/test_weights.json` and `verifier/ctrf.json` (lines 779 to 781), and none of those exist in a 0.24 bundle. Read the channels from rewardkit's `reward.json` and `reward-details.json` (section 3) | runtime |
| Step 10: one oracle run and one nop run | five oracle runs at exactly 1.000, one nop run at exactly 0.000, and one stub run you judge, all on `exe_copy.py` tests-only copies | Final_checklist Step 10 |
| the word canary banned (old X3) | X3 is now the 100 MB ceiling. Benchmark self-references and GUIDs are still banned by IN-4 | X3, IN-4 |

### 0.1 Changes since the first version of this guide

These landed in `Input_Bundle_QC/` and the generator after this guide was first
written. Each one fails a bundle built to the older text.

| This guide used to say | Current rule | Checked by |
|---|---|---|
| judge annotations carry 8 to 11 keys (`mode, type, evidence, residue, kind, category, evaluation_target, importance`, plus `contract_sentence`/`contract_file` or `serves`) | annotations carry **exactly four keys in this order**: `mode`, `type`, `evaluation_target`, `importance`. `category`, `kind`, `serves`, `residue`, `evidence`, `contract_sentence` and `contract_file` are retired and **fail** | J6, JD-S8 |
| annotations `type` is the observed effect (VALUE, EFFECT, ABSENCE, INVARIANT, ORDERING, DIVERGENCE) | annotations `type` **is the category**: `task completion`, `instruction following`, `tool use`, `agent behavior`, `factuality and hallucination`, `safety and boundaries`. The effect vocabulary is gone | J7, JD-S9 |
| `kind = "constraint"` if and only if `category = "instruction following"` | there is no `kind` key. A constraint criterion carries `type = "instruction following"`, and an outcome or conduct criterion never carries that label | JD-16 |
| a constraint criterion's `contract_sentence` must appear verbatim in the instruction (playground A3) | there is no `contract_sentence` key and no A3 check. The quoted sentence still has to exist, but you record it in your private notes and in TRUTH.md, and gate 04 checks it by reading | JD-16 |
| all agent input lives in `environment/data/` | input lives in **one or more named directories** next to `environment/Dockerfile` (`data/`, `repo/`, `fixtures/`, `logs/`, and a task may ship several). Each holds at least one file and each is a COPY/ADD source in the Dockerfile. `environment/` holds no loose files | S4, FC-S3 |
| D1 bans an unconditional grade-time read of `/app/data` | D1 bans an unconditional read of **every** COPY destination, so `/app/repo` and `/app/fixtures` crash the verifier exactly as `/app/data` does | D1 |
| playground reruns the oracle once per data file | ablation has three modes: `sample` (default: one unit per input directory plus up to 8 more), `full` (every unit, for sign-off) and `off`. A tree directory such as `repo/` ablates as one unit, a flat directory file by file. `--jobs` sets parallelism | playground D4 |
| playground static checks are A1 to A5 | A3 is gone with `contract_sentence`. The static checks are A1, A2, A4, A5 | playground |
| `{{TRUTH_DATA_FILE_COUNT}}` counts `environment/data/` | it counts every file of every input directory, at its image path | generator |

| the pinned `[judge] mode` is `"individual"` | it is now **`"batched"`**, rewardkit's own default. `individual` re-sends the whole trajectory once per criterion, so a 30-criterion file costs 30x the input tokens for the same verdicts | G2 |
| `test.sh` sets `chmod 700` on the verifier log directory, and the Linux read-back risk is unverified | the pinned value is now **`chmod 755`**, and the risk is fixed. H5 passes on 755 and **warns on 700** with the reason: Harbor reads the bind-mounted reward file back as the host user, and a directory it cannot traverse makes that read fail on Linux with `RewardFileNotFoundError` even though grading succeeded. Root ownership still blocks other writers | H5 |

The `tests_qc.py` module docstring still says "chmod 700" at H5. That line is
stale; the implementation checks for 755 and the pinned template uses it.

Two harness facts to check before you start. This repo's own `pyproject.toml`
says 0.20.0, but Step 10 requires the installed `harbor --version` to print
0.24.0 or newer. Upgrading the CLI with `uv tool install harbor==0.24.0 --force` is
the one install Step 10 allows. Also, the pinned agent image pre-bakes the
openhands-sdk runtime, so the first image build takes several minutes.

---

## 1. Deliverable: exactly this tree

```
<task-name>/                      lowercase kebab-case, 3 to 64 chars (S1)
  instruction.md                  agent-visible prompt
  task.toml                       pinned schema 1.4 template
  environment/
    Dockerfile                    pinned agent image
    <input-dir>/ ...              ALL agent inputs: one or more named directories
                                  (data/, repo/, fixtures/, logs/ ...), each COPYed
                                  into the image. No loose files in environment/
  solution/
    solve.sh                      oracle entrypoint, LF, scores exactly 1.000
    solve.py                      independent reference implementation
    TRUTH.md                      author-side golden trajectory, never agent-visible
  tests/
    Dockerfile                    verifier image, tests/ is the build context
    test.sh                       pinned hardening + exec rewardkit
    test_output.py                rewardkit checks + weight registrations
    judge.toml                    LLM-judged criteria, pinned header
    reward.toml                   0.5 / positive total per channel
```

Anything else is a fail: `README.md`, `cheat/`, `tests/rubric.json`,
`tests/test_weights.json`, notes, plans, scratch dirs, `__pycache__/`,
`.pytest_cache/`, `.git/`, `.DS_Store`, and any `reward.txt`, `reward.json`,
`reward-details.json` or `ctrf.json` anywhere. rewardkit imports every `.py` and
reads every `.toml` at the top of `tests/`, so `tests/` must hold exactly the five
files above.

Keep your **private author notes** in one file outside the bundle directory (for
example `~/.cache/<task-name>-author-notes.md`). Calibration numbers, wrong-prior
estimates, the near-miss ladder, gate arithmetic, the withheld-rule reading
enumeration, the novelty paragraph and the archetype choice go there. None of it
goes in the bundle.

---

## 2. The pinned files

Copy these shapes. Values without angle brackets are pinned and identical in
every bundle. Extra keys, missing keys and reordering all fail.

### 2.1 task.toml

```toml
schema_version = "1.4"
artifacts = ["/app/<deliverable>", "/app/<deliverable2>"]

[task]
name = "terminal-bench/<task-name>"
version = "1.0.0"
description = "<one paragraph, at most 100 words>"
keywords = ["<at least one>"]
authors = [{ name = "<Your Full Name>", email = "<name-derived>@ethara.ai" }]

[metadata]
category = "<truthful name of the dominant work>"
platforms = ["linux/amd64", "linux/arm64"]
tags = ["<at least one>"]
estimated_duration_sec = <positive>
expert_time_estimate_min = <positive, honest time of the TRUTH.md plan>
junior_time_estimate_min = <strictly greater than expert>
null_floor = 0.0
discrimination_weight = 1.0

[verifier]
timeout_sec = <positive>
environment_mode = "separate"
network_mode = "allowlist"
allowed_hosts = ["api.openai.com", "*.openai.com"]

[verifier.env]
OPENAI_API_KEY = "${OPENAI_API_KEY:-}"

[verifier.environment]
network_mode = "allowlist"
allowed_hosts = ["api.openai.com", "*.openai.com"]

[agent]
timeout_sec = <positive, equals N in "You have N seconds to complete this task.">
network_mode = "allowlist"
allowed_hosts = ["api.anthropic.com", "api.z.ai"]
user = "1000:1000"

[environment]
build_timeout_sec = <positive>
network_mode = "no-network"
cpus = <positive int>
memory_mb = <positive int>
storage_mb = <positive int>
gpus = 0
mcp_servers = []
```

Generator defaults, if you have no better figure: agent 7200 s, verifier 2700 s,
build 900 s, expert 480 min, junior 1440 min, 2 CPUs, 4096 MB, 10240 MB storage.
Artifacts are absolute paths with no `..` and no backslash. `[verifier.env]` must
hold the placeholder exactly. A literal key there is a leaked credential (AL-19).

**The offline contract is now real.** `[environment]` is `no-network`. The
instruction must not tell the agent to fetch, download or install anything, the
Dockerfile must not install at run time, and `solve.py` must run with no network
(IN-11, DS-11, AL-15). Saying nothing about the network is correct. The verifier
and agent allowlists are harness plumbing and are never a finding.

### 2.2 environment/Dockerfile

```dockerfile
FROM public.ecr.aws/docker/library/python:3.12-slim@sha256:646fb0bca3dd3ea1bcc6feb72c17ed16eed6e10cffc732fcc1478bd3e7f02d7b
RUN groupadd -g 1000 agent && useradd -u 1000 -g 1000 -m -d /home/agent -s /bin/bash agent
ENV HOME=/home/agent
RUN apt-get update && apt-get install -y --no-install-recommends xxd file curl bash nodejs npm procps ca-certificates tmux && rm -rf /var/lib/apt/lists/*
RUN python3.12 -m venv /opt/openhands-sdk-venv \
    && /opt/openhands-sdk-venv/bin/pip install --no-cache-dir openhands-sdk==1.55.1 openhands-tools==1.55.1 litellm==1.105.0 fastapi \
    && /opt/openhands-sdk-venv/bin/python -c "import openhands.sdk, openhands.tools" \
    && chmod -R a+rX /opt/openhands-sdk-venv
RUN mkdir -p /app && chown 1000:1000 /app
WORKDIR /app
COPY data /app/data
COPY repo /app/repo
```

S8 replays `mkdir`, `chown`, `chmod`, `COPY --chown`, `WORKDIR`, `USER` and
`useradd -u`. Every artifact directory (for example `/app/out`) must be writable
by uid 1000, or the oracle dies with `PermissionError` and Step 10 reads 0.000.
Create subdirectories before the `chown`, or `chown` them too.

**One COPY line per input directory.** S4 fails any input directory the
Dockerfile never copies, because the agent would never see it, and it fails any
input directory that holds no file. Name each directory for what it holds. The
destination is conventionally `/app/<dir>`, and whatever you choose is the path
the instruction must name and the path D1 then forbids the verifier from reading.
S7 and DS-23 still bind: the build context is `environment/`, so no COPY may
reach outside it, and `environment/` itself holds the Dockerfile and the input
directories and no loose files.

Add task-specific apt or pip packages only when the task needs them. Pin pip
versions, never pin apt versions. Never install an agent CLI. DS-26: no build
step may leave an expected output, a build stage holding the answer, or a build
log anywhere in the image.

### 2.3 tests/Dockerfile

```dockerfile
FROM python:3.12-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends util-linux \
 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0
ENV LITELLM_LOCAL_MODEL_COST_MAP=True
COPY . /tests/
RUN mkdir -p /app
WORKDIR /app
```

Add every third-party module `test_output.py` imports to the pip line (K4).
pytest is not needed. Three pins are mandatory and each has its own check:
`harbor-rewardkit==0.2.1` (K5), `litellm==1.105.0` (**K8**, a fail: rewardkit
accepts `litellm>=1.83` with no upper bound, so an unpinned build takes whatever
PyPI serves that day), and the `ENV` line (K7, without which rewardkit deadlocks
at shutdown on about half of all runs). `util-linux` provides `setpriv` for
running agent code unprivileged (H1).

### 2.4 tests/test.sh, byte for byte

```bash
#!/bin/bash
set -euo pipefail

rm -f /logs/verifier/reward.txt /logs/verifier/reward.json /logs/verifier/reward-details.json
mkdir -p /logs/verifier
chown root:root /logs/verifier
chmod 755 /logs/verifier
chmod -R go-rwx /tests

exec rewardkit /tests --workspace /app --output /logs/verifier/reward.json
```

LF line endings. No `exit`, `return` or `||` (B5). No SKIP switch, no sourcing
from `/app`, no agent-writable directory on PATH. Do not add the blueprint's exit
trap.

**Why 755 and not 700.** In separate verifier mode Harbor reads `reward.json`
back from the host side of the bind-mounted log directory, as the host user. A
root-owned directory at 700 cannot be traversed by that user, so the read fails
with `RewardFileNotFoundError` and the trial errors even though grading
succeeded. The older 700 form caused exactly that on Linux hosts and passed on
Windows only because Docker Desktop ignores bind-mount ownership. 755 keeps the
protection that matters, since root ownership still blocks every other writer,
and allows the read. H5 warns if you set 700. Use the pinned script unchanged.

### 2.5 tests/reward.toml

```toml
[[reward]]
name = "reward"
aggregation = "weighted-sum"
weights = { test_output = <0.5 / test positive total>, judge = <0.5 / judge positive total> }

[scoring.test_output]
aggregation = "weighted-sum"
```

Write each weight as Python's `repr(0.5 / total)`, the full float (R3). Recompute
both every time a weight changes.

### 2.6 tests/judge.toml header

```toml
[judge]
judge = "openai/gpt-5.6-sol"
mode = "batched"
timeout = 300
atif-trajectory = "/logs/agent/trajectory.json"
weight = 1.0

[scoring]
aggregation = "weighted-sum"
```

No `reasoning_effort`, no other top-level table. Criterion rules are in section 9.

---

## 3. Score arithmetic under rewardkit

Every check and criterion is binary. A positive that comes back True adds its
weight. A negative that comes back True (the cheat or bad behaviour happened)
adds its negative weight. False adds nothing.

```
test_frac  = (sum of weights of test checks returning True)   / P_test
judge_frac = (sum of weights of criteria judged yes)          / P_judge
reward     = round(0.5 * test_frac + 0.5 * judge_frac, 4)
```

`P` is the channel's positive weight total. W7 and G6 cap each channel's negative
total at its positive total, so each channel runs from -1 to 1 and contributes
-0.5 to 0.5. Nothing is clamped.

**Consequences for design.**

- The judge channel is half the reward. A judge channel at 100 percent beside a
  test channel at 0 is a reward of 0.5. No test weighting rescues a narratable
  judge file.
- Design each channel to land in the 8 to 12 band once the negatives are
  counted. The negatives are a dial, not a rescue: they are worth about 22
  points of the judge channel, so a positive half left at 30 percent cannot be
  dragged into the band by negatives alone, and a positive half already at 12
  will undershoot once four negatives fire. Project both together.
- Negative must be earned. It is legitimate only when the fired negatives name
  shortcuts the run actually took. If a negative fires on nop or on the oracle,
  the bundle has a defect.

**Reading a real run.** For each trial, open `verifier/reward.json` and
`verifier/reward-details.json`. `reward.json` holds the combined `reward` and one
entry per channel (`test_output`, `judge`). Divide each channel's raw
weighted-sum by that channel's positive total to get the channel percentage, then
cross-check that `0.5 * test_frac + 0.5 * judge_frac` reproduces `reward`.
`reward-details.json` lists the verdict of every check and criterion, so the
failed-for-the-right-reason analysis in 10.4 comes from there. I read this
structure from the Final_checklist and rewardkit's runner. I did not run a live
0.24 trial, so confirm the field layout on your first run before you trust a
script built on it. Real agent runs need the judge key passed through, for
example `--ve OPENAI_API_KEY=$OPENAI_API_KEY`. Without it the verifier errors by
design.

---

## 4. One-pass build order

The order is the method. The worked answer comes before the prompt, and the
mutations come before the weights.

1. Read every `instruction.md` under `Tasks_INPUT/` and `dataset/`, the
   Final_checklist in full, and the four QC scripts. List the mechanisms this task
   may not reuse. The recovery and decoding shapes already in `Tasks_INPUT/`
   (slice recovery, snapshot index recovery, telemetry codec recovery, coefficient
   recovery) are banned outright by 5.1. Write the novelty paragraph in your
   private notes, by mechanism and never by domain.
2. Keep the given category. Choose the archetype yourself from that category's
   legal candidates (6.1). Never let the generator pick one.
3. Name one primary crux in one sentence, write the evidence-to-result chain,
   and confirm the three burdens (5.2).
4. Run the paraphrase test and the retrieval test (5.3). If either fails, pick a
   new crux.
5. Confirm real algorithmic depth. At least one deliverable must need an
   algorithm whose correctness is non-trivial.
6. Design the trap set (5.6), at least five evidence and state levers (5.8), the
   interaction matrix, the failure-mode inventory (5.12) and the spine (5.2).
7. Apply silent plausibility (5.10) to every trap. Redesign any trap whose wrong
   branch crashes or emits an obviously broken artifact.
8. Design and generate the corpus (section 7) from a fixed seed.
9. Design the artifact graph and identity triangle (section 6), and the closing
   report's counterfactual payload (9.3).
10. Write `solution/TRUTH.md` now, before the prompt (section 12).
11. Write `solution/solve.py`, independent of the verifier (O1, DS-24).
12. Build the near-miss mutants: one per documented rule and one per profile
    in 10.5.
13. Write `test_output.py` (section 8), assign weights, run the gates in 10.1 to
    10.3 on paper, then run the mutants. Move weight until the ladder reads
    correctly.
14. Write `judge.toml` (section 9) and run JD-7 against the oracle line by line.
15. Write `instruction.md` last, derived from `TRUTH.md` (section 11). Remove
    every route hint, and state every graded rule unless it is withheld under
    5.9 with its proof.
16. Write `task.toml`, both Dockerfiles, `test.sh` and `reward.toml` from
    section 2.
17. Walk every input directory and the whole agent image file by file for answer
    keys (5.11, DS-26).
18. Run the offline hardness gate (10.6) on a scratch copy.
19. Run the four QC scripts, `validate_bundle.py --archetype <name>`,
    `playground.py`, and the five model gates. Fix everything and rerun until
    all of them pass.
20. Run the section 17 blind solvability probe. Fix every UNREACHABLE item and
    every INVENTED literal before going further
21. Run Step 10 (section 13), then the section 16 blind difficulty probe, then
    the real trajectory run against the reference models. Read both channels.

Steps 12, 13 and 18 are what make this one pass instead of three.

---

## 5. Difficulty engineering

### 5.0 The four design laws

Everything in this section serves four laws. Build to these and the rest is
detail; break one and no amount of trap count recovers it. Each law carries the
one QC rule that keeps it honest, because three of the four have a failure mode
that turns a hard task into an unfair one.

**Law 1. The obvious approach must finish and be wrong.** A competent first
attempt should run clean, write every artifact, print nothing alarming and exit
zero, while being wrong. This is the whole of 5.10 and it is the law the
research supports most directly: software engineering agents survive their own
blindness because the environment tells them when they are wrong (15.2). Every
trap that crashes hands that lifeline back. *The honest line:* the wrong branch
must be wrong because the solver missed a stated or derivable rule, never
because a value was unobtainable.

**Law 2. Decisive facts live in the data, not in the instruction.** An offset, a
changed unit, a precedence that is not last-wins, a parameter the prompt never
names: put these in the corpus and let the solver find them. A rule written out
in full is a rule a frontier model transcribes, which is 5.9's measured result.
*The honest line, and this is the one that breaks bundles:* "not in the
instruction" is not "nowhere". DS-21 and CL-10 require every graded fact to be
reachable from `instruction.md` plus `environment/`, by reading or by
derivation. And DS-25 is separate and stricter: every **output literal** the
checks require, meaning key names, column names, enum values, filenames and any
ordering the tests assume, must appear in an agent-visible file. Withhold the
rule; never withhold the shape. A run that computes every value correctly and
emits them under invented names scores zero, and that is the most common way a
hard task becomes an unpassable one.

**Law 3. State the goal and the output contract, never the steps.** Describe the
end state and what must be true of it. No procedure, no named algorithm, no
"first, then, next", no file-to-deliverable map. IN-14 requires this and 11.1 is
how it is done inside the length guideline. *The honest line:* cutting the
method is right, cutting the contract is a defect. Section 11's keep-and-cut
list is the test.

**Law 4. Accept every answer the instruction allows.** Read each assertion and
ask what it demands beyond the answer being right: list order, key spelling,
casing, path form, number representation. Each of those must either be stated in
the contract, or be shown by an example the agent is actually given in the
input, or be compared in a way that does not care. Anything else grades
telepathy and fails CL-5. This law is the counterweight to the other three: laws
1 to 3 make the task hard, and this one keeps the hardness in the reasoning
rather than in guessing the author's conventions. 8.8 is the procedure.

The four together are what produce a task a senior engineer finds hard and
finishes, and a frontier model finishes and gets wrong.

### 5.1 Hard rules

- Banned mechanisms whatever the category: recovery, encoding or decoding,
  pattern matching, cryptography, corrupted-data reconstruction, shard recovery,
  reverse engineering. The `format-recovery` archetype is banned.
- Banned difficulty: a requirement stated nowhere, a rule stated ambiguously and
  graded one way, a tolerance no correct implementation meets, float equality, a
  deliberate contradiction, a rule you can only discover by reading the tests,
  volume for its own sake, puzzles not motivated by the domain, Unicode
  normalization forms, homoglyphs and BOM tricks, grading key order, whitespace or
  casing, and anything a senior engineer cannot finish in the expert time.
- No single library call may solve it. If one package implements the
  specification, change the specification so at least three documented rules
  depart from that package's defaults, and say so plainly.

### 5.2 The shape of a hard task

**Governing rule:** withhold the route, never the destination and never the
evidence needed to find the route. The route is the method. Every rule a check
grades is stated, or decided by shipped evidence under 5.9.

**Three burdens, all present.** Discovery: the agent must work out which files
and facts govern the result. Synthesis: individually simple facts interact.
Validation: the obvious implementation passes the easy visible case and fails on
another size, order, state, boundary or failure mode.

**Dependency-chain test.** Write the shortest honest chain from evidence to
result. `read -> transcribe -> write` is too easy. A chain containing "guess a
hidden constant" is impossible. A chain whose steps are independent is broad and
shallow, so add interaction between the steps rather than more steps.

**One crux, one spine.** Every trap reinforces one central difficulty. Pick one
spine quantity (a cursor, a resolved key, a running state, a count) that most
weighted checks depend on. Put the highest-weight lever and the most decisive
withheld rule on the spine, so one early wrong decision cascades through every
weighted check downstream. Measured in this project: threading one quantity
through four artifacts moved a task from 57.8 percent to 19.6.

### 5.3 Novelty

The hardness has to survive paraphrase. Renaming the industry, the files or the
story does not make a task new. It is new only when the evidence combined, the
crux or the shape of the chain is different. Retrieval test: if a strong agent
searched for the closest match, would the top result contain the full solution?
If so, it is a reskin. The task counts as new when at least one of these holds:
it combines known pieces in a way no standard solution covers, it imposes a
constraint that rules out the textbook approach, its inputs break an assumption
the standard solution relies on silently, it is an invariant to enforce rather
than a recipe, or it crosses two domains rarely combined. Never name another
task's slug inside the bundle.

### 5.4 Legitimate trap test

Run this four-part check on every trap and record the result in your private
notes:

1. The rule is stated in `instruction.md` or a spec it points to, with exactly
   one reading. If it is withheld, exactly one reading reproduces the shipped
   evidence.
2. A competent practitioner who skipped that sentence would do something
   different. If not, it is filler.
3. A human holding the whole prompt can satisfy it without guessing.
4. At least one check or criterion detects the wrong version specifically.

### 5.5 The pass@8 arithmetic

`pass@8 = 1 - (1 - p)^8`. For pass@8 at or below 25 percent, `p` must be at or
below 3.6 percent. Coin-flip traps do not survive eight attempts: one trap a
model gets right half the time gives 99.6 percent. The mechanism you want is
**correlated failure**. Each load-bearing trap's wrong answer must be the
overwhelming prior, so the same wrong choice recurs in all eight runs. Per-trap
test: if ten experienced engineers implemented the rule without reading its
sentence, eight or more would get it wrong. Designate four to six load-bearing
traps, each with a recorded wrong prior of 80 percent or more, and each graded by
at least one weight-5 check.

### 5.6 Trap catalogue (use 12 or more, 18 is better, 50 to choose from)

Every trap must be documented, or withheld with evidence, interact with at least
two others, and be graded by a named check or criterion.

1. Canonical ordering with a tiebreak most solvers ignore. Ties must occur.
2. A named rounding mode at a named precision and stage, applied once. Use
   integer minor units or `Decimal`.
3. Same field name, different units across two files, documented.
4. A business-day boundary at a named offset that is not UTC midnight.
5. Three-layer precedence where one key class resolves by a different rule.
6. Clamp before aggregation, not after.
7. Excluded from the derived rate but still counted in a separate audit total.
8. Duplicate ids with a documented winner that is neither first-seen nor
   last-seen.
9. Normalization before comparison, domain-realistic (padded ids, upper-cased
   codes, legacy aliases). Grade the joined result, never the normalized string.
10. Null, zero and missing behave three different ways.
11. Cross-artifact identity: artifact B satisfies a stated arithmetic identity
    against A.
12. Carry-forward with a rare conditional reset.
13. Half-open intervals `[start, end)`.
14. Retractions and corrections that arrive later, in another file, under a
    documented governing-version rule.
15. Allocation tiebreak under exhausted capacity.
16. Malformed input goes to a rejects artifact with a schema and reason codes,
    malformed in a way a naive parser silently tolerates.
17. Remainder distribution by largest remainder with a documented tiebreak.
18. Self-reported counts that the checks recompute.

The next twenty are newer and harder. They were chosen because each one defeats
a specific habit of a frontier model rather than a careless reader, and because
handling each one wrong still produces a well-formed artifact (5.10). Mix them
with the first eighteen; do not use these alone.

19. **Non-associative aggregation order.** The documented fold is left to right
    over a canonical order, and the quantity is one where grouping changes the
    result (clamped running totals, saturating counters, capped carry). A model
    that groups by key and sums per group gets a plausible wrong number.
20. **Two clocks that disagree by design.** Every record carries both an
    effective time and a recorded time, the window rule names one and the
    eligibility rule names the other, and a documented subset arrives late
    enough that the two disagree. Using one clock everywhere is the habit.
21. **Reopened intervals.** A unit closes, then a later record reopens it inside
    the same period. The documented rule says whether the reopened span is one
    interval or two, and the identity totals differ between the readings.
22. **An identity that holds under the wrong rule too.** Design one of the three
    identities so a specific wrong reading also satisfies it, and make a second
    identity the only one that separates them. This punishes the model that
    self-checks with one invariant and stops.
23. **A superseding correction that is itself superseded.** Correction chains two
    or three deep, where one chain loops back to an earlier version and the
    documented rule resolves it by provenance rank, not by recency.
24. **Partial-credit decoy state.** A state value that is legal in the enum but
    unreachable under the documented transitions. Any unit carrying it is
    evidence of a wrong path, and the rejects contract names the code for it.
25. **Unit drift inside one file.** A column changes unit at a documented
    effective date (minor units before, major units after), recorded in the spec
    and not in the header. Schema sniffing reads the whole column one way.
26. **Cross-file key collision with different meanings.** The same identifier
    value exists in two namespaces, and the documented disambiguation is a
    second field, not the id. A naive join merges two real entities.
27. **An authoritative source that is silent, not absent.** One source carries a
    documented empty marker meaning "no change", distinct from both a missing row
    and a zero row. Collapsing it into either one moves the carry-forward.
28. **Order-dependent dependency resolution.** The dependency graph has a cycle
    that the documented rule breaks at a named edge class. Topological sort
    without the rule yields a different, still plausible, order.
29. **A quota that binds only after exclusions.** The cap applies to the
    post-exclusion set, and the data is built so the pre-exclusion set also fits
    under a different cap. Both produce a full, believable allocation.
30. **A rounding stage that interacts with a tiebreak.** Two units tie only when
    rounding is applied at the documented stage, and do not tie when it is
    applied earlier. The tiebreak then decides a visible ordering.
31. **Evidence that only three sources together settle.** Any two sources agree
    on a wrong reading for a documented subset, and the third breaks the tie.
    This is triangulation made load bearing rather than decorative.
32. **A recurring commitment with an exception calendar.** A schedule generates
    occurrences, and a separate exceptions file cancels, moves or splits some of
    them under a documented precedence. Expanding the schedule first and
    applying exceptions second gives a different set than the documented order.
33. **A field whose absence is meaningful only in one state.** Missing means
    "inherit" in one state and "unset" in another, and both appear.
34. **A deliberately stale derived column.** The input ships a precomputed
    column that was correct under a prior rule version, and the spec names the
    current rule. Trusting the shipped column is the shortcut, and CL-6 is
    satisfied because the spec marks it as advisory.
35. **A boundary that moves with the entity.** The period boundary is per entity
    (a fiscal calendar, a contract anniversary), not global, and a reference
    table carries it. One global boundary is the habit.
36. **An exclusion that is itself conditional.** A unit is excluded only when a
    second condition holds at the effective time, and the data carries units
    that satisfy the first condition at both truth values of the second.
37. **A count the report must state that no artifact carries.** Pair every
    counterfactual figure in 9.3 with a trap, so the figure is wrong exactly when
    the trap is handled wrong. This is what makes the judge channel move.
38. **Idempotence under re-run with a mutable input.** The deliverable must
    produce identical output when run twice, and one documented input carries a
    field that a naive implementation writes back or reorders in place.

The last twelve are aimed at the measured failure modes in section 15 rather
than at a careless reader. Each names the mechanism it exploits. These are the
ones most likely to move a frontier model, so take at least four.

39. **Entity binding drift bait** (15.2, measured at 8.5x on Opus 4.5). Give
    each entity three or four legal handles: a legacy id, a display code, a
    vendor alias, a composite natural key. The documented rule resolves the
    canonical entity once, and later stages are specified in terms of the
    canonical entity while the inputs keep using the handles. A run that
    resolves correctly at the join and then quietly re-binds on a later handle
    produces a complete, plausible, wrong result. Make at least one handle
    collide across two entities so a wrong binding is reachable, not just
    careless.
40. **Late contradiction that invalidates an early decision.** A record in a
    file the solver reaches late makes an earlier branch wrong under the stated
    precedence. The correct response is to regenerate everything downstream; the
    habit is to patch the one artifact in hand. The identity triangle then fails
    in two places, which is 15.2's cascade row turned into a graded fact.
41. **A rule that only engages past a horizon.** A documented condition that
    cannot fire until a running value has crossed a threshold, so it appears
    only in the back half of the data. A solver that validates on the head of
    each file never sees it. This pairs with the self-conditioning row: the rule
    lands exactly where per-step accuracy is lowest.
42. **No environment feedback on the wrong path** (15.2, the recovery row). This
    is a property to enforce across every trap rather than a single trap. For
    each wrong branch, confirm the run still exits zero, imports cleanly, writes
    every artifact and prints nothing alarming. Where a wrong branch would
    naturally raise, change the data so the naive path silently tolerates it: a
    sentinel that parses as a number, a missing key with a documented default, a
    short row that a permissive reader pads. The research says this is the one
    thing that keeps a software engineering agent from recovering.
43. **A self-check that passes on the wrong answer.** Give the agent a
    verification it can genuinely run, and design one documented wrong reading
    that also satisfies it. The contract requires a second, different check that
    separates them. This exploits self-verification failure directly: the model
    runs the check it thought of, sees green and stops.
44. **A plausible wrong intermediate placed early.** A shipped advisory value
    (a prior period's resolved mapping, a vendor's own reconciliation) that is
    correct for most units and wrong for a documented subset, marked advisory so
    CL-6 holds. A model that adopts it early carries it through every later
    stage, which is self-conditioning with a ready-made first error.
45. **A group key that drifts mid-series.** The aggregation key changes
    representation at a documented effective point (a renamed region, a merged
    cost centre, a re-parented node). Correct handling maps both to one group;
    the habit is two groups, and both totals look reasonable.
46. **An ordering that only matters under a later rule.** Two stages commute
    unless a third documented rule is active, and that rule is active for a
    documented minority. The solver that fixes one order globally is right most
    of the time and wrong on exactly the units the checks sweep.
47. **A terminal obligation stated once, early.** One requirement about the
    final artifact stated in the first third of the specification and never
    repeated, taking effect only at the last stage. This is the memory row of
    15.2: catastrophic forgetting becomes dominant as the horizon grows. It is
    fair because it is stated plainly, once, in the place it belongs.
48. **A documented idle case that must still be reported.** A class of unit the
    rules deliberately leave with nothing to do, which must still appear in a
    named artifact with its reason code. Models drop the empty case and report
    the interesting ones.
49. **Two aggregates that must disagree.** A documented pair where the naive
    expectation is that two totals match, and the rules require them to differ
    by a derivable amount the report must state. A run that "fixes" the gap to
    make them agree looks tidier and is wrong.
50. **A cross-file quantity no single file can produce.** One graded figure
    requires joining three or more sources, where each pair alone yields a
    defensible but different number. This is triangulation made load bearing,
    and it defeats the solver that samples one file and generalises.

Keep two or three **structural levers** separate from the traps. Never one,
never more than three, each undone a different way, and at least one an
isolation breaker (chained state, running delta, drifting key, sliding window)
so no unit resolves in isolation.

**Interaction is what makes the count matter.** Twenty independent traps is a
long task, and section 15.3 shows the arithmetic: independent sub-problems give
the model twenty chances at partial credit, while dependent steps multiply. Build the set so each trap changes the outcome of at least two
others, record that matrix in TRUTH.md, and cut any trap you cannot link. Four
to six of them are load bearing under 5.5, each with a recorded wrong prior at
or above 80 percent, and each graded by at least one weight-5 check.

### 5.7 Chained and implicit dependencies

Build the deliverables as a DAG at least four levels deep. At least three
artifacts depend on two or more upstream results, and at least two dependencies
are implicit: the instruction states the downstream rule without restating the
upstream rule it relies on. Require one rule whose correct application depends
on a value produced two levels earlier. A reconciliation artifact at the bottom
is the strongest single lever, because it is right only when everything above it
is right.

```
level 1  parse, normalize, apply the rejects contract
level 2  resolve duplicates, precedence, units
level 3  primary result under ordering, clamp order, rounding
level 4  secondary result under the cross-artifact identity
level 5  reconcile: restate counts and totals, record branch decisions
```

### 5.8 Evidence and state levers (use at least five)

Triangulation across three or more sources. Distributed evidence, so no single
file answers any graded question. Resolvable disagreement under a findable
precedence rule. Retractions and late corrections. Watermarks and visibility
windows. Interacting state across steps. Cross-artifact invariants, each paired
with a recomputed value, because an identity also closes on a consistently wrong
pipeline. A divergence point where two plausible readings separate and only one
survives a later check. Independent defect pockets for repair archetypes, at
least one under a realistic comment or guard that seems to handle the case. One
quantity threaded through the pipeline. Misleading content is allowed only when
it is realistic in-domain content, such as a stale comment or an outdated runbook
line, and CL-6 requires that something agent-visible marks it as not
authoritative.

### 5.9 Withheld rules (the strongest lever against transcription)

A frontier model transcribes every stated rule. Measured here: a spec
transcriber scored 1.000. With four decisive sections replaced by an observation
record the rules could still be derived from, it scored 0.108. A solver trusting
a shipped legacy note with the wrong reading scored 0.067.

Withhold three to six decisive rules, and only when the evidence decides them:

1. List every reading a competent practitioner could hold.
2. For each reading, hold all other rules at their true values, recompute
   against the shipped evidence, and count the units whose outcome changes.
3. Exactly one reading must reproduce the evidence. If a reading changes zero
   units, add targeted observations (a unit exactly on a boundary, a repeated id)
   until it changes some.
4. Flip each withheld rule in turn. Every decision must move at least one observed
   unit.

The evidence must carry no graded quantity. Record outcomes as states or flags.
Label choices with descriptive tokens, never A and B. Vary withheld values per
seed and per graded extract. Sweep the surviving spec for any sentence that
restates a withheld consequence. Never withhold the contract: every output name,
shape and enum stays stated (DS-25). Every withheld rule still gets a
traceability row that points at its evidence file. This passes DS-21, F0e and
CL-10 only because the derivation exists. Removing the statement is allowed.
Removing the ability to derive it never is.

### 5.10 Silent plausibility

Handling a trap wrong must still produce a well-formed artifact that looks
right: no crash, no stack trace, no empty file, no absurd number. A model that
crashes investigates. A model that sees a plausible number stops. A unit mismatch
that makes a number three times too large is a good trap. One that divides by
zero is a hint. Never rely on a rule whose violation raises a library exception.

### 5.11 No answer key, no self-verification

Banned anywhere the agent can reach (corpus, image, `/tmp`, build stages,
archive interiors, examples, prompt): expected outputs, golden files, a worked
example that composes several rules, an input paired with its result, a checksum,
count or length of a correct artifact, a self-test that encodes the answer, a
comment stating a computed result. Measured: a bundle shipping 24 worked answers
scored 82 percent on tests, and a comparable bundle with none scored 15. The
agent may verify **conformance** to stated rules, and must record that it did
(5.13). It may never verify **correctness** against ground truth. `/tests` is
`go-rwx` so executed agent code cannot read the answer key. Every value a check
compares against is recomputed inside the verifier from its own seed.

### 5.12 Failure-mode inventory and the reference-model profile

Measured in this harness: the reference model is strong at aggregates and at
narration, and weak at exhaustive per-unit correctness. On one task it scored 64
on tests and 100 on the rubric: every summary right, four artifacts wrong on
disk. Design against these modes. Each maps to a mechanism:

| Failure mode | Mechanism |
|---|---|
| detail wrong, aggregates right | per-unit whole-artifact checks, counterfactual judge figures |
| sampling instead of enumerating | rule-firing rows spread through the file, never in the first 50 rows; corpus too big to read |
| patching locally after a late discovery | 4-level DAG plus the identity triangle |
| inventing instead of abstaining | a documented unresolvable case with its own reason code |
| computing without verifying | a recorded self-check whose residuals the judge reads |
| silently tolerating malformed input | rejects contract, class-partition check |
| nondeterminism | run the deliverable twice, compare bytes |
| skimming a long spec | composed defined terms, no closing recap |
| applying the habitual order | stated order differs from habit, presentation order differs from execution order |
| narrating the method instead of the result | judge criteria name results only the per-unit path produces |

Write the ten most likely failure modes, ranked, into `TRUTH.md` as a table:
mode, rule violated, the check or criterion that catches it, weight at stake. The
top three must together carry more than a third of the positive test weight. The
profile comes from a few runs of one model, so re-derive it from your own runs as
they accumulate.

### 5.13 Long horizon, determinism, abstention, negative space

Require byte-identical output on a second run, and ban wall-clock timestamps,
hostnames and absolute build paths inside artifacts. Require a named intermediate
that a later stage consumes. Include a documented unresolvable case with a named
reason code. Require a recorded self-check in the reconciliation artifact. State
the negative-space obligations (inputs unmodified, no extra files at output
paths, no partial artifact on an error path), and grade them as `negative_`
checks per TS-25.

### 5.14 Simultaneous constraint load

The most constrained artifact holds at least twelve documented constraints at
once. Record the count and the artifact in your private notes.

---

## 6. Archetype and artifacts

### 6.1 Choose, then lock

| Category key | Legal archetypes (format-recovery excluded) |
|---|---|
| software-engineering | repo-patch, build-repair, cli-config, performance |
| system-admin | cli-config, service-interaction, build-repair, data-pipeline |
| model-training | performance, data-pipeline, build-repair, service-interaction |
| machine-learning | performance, service-interaction, data-pipeline, domain-calculation |
| optimization | performance, domain-calculation, repo-patch, cli-config |
| data-science | data-pipeline, domain-calculation, performance |
| data-processing | data-pipeline, domain-calculation, performance |
| data-querying | domain-calculation, data-pipeline, performance |
| scientific-computing | domain-calculation, performance, data-pipeline |
| mathematics | domain-calculation, performance, repo-patch |
| debugging | repo-patch, build-repair, performance |
| security | repo-patch, cli-config, service-interaction |
| file-operations | data-pipeline, cli-config, build-repair |
| games | performance, data-pipeline, service-interaction |
| video-processing | performance, data-pipeline, build-repair |
| personal-assistant | cli-config, service-interaction, data-pipeline |

This table was read from `_DOMAIN_ARCHETYPE_AFFINITY` in `generate_bundle.py`.
Re-read it if the generator changes. Pick the archetype whose workflow carries
the crux most naturally: stateful reconciliation fits a pipeline or calculation
archetype, a defect hunt fits a repair archetype, interaction under changing state
fits service-interaction, and correctness under a budget fits performance. Then
pass it explicitly everywhere:

```bash
python3 "Input Bundle Generator New/generate_bundle.py" --out Tasks_INPUT/ \
  --category <key> --archetype <name> --seed <int> --name <task-name> \
  --author "Ram Lakhan <ram.lakhan@ethara.ai>"
python3 "Input Bundle Generator New/validate_bundle.py" Tasks_INPUT/<task-name>/ --archetype <name>
```

Inherit the archetype's structure, file expectations, execution model and
manifest. Never import another archetype's requirements. Record the choice and
the reason in your private notes, never in the bundle.

### 6.2 Artifacts equal the manifest

`validate_bundle.py` §1.12 fails any `artifacts` list that differs from
`templates/<archetype>/archetype.toml`, and the generator README requires
validate_bundle to report no FAIL before the model gates run.

| Archetype | Manifest artifacts | min_inputs | ablation_max |
|---|---|---|---|
| data-pipeline | 14 | 10 | 0.5 (default) |
| domain-calculation | 10 | 10 | 0.5 (default) |
| performance | 10 | 10 | 0.85 |
| build-repair | 7 | 6 | 0.9 |
| cli-config | 7 | 6 | 0.5 (default) |
| repo-patch | 7 | 6 | 0.9 |
| service-interaction | 7 | 6 | 0.7 |

Put the difficulty into what the artifacts contain, never into how many there
are. Each artifact must be a distinct product of reasoning. For each one, name
the documented rule that shapes it and the graded value that changes when that
rule is applied wrong. An artifact with no such rule is padding. Good roles: a
primary result that depends on the full rule set, a secondary result bound to it
by an identity, a rollup at another granularity bound by a second identity (the
**identity triangle**), a normalized intermediate a later stage consumes, rejects
with reason codes, unresolvables with their own code, a reconciliation and
validation record, a run manifest of branch decisions, and the reusable transform
where the archetype delivers code.

**DS-25 and CL-5: over-specify the contract.** Every literal the checks require
(JSON keys, columns, enum values, headings, file names, list order, path form)
must appear in an agent-visible file. A correct answer under invented names
scores zero, which is the most common way a solvable task becomes unpassable.
Compare parsed values, never key order, whitespace or casing. Spread the
artifacts across several formats, each with its own contract.

---

## 7. Corpus (the input directories under environment/)

- **One or more named input directories**, each copied into the image by its own
  COPY line, each holding at least one file, and `environment/` holding no loose
  files (S4). Name each for what it holds: `data/` for flat records, `repo/` for
  a source tree, `fixtures/`, `logs/`, `policies/`. Several directories is the
  better shape for a hard task, because it lets you separate evidence classes
  that the solver has to join, and because a tree directory ablates as one unit.
- **50 to 60 files across the input directories**, and no file over 100 MB.
  Volume is not difficulty. Each file must contribute distinct evidence: an
  independent source to triangulate, a period or shard with its own corrections,
  a reference table a rule depends on, a configuration layer, an exceptions file,
  or a specification document. Split by concern, never by size. A flat input
  directory holds files only; a tree directory such as `repo/` may nest.
- **Line floors (playground A5).** Every record file (`.csv`, `.tsv`, `.jsonl`,
  `.txt`, `.log`) has at least 2,000 lines, and the inputs total at least 20,000
  lines. Write specification, schema and policy documents as `.md` so the
  record-file floor does not apply to them. Each still has to earn its place.
- **Every file named (playground A4)** by the instruction or by a spec document.
  An index spec in the corpus that names each file and its schema is fine. A
  route map saying which file solves which deliverable is not.
- **Ablation.** playground reruns the oracle with one input unit deleted and
  requires each run to score at most the archetype's `ablation_max`. A flat
  directory ablates file by file; a tree directory such as `repo/` ablates as one
  unit. `--ablation sample` is the default and takes one unit per input directory
  plus up to eight more chosen from the data hash. Run `--ablation full` for
  sign-off, and use `--jobs` to run containers in parallel. With 50 or more files
  this passes only if every file feeds the spine or a weight-5 check. A file
  whose deletion costs nothing is padding, and the full pass will find it.
- **Twelve or more trap instances in every data file**, drawn from the 12 or more
  trap types across the bundle. That is twelve firing units per file, not twelve
  distinct rules per file.
- At least one same-name-different-unit pair, and at least one pair that joins
  only after the documented normalization. Scatter rule-firing units across many
  files and keep them out of the first 50 rows of any file.
- Decoys inside real inputs: identical duplicates with no conflict, a value that
  looks like the other unit but is annotated, a record one second inside the
  boundary. Over-applying a rule must cost as much as under-applying it.
- Scale: 2,000 to 50,000 records, large enough that reading cannot replace a
  program and small enough that a correct program finishes in seconds.
- Generate from a fixed seed and commit only the generated bytes. Never commit the
  generator. A record-incidence table (trap, records that fire it, graded value
  that changes) goes in `TRUTH.md`. A trap whose wrong handling leaves every
  artifact byte-identical is invisible, so cut it or change the data.
- The verifier has **none** of the input directories. D1 now bans an
  unconditional read of every COPY destination, not only `/app/data`, so
  `/app/repo` and `/app/fixtures` crash the verifier the same way. When a check
  needs shipped input, embed a zlib-compressed copy in `test_output.py` as a
  module-level constant, decompress it inside the check, and keep any read of an
  input path behind an existence check (D1, TS-1).

### 7.1 Building the corpus so it defeats a frontier model

The file count and the line floors are the contract. They are not the
difficulty. A corpus of sixty well-formed files on one subject is a reading
exercise. These are the properties that make the same sixty files hard, each
aimed at a mechanism in 15.2.

**Size it so the corpus cannot be held in context.** Retrieval and reasoning
quality fall as context grows, and many models are below half their
short-context score by roughly 32k tokens. A corpus a model can read end to end
invites it to reason over the text directly, which is its strongest mode. A
corpus it must process with a program forces it to trust that program, which is
where the per-unit failures live. The purpose is to select the approach, never
to exhaust the model, so keep a correct program finishing in seconds.

**Put the deciding evidence in the back half of every file.** A solver that
reads the first fifty rows must not see a representative sample. This is not a
trick; real data behaves this way, and it defeats generalising from the head.
Trap 41 goes further: a rule that cannot fire until a running value crosses a
threshold appears only late by construction.

**Spread one question across directories.** With several input directories the
natural shape is one evidence class per directory: records in `data/`, the
source tree in `repo/`, operational history in `logs/`, reference tables in
`policies/`. Make at least one graded figure need three of them (trap 50). A
solver that reads one directory has strictly less than one that reads all of
them, and the ablation gate then passes honestly because every directory is
load bearing.

**Make the handles collide before you make them unique.** Trap 39 is the
measured weakness. Every entity should be reachable by several legal handles,
at least one handle should collide across two entities, and the canonical
resolution should be documented and non-obvious. Entity resolution over a long
run is where the 8.5x amplification was measured.

**Decoys inside real inputs, never decoy files.** A decoy is a record that looks
governed by a rule and is not: an identical duplicate carrying no conflict, a
value annotated as already converted, a record one second inside a boundary.
Over-applying a rule must cost as much as under-applying it. A file whose only
job is to waste time is padding, it fails the ablation gate, and 5.1 forbids it.

**Every malformed row must be malformed quietly.** Trap 42 and the recovery row
in 15.2. A row that crashes a naive parser hands the model the feedback that
lets it recover. A sentinel that parses as a number, a short row a permissive
reader pads, a date that parses under the wrong format: those stay silent and
reach the rejects contract only if the solver read the rule.

**Ship one advisory wrong value, signposted.** Trap 44, and CL-6 requires the
signpost. A prior period's resolved mapping or a vendor's own reconciliation,
correct for most units and wrong for a documented subset, marked advisory in a
spec. This gives self-conditioning a ready-made first error that the solver who
checks the evidence avoids.

**Write the spec documents as `.md`.** The 2,000-line floor applies to record
files (`.csv`, `.tsv`, `.jsonl`, `.txt`, `.log`), not to specification, schema
and policy documents. Those carry the delegated rules from 11.1 and still have
to earn their place under the ablation gate.

**Record the incidence before you generate.** For each trap: how many units fire
it, in which files, and which graded value changes when it is handled wrong. A
trap whose wrong handling leaves every artifact byte-identical is invisible, so
cut it or change the data. That table goes in TRUTH.md and it is what lets you
answer the ablation and AL-27 questions without re-deriving them.

---

## 8. Test channel (tests/test_output.py)

### 8.1 Mechanical rules

```python
from pathlib import Path
from rewardkit import criteria, criterion

@criterion(description="primary ledger equals the independent recomputation on every unit")
def primary_ledger_exact(workspace: Path) -> bool:
    try:
        ...
    except Exception:
        return False
    return produced == expected

@criterion(description="a shipped input file differs from its shipped bytes")
def negative_input_modified(workspace: Path) -> bool:
    # True when the cheat happened. A missing file is graded elsewhere.
    ...

criteria.primary_ledger_exact(weight=5)
criteria.negative_input_modified(weight=-3)
```

- `from rewardkit import criteria, criterion` (A1). Use 10 to 35 checks, with 28
  to 32 as the target (A3). Each check is a top-level function taking only
  `workspace` and returning a bool (A4, A5).
- No `{` or `}` in a description, because rewardkit runs `str.format` on it (A4).
- Every check registered exactly once at module level, `weight` only, an integer
  literal in {5, 3, 1, -1, -3, -5} (W1 to W3). Weights not all identical, at least
  one positive and one negative, `negative_` prefix if and only if the weight is
  negative, and the sum of negative magnitudes at most the positive sum (W4 to
  W7).
- **No check may raise** (TS-29). An exception aborts the whole run and no reward
  is written. Wrap every read, return False on bad or missing output, and handle
  hostile output (huge files, symlinks, non-UTF-8 text).
- Nothing at module level does work beyond constants, checks and registrations.
- O1 and DS-24: `solve.py` shares under 35 percent of its substantive lines with
  `test_output.py`, with a warning from 20 percent. Shared corpus generation is
  fine. Shared grading logic is not.
- TS-12: outcome-driven only, never grading command history or console output.
  TS-13: one property per check. TS-26: no two checks of any sign pay for the
  same observable. TS-27: never grade source tokens, identifiers or line counts.
  Run the code.

### 8.2 Hardening when grading executes agent code (TS-24, TS-28, H1 to H5)

Run delivered code only under dropped privileges, for example
`setpriv --reuid=nobody --regid=nogroup --clear-groups`, with a timeout, a
scratch working directory and the network unavailable. `/tests` is already
`go-rwx` from `test.sh`. Never let agent code write into a path a later check
reads as ground truth. No check may mutate the tree it grades.

### 8.3 Grade on inputs the agent never saw

Where the archetype delivers a program, transform, tool or repaired code base,
generate a held-out tier inside the check from a seed constant, run the delivered
code on it, and compare against the verifier's own recomputation. The visible
tier in the shipped input directories shows the simplest documented layout. The held-out
tier exercises the full rule interaction on at least 85 percent of its cases, at
another scale, with legal combinations that never co-occur in the visible data,
boundaries, empty and maximal inputs, and reordered unordered input. The seed
picks values, never rules. Keep the held-out tier deterministic. The instruction
says only that the deliverable will be run on unseen inputs.

Add **metamorphic checks**: duplicate every unit, scale every quantity, split a
period in two, permute unordered records, then assert the output moved exactly as
the spec says. For service-interaction, probe with requests the agent never saw.

### 8.4 Assertion catalogue (use at least ten)

1. Whole-artifact semantic equality against the recomputation (the backbone of
   the weight-5 checks).
2. Whole-sequence equality under canonical order.
3. Cross-artifact identity across three artifacts, so no two-right-one-wrong
   arrangement passes.
4. Self-report reconciliation.
5. Class-partition completeness: accepted plus rejected plus unresolved equals
   input, and no unit sits in two classes.
6. Boundary sweep in one check.
7. Tie sweep.
8. Reason-code exactness over the closed set.
9. The unresolvable case, and nothing else, in the unresolvable artifact.
10. Determinism: run twice, compare bytes.
11. Independent precision: integer minor units by a different route, exact.
12. Carry and reset at every period boundary.
13. Held-out execution (8.3).
14. Metamorphic relation (8.3).

Patterns for absence (inputs unmodified, no extra files, no partial artifact)
are now **negative** checks under TS-25. Exact comparison only: integer minor
units or `Decimal`, no tolerance unless the instruction states one (TS-17,
TS-18). Each load-bearing trap needs at least one of patterns 1 to 6 behind it.

### 8.5 CL-4: partial credit, reconciled with conjunctive grading

The blueprint concentrates weight on whole-artifact conjunctive checks. Gate 05
CL-4 fails "an answer almost entirely right scoring as though entirely wrong",
which happens through one whole-object equality settling N independent facts, or
many checks keyed to one comparison. Both are satisfiable:

- **State the bar.** If an artifact counts only when every unit is exact, say so
  in the instruction. CL-4 exempts an exactness bar the instruction states out
  loud.
- **One check per comparison.** Never register several weighted checks that all
  turn on the same dict equality (that also breaks TS-26).
- **Decompose along the trap axes.** Give separate checks to facts that are
  independently discoverable (per artifact, per class, per boundary family). A
  single check that legitimately owns most of the reward because it grades the
  main outcome is good design per CL-4. Low scores then come from correlated
  failure on the spine, not from a cliff.
- **Prove it.** Gate T3 in 10.3 is CL-4 in numbers. Record "one fact wrong
  scores X" in your private notes. Gate 05 asks for that number.

### 8.6 Negatives and nop

8 to 10 `negative_` checks, each naming one shortcut and firing only on it
(TS-16), returning True when the shortcut happened, with an inline comment
(TS-15). Every negative must return False when the artifact is simply missing,
or nop goes below zero. Good targets: a hardcoded visible answer, embedded
visible records, reading `/app/data` at run time instead of the input it was
handed, output that depends on filenames or order, nondeterminism, modified
inputs, extra files at output paths, a network or shell-out dependency. Every
positive check must fail on the untouched container.

### 8.7 Weight quota (roughly 30 checks)

| Item | Count |
|---|---|
| patterns 1 to 6 and 13 to 14 at weight 5 | 6 to 8 |
| patterns 7 to 12 at weight 3 | 8 to 10 |
| parse or shape at weight 1 | at most 2 |
| `negative_` checks | 8 to 10 |

Never pay for existence, parseability or shape alone. A weight-1 parse check is
fine only if the weight-5 content checks cannot pass without it. TS-20: weights
must track semantic importance.

### 8.8 Accept every answer the instruction allows (law 4, CL-5)

A strict check that demands something the contract never promised does not make
the task harder. It makes it a guessing game about your conventions, it fails
CL-5, and it costs the honest senior engineer exactly as much as the careless
model. Run this before you ship, one assertion at a time.

**The procedure.** For each check, write down what it demands **beyond the
answer being right**. The recurring five:

| Hidden demand | Legitimate only when |
|---|---|
| list or row ordering | the contract states the order, or the check sorts both sides before comparing |
| key or field spelling | the name appears in an agent-visible file (DS-25), or the check is case and order insensitive on parsed data |
| path and filename form | the artifact path is declared in `task.toml` and named in the instruction |
| number representation | the contract fixes it (integer minor units, a named precision, a rounding mode and stage) |
| letter casing of values | the enum is closed and written out, or the check normalises before comparing |

Each row must land in one of three states: stated in the contract, shown by an
example the agent is actually given in the shipped input, or not enforced at
all. Anything else is a defect, and the fix is usually to loosen the check
rather than to add a sentence, because a contract that pins presentation is
spending its length budget on the wrong thing.

**Compare parsed values, never bytes**, unless the contract makes the bytes
themselves the meaning and says so. A JSON check that loads both sides and
compares dictionaries does not care about key order or whitespace, and that is
correct. A byte comparison of the same file grades formatting.

**The multiple-correct-form test.** Where the contract genuinely permits more
than one form, enumerate the permitted forms and confirm the check accepts each.
Two that recur: a number the contract allows as either an integer or a decimal
with trailing zeros, and an optional field the contract says may be omitted or
present as null. Write the check against the permitted set, not against the one
form your oracle happens to emit.

**Where this trades against difficulty, and where it does not.** Law 4 never
weakens laws 1 to 3. An exactness bar on *values* is difficulty and is allowed,
and 8.5 says to state it out loud so CL-4 is satisfied. An exactness bar on
*presentation* is telepathy. The line is whether a senior engineer who read the
whole contract and got every value right could still fail. If yes, you are
grading convention rather than correctness.

---

## 9. Judge channel (tests/judge.toml)

### 9.1 Mechanical rules

```toml
[[criterion]]
id = "R1"
name = "r1_reports_tiebreak_count_and_winner_class"
description = "The response states that 37 ties were resolved by settlement time, that 11 of them fell in the reversal class, and that the residual of each of the three stated identities is zero."
type = "binary"
weight = 5

[criterion.annotations]
mode = "judged"
type = "task completion"
evaluation_target = "user_facing_message"
importance = "critically_important"
```

(Sample figures only. Every real figure comes from your reference run.)

- Keys exactly `id, name, description, type, weight`, then annotations (J1). No
  `negate`, no `points`. `id` is R1, R2 and so on with no gaps (J2). `name` is
  unique and matches `^[a-zA-Z0-9_-]{1,64}$` (J3). `type = "binary"` (J4).
  `weight` is an integer in {5, 3, 1, -1, -3, -5}, never a float (J5).
- **Annotations carry exactly four keys, in this order**: `mode`, `type`,
  `evaluation_target`, `importance`. All four are non-empty strings, and the
  order is checked, so the right keys in the wrong sequence still fail (J6).
  `category`, `kind`, `serves`, `residue`, `evidence`, `contract_sentence` and
  `contract_file` are retired and each one fails.
- Values (J7): `mode = "judged"`. Annotations `type` **is the category**, one of
  `task completion`, `instruction following`, `tool use`, `agent behavior`,
  `factuality and hallucination`, `safety and boundaries` (spelled with "and";
  the ampersand fails). `evaluation_target` is one of `final_answer`,
  `user_facing_message`, `trajectory`, `state_change`. `importance` is
  `critically_important` or `important`.
- `type` means two different things in the same file. On the criterion it is the
  answer format and is always `binary`. In the annotations it is the category.
- Never let the word "negative" appear in an annotations `type`, and never let
  "optional" appear in `importance`. rewardkit reads both strings: the first
  silently turns on negation, the second marks the criterion optional. The closed
  value sets prevent this, so do not invent values.
- The three-way classification (outcome, constraint, conduct) is still how you
  design and how gate 04 reviews, and it is no longer written in the file. A
  constraint criterion carries `type = "instruction following"`, and an outcome
  or conduct criterion never carries that label. Keep your own
  criterion-to-kind mapping, with each constraint's quoted sentence and its file,
  in your private notes and in TRUTH.md under Verification, because JD-16 still
  requires the sentence to exist and the gate checks it by reading.
- Phrasing (J9 to J12): `final_answer` and `user_facing_message` start with "The
  response"; `trajectory` and `state_change` start with "The agent". Do not use
  not, without, fails to, cannot or instead of. A negative describes the bad
  behaviour as happening and its negative weight punishes it. No vague words:
  approximately, around, about, roughly, mostly, typically, often, properly,
  correctly, clearly, adequately, many, several, few, repeatedly ("some" warns).
  No brackets, placeholders, dashes or tag prefixes.
- Importance pairing (J13): `critically_important` needs weight 3 or 5,
  `important` needs 1 or 3.
- Whole file: 8 to 35 criteria (G3), at least one positive and one negative (G4),
  weights not all identical (G5), and the sum of negative magnitudes at most the
  positive sum (G6).
- JD-16 still requires every constraint criterion to quote a sentence that
  really exists in `instruction.md` or a spec it points to, to cover exactly one
  rule, and to be graded once. The `contract_sentence` key and the playground A3
  verbatim check are gone, so nothing mechanical catches a constraint criterion
  invented out of nothing. Check each one by hand against the instruction before
  you ship.

### 9.2 What the judge may grade (JD-8, JD-9, AL-F0d)

**Tests read artifact bytes. The judge reads the trajectory and the closing
message.** No observable may be graded on both sides, whatever the wording. A
criterion restating a check's value is a fail. Process value is the judge's job:
derivation, verification habits, honest reporting, safe behaviour. Ownership
rule (JD-16): if a test could check a rule, the test owns it. Tool-use rules,
ordering rules and scope over undeclared paths show up only in the trajectory, so
the judge owns those. JD-17: deleting every constraint criterion must still leave
a substantial task. JD-18: when the agent writes code, at least one criterion
judges the quality of that code without prescribing a style.

### 9.3 The counterfactual payload, the judge's only hard positive

A criterion naming an activity is free credit, because a strong model does it
whether or not it ends up correct. A criterion naming an aggregate is narratable,
and usually overlaps a test. So in the artifact-design step, choose **eight to
ten quantities a correct run must state in its closing message that appear in no
artifact**, and make `instruction.md` require the message to state each one.
Shapes that work: which rule governed the most units and the count; how many
units satisfied two rules and which rule won; how many units the normalization
changed; which candidate reading was rejected and on what evidence; the residual
of each identity; how many units changed class between two named stages; ties
resolved; boundary units excluded. Each needs the full per-unit path. If you
cannot find eight, return to artifact design.

**Conjunction is the multiplier.** With per-fact accuracy `p`, a `k`-fact
criterion is earned with probability `p^k`. At `p = 0.7`: k = 1 gives 0.70, k = 4
gives 0.24. Write every counterfactual criterion over three or four facts that
must all hold. JD-5 wants one observable, and the closing message is one
observable, so a multi-fact statement about it is fine. The judge defaults to
No, so a fact missing from the message means the criterion is not earned. That
is fair only because the instruction required the fact. JD-7 still binds: the
reference run must state every fact correctly.

**Grade the inference, never the naming.** "The response names the reading it
settled on" pays a wrong run as readily as a right one. Measured: such criteria at
weights 5 and 3 lifted every mutant from 18 to 28 percent. Put those at weight 1
at most.

### 9.4 Slots (house floor of 25 criteria, target 26 to 32)

The `kind` column is your design classification and is no longer written in the
file. The `annotations type` column is what you actually write.

| Slot | Count | your kind | annotations `type` | `evaluation_target` | weight |
|---|---|---|---|---|---|
| counterfactual figures, 3 to 4 facts each | 9 to 12 | outcome | task completion | user_facing_message | 5 |
| derivation evidence naming the specific evidence the crux needs | 3 to 5 | conduct | agent behavior or tool use | trajectory | **1** |
| stated rules of engagement visible only in the trajectory | 0 to 2 | constraint | instruction following | trajectory | 1 |
| honest reporting against the agent's own computed figures | 1 to 2 | conduct | factuality and hallucination | user_facing_message | 1 |
| code-quality judgement (JD-18) | 1 | conduct | agent behavior | state_change or trajectory | 3 |
| negatives, one triggering action each | 8 to 10 | mixed | mixed, often safety and boundaries | trajectory or user_facing_message | -3 mostly |

**Derivation and conduct criteria sit at weight 1, and that is the single most
important number on this page.** An earlier version of this table put them at
weight 3, which does not hold the band. Worked, with nine counterfactual
criteria at 5, nine derivation criteria at 3, three constraints, honest
reporting and code quality, the positive total is 86. A strong model earns
roughly 70 percent of every conduct criterion by working visibly, which is 18.9
points from the derivation slot alone, or 22 percent of the channel before it
gets anything else right. The projection for that mix is **37.7 percent**, and
the measured 83.33 in 15.1 is the same defect in a cruder form. Moving
derivation to weight 1 and cutting the count to three to five takes the same
slot to about 4 points of an 11 percent projection.

The blueprint's "first five are instruction following" is no longer a QC rule.
Use constraint criteria only for real trajectory-only rules your instruction
states, and never invent rules to fill slots. A derivation criterion survives
only when it names the specific evidence: "the agent inspects the data" is free
credit, while "the agent states which of the three layering orders it tested and
what each produced" is not. Conduct criteria must pass JD-15 step 1 (every
competent route satisfies them) or step 2 (the approach raises the odds of a
correct result).

### 9.4a The arithmetic that decides whether both models fail

The slot mix in 9.4 is necessary and it is not sufficient. Run this worksheet
before writing a single criterion, because it tells you which part of the design
actually holds the band, and it is not the part most authors tune.

Take the recommended mix: 9 counterfactual at 5, 4 derivation at 1, 1 constraint
at 1, 1 honest reporting at 1, 1 code quality at 3, and 9 negatives at -3. The
positive total `V` is 51. Let `p` be the model's per-fact accuracy on your
counterfactual quantities, so a 4-fact criterion is earned with `p^4`. Assume a
strong model earns 80 percent of the weight-1 conduct criteria and 4 negatives
fire.

| per-fact `p` | `p^4` | judge channel, 4 negatives fire | judge channel, none fire |
|---|---|---|---|
| 0.60 | 0.13 | 1.8 | 24.0 |
| 0.70 | 0.24 | 11.0 | 33.2 |
| 0.80 | 0.41 | 25.2 | 47.4 |
| 0.90 | 0.66 | 45.7 | 67.9 |
| 0.95 | 0.81 | 58.9 | 81.1 |

**Read the table as the design brief.** The same rubric, the same weights and
the same counts span 1.8 percent and 58.9 percent. Nothing in the slot mix moved;
only `p` moved. So the question that decides whether Opus 5 and GLM-5.3 fail is
not how you weight the judge file. It is **whether a model with a wrong per-unit
path can still state your counterfactual figures correctly.**

Three consequences, and they are the whole of the method.

**One. Every counterfactual figure hangs off the spine.** A figure the model can
reach by a shortcut, by a summary path, or by reasoning over a sample has a high
`p` no matter how you word the criterion. A figure that requires the full
per-unit derivation inherits the spine's correctness, so a model that got the
spine wrong states it wrong, and `p` collapses. When you list the eight to ten
quantities in 9.3, write beside each one the trap it depends on. A quantity you
cannot tie to a trap belongs in no criterion.

**Two. Conjunction is what turns a middling `p` into a failed criterion.** At
`p = 0.8` a single-fact criterion pays 0.80 and a four-fact criterion pays 0.41.
Four facts is the floor for this bar; three is acceptable only when every fact
is spine-dependent.

**Three. The negatives are worth about 22 points of the channel.** At `p = 0.7`
the projection is 11.0 percent with four negatives firing and 33.2 with none.
That is why gate R2 asks for at least four that can actually fire on an honest
run, and why 9.5's honest-mistake negatives matter more than the anti-cheat ones
that never fired in the measured run.

**The combined figure, since the judge is half of it.** With a test channel at
5 percent: a judge channel at `p = 0.7` gives a reward near 0.080, at `p = 0.8`
near 0.151, and at `p = 0.9` near 0.253. A judge channel you have not made
spine-dependent will carry the whole bundle above the bar on its own, whatever
the test channel does.

**What to do with the worksheet.** Estimate `p` honestly for your figures, by
asking what fraction of them a run with two broken load-bearing traps would
still state correctly. If your answer is above 0.8, the figures are not
spine-dependent and no amount of rubric tuning will fix it; go back to 9.3 and
replace them. Record the estimate, the mix and the projection in your private
notes beside the 10.2 gate numbers.

### 9.5 Judge negatives

The judge's negatives target trajectory and message behaviour; the tests'
negatives target artifact behaviour. Split the failure-mode inventory between the
two layers instead of mirroring it (JD-8, JD-14). Shapes that fire on strong
models honestly: stating a figure as approximate or a range where the contract
requires an exact integer; leaving out an identity residual the contract requires;
a reported figure that differs from what the agent's own run computed; inventing
an answer for the documented unresolvable case; opening a path under `/tests` or
`/logs/verifier`; hardcoding values from a worked example; looping on an
identical failing command. JD-11: every negative must be possible in this task.

**AL-28 penalty stacking.** Group every negative check and every negative
criterion by the single agent action that triggers it. No action may fire more
than one max-severity (-5) penalty across both channels. House rule kept from the
blueprint: the summed magnitude per action stays at 5 or below.

---

## 10. Calibration gates (paper arithmetic before any run)

Write down the **strong-but-wrong profile** first: it parses every input, writes
every artifact well formed, gets the aggregates right, breaks two load-bearing
traps, narrates confidently and never crashes.

### 10.1 Test channel

`P` = positive test weight, `F` = positive weight that fails under the profile.

- **T1:** `F / P` at 0.90, in the range 0.88 to 0.92. That is a test channel
  of 8 to 12 percent. Do not push to 0.95, which is a 5 percent channel and
  undershoots the band. Equivalently
  `hard_total > 9 * easy_total`.
- **T2:** each load-bearing trap alone fails at least 40 percent of `P`.
- **T3:** missing one supporting rule still scores above 50 percent of `P`.
  Missing one load-bearing rule scores at most 60 percent.

The lever is check count and coupling, not weight size. A weight-5 check the
profile fails raises `F / P`. A weight-5 check the profile passes lowers it. When
T1 fails, bind the passing checks to the spine quantity or delete them.

### 10.2 Judge channel

`V` = positive judge weight, `M` = positive weight the profile earns, `N` =
magnitude of the negatives it trips.

- **R1:** `(M - N) / V` in the range 0.08 to 0.12. Below 0.05 is an undershoot
  and is investigated, not celebrated, per the target-band section.
- **R2:** at least four trajectory-or-message negatives trip under the profile
  by a mechanism you can demonstrate from the profile's closing message (for
  example a hedged figure or a missing residual). Pure conduct negatives with no
  message trace do not count toward R2.
- **R3:** the estimated per-fact accuracy `p` on the counterfactual figures is
  about 0.70, in the range 0.65 to 0.75, and every figure is justified by
  naming the trap it depends on. At `p = 0.70` with four negatives firing the
  channel is 11.0 percent, which is the band. At 0.60 it is 1.8 percent, which
  is an undershoot. The 9.4a worksheet shows one rubric spanning 1.8 to 58.9 percent on `p`
  alone, so a bundle that cannot justify a low `p` is not calibrated whatever
  R1 computes. Estimate `p` as the fraction of your figures that a run with two
  broken load-bearing traps would still state correctly.
- **R4:** no conduct or derivation criterion carries weight 3 or 5. At weight 3
  a strong model collects roughly 70 percent of that slot by working visibly,
  which is what produced the measured 83.33 in 15.1.

### 10.3 Worked example

This example lands in the band rather than under it, and uses the corrected 9.4
mix with derivation criteria at weight 1.

**Test channel.** 7 checks at weight 5, 9 at weight 3, 2 at weight 1, so
`P = 64`. Under the profile all seven weight-5 checks fail, seven of the nine
weight-3 checks fail, and one of the two parse checks fails. `F = 57`, so
`F / P = 0.891` and the profile keeps 7 points: **10.9 percent**.

**Judge channel.** 9 counterfactual at 5, 4 derivation at 1, 1 constraint at 1,
1 honest reporting at 1, 1 code quality at 3, so `V = 54`. At `p = 0.70` each
four-fact counterfactual criterion is earned with probability 0.24, so the
profile earns about 10.8 of the 45 counterfactual points, plus most of the
weight-1 conduct criteria and the code-quality criterion: `M = 18.0`. Four
negatives at -3 fire, so `N = 12` and the channel is **11.0 percent**.

**Combined.** `0.5 * 0.109 + 0.5 * 0.110 = 0.110`, or 11.0 percent. Both
channels and the combined figure sit in the 8 to 12 band.

Compare the same arithmetic with the old mix, derivation at weight 3 and no
`p` discipline: the judge channel comes out at 37.7 percent and the combined
figure above 20. And compare it with an over-tuned bundle at `F / P = 0.95` and
`p = 0.60`: test 5 percent, judge 1.8, combined 3.4, which undershoots the band
and triggers the floor investigation in the target-band section.

### 10.4 Near-miss ladder

Mutate `solve.py` once per documented rule, plus once per profile in 10.5.
Score each mutant tests-only. Read the table three ways. A check every mutant
passes grades no rule, so rewrite or delete it. A check the reference fails is
broken. A single-rule mutant above 40 percent means weight sits in the wrong
place. For each mutant that fails a check, at least one judge criterion must
also change verdict on its closing message, or the judge is grading something
the mutant did not change. AL-27: every stated rule has a fixture that triggers
it, and a rule whose mutant passes every check is not graded.

### 10.5 Five solver profiles, each defeated for its own reason

| Profile | Defeated by |
|---|---|
| literal transcriber | withheld rules (5.9), and rules that live in the spec rather than the prompt |
| happy-path solver | held-out inputs outside the visible range |
| local patcher | the invariant exercised in several places, one with no visible symptom |
| visible-sample overfitter | a held-out tier structurally distinct from the visible one |
| correct general solver | passes |

If two profiles fail for the same reason, one of them will get through.

### 10.6 Offline hardness gate

On a scratch copy outside the bundle: run `solve.py` on the corpus, point the
checks at its artifacts (import `test_output.py` and call each check with the
workspace path), and confirm every positive passes and no negative fires. Repeat
for every mutant. Record T1, T2, T3, R1, R2, the ladder, the per-action penalty
table and the "one fact wrong" score in your private notes. Never write these
projections into the bundle as if they were measurements (AL-7). Then run
`playground.py --ablation full` (static, Docker and ablation layers). The tests-only oracle must
read exactly 1.0, nop exactly 0.0, the stub near zero, and every ablation at or
below `ablation_max`.

---

## 11. instruction.md

Mechanical (instruction_qc and validate_bundle):

- C1: the exact sentence `You have N seconds to complete this task.` with `N`
  equal to `[agent] timeout_sec`.
- C2 and C3: never name `test.sh`, `test_output.py`, `judge.toml`,
  `reward.toml`, `rewardkit`, `solve.sh`, `solve.py`, `TRUTH.md`,
  `/logs/verifier`, `reward.txt`, `reward.json` or `ctrf.json`, and never use the
  word reward. C6 warns on "grader", "checker" and "verifier".
- C4: every `/app` path you name exists in the image. C5: every artifact appears
  by its full absolute path.
- P1 to P3: no em or en dashes, none of the banned words (leverage, utilize,
  utilise, delve, meticulous, meticulously, comprehensive, comprehensively,
  endeavor, endeavour, furthermore, moreover, subsequently, aforementioned,
  henceforth, myriad, plethora, paradigm, robustly, seamless, seamlessly,
  holistic, pivotal, facilitate, streamline, elucidate, ascertain, or the same
  kind of word), and no AI-tell phrases.
- validate_bundle §2.2: 6,000 characters is a drafting guideline, not a QC
  rule. Past it the validator prints an informational line and QC sets no cap;
  the hard ceiling is 20,000 characters, which fails. Aim under 6,000 anyway,
  because a prompt that cannot be held in one reading is a specification defect.
  §2.5: carry one sentence
  forbidding online solution lookup. That is not network wording under IN-11.
- IN-11: no fetch, download or URL-as-source sentences. IN-4: no benchmark
  self-references or GUIDs.

Hardness (house rules, all QC-legal):

- **At least twenty distinct requirements**, dense and never ambiguous (IN-16).
- **Plain prose paragraphs**, with schemas, shapes and worked single-rule
  examples in fenced blocks. QC now allows headings and bullets, but this house
  rule keeps the instruction free of scannable surface, which is a difficulty
  lever.
- **Three or four composed defined terms**, each defined once in full and each
  used in three or more later rules.
- State each rule where it belongs, not where it is used. Express rules as
  properties of the output, not procedures. Give one explicit precedence sentence
  wherever two rules could both apply. Use multi-predicate conditions. Close every
  vocabulary ("these are the only four reason codes"). Be exact with
  quantifiers. Let presentation order differ from execution order.
- **Specified but uninstructive.** Cut every step list, every "first, then,
  next", named algorithms, named libraries, root-cause labels, the file-by-file
  map, reasons a rule exists, signals about which parts are hard, reassurance,
  and any closing recap. Keep every graded rule (or its withheld evidence), every
  defined term, every artifact path and contract, the closed vocabularies, the
  unresolvable-case obligation, the negative-space obligations, the
  closing-message figures from 9.3, and the timeout sentence. Test for each cut:
  would a check or criterion fail a solver who never read this sentence? If yes,
  put it back.
- Point once at the specification documents in the input directories. AL-1 and IN-8 let
  the prompt delegate to a spec the agent can read, so the detailed rules live
  there.
- **Fresh-reader check.** Give the finished instruction to a fresh session and
  ask it to list every requirement. Requirements it **missed** are the difficulty
  working. Requirements it **misread** are ambiguity, and each one must be
  rewritten until only one reading is left.

### 11.1 Making the 6,000 character guideline carry an expert task

Six thousand characters is roughly one dense page. It is a guideline rather
than a QC rule, and it is still the right target, because a flat page of twenty
requirements is a checklist a model works through and a longer one invites
skimming. These are the devices that put expert load
into that page without adding a word of ambiguity. Each one is QC legal, and
each aims at a mechanism in 15.2.

**Delegate the detail, keep the obligations.** AL-1 and IN-8 let the prompt
point at a specification in the input directories. So `instruction.md` carries
the deliverable contracts, the defined terms, the closed vocabularies and the
closing-message figures, and the spec documents carry the per-rule detail. The
page stays readable and the contract stays complete. This is also what lets the
corpus hold fifty rules without a 20,000-character prompt.

**Compose terms so one misreading costs six rules.** This is the highest-value
device in the section. Define `effective window` once, with the offset, the
half-open boundary and the per-entity calendar folded into the definition, then
use the term plainly in six later rules. A solver who reads the definition
loosely gets six things wrong, and those six failures are correlated in the
sense of 5.5, because they share one root. Three or four such terms, each used
three or more times, is the target. Nothing is hidden: the definition is stated
in full before first use.

**State the obligation, never the order.** Describe the deliverables in the
order a reader wants them, which is not the order they must be computed. The
execution order is derivable from the dependencies you stated, and deriving it
is the work. This costs nothing in clarity and it defeats the solver that
transcribes the prompt top to bottom.

**Put one terminal obligation early.** Trap 47. One requirement about the final
artifact, stated plainly in the first third and never repeated, that only takes
effect at the last stage. Catastrophic forgetting is a measured failure mode at
long horizons, and a requirement stated once in its proper place is fair.

**Require the counterfactual figures in the prompt.** The 9.3 payload only works
if the instruction demands each figure, because the judge defaults to No on a
fact the message never states. Name all eight to ten explicitly, as properties
of the closing message. This is usually the densest paragraph in the file and
it is the one that carries the judge channel.

**Use multi-predicate conditions and exact quantifiers.** A rule that fires when
one condition holds and another does not is harder to implement than two
separate rules and exactly as unambiguous. Every, each, exactly one, at most
one, at least one: these change behaviour and cost nothing.

**Say the exactness bar out loud.** CL-4 exempts a bar the instruction states.
One sentence naming which artifacts count only when every unit is exact lets the
checks be strict without failing the partial-credit gate.

**Write no summary and no closing recap.** A recap invites the model to work
from the recap and skip the body, and every requirement outside it is dropped.
Ending without one withholds nothing, because every requirement is stated once,
in full, in the body.

**The two checks before you ship the prompt.** First, count the characters; if
you are over the 6,000 guideline, move detail into a spec document rather than
cutting an obligation, and never approach the 20,000 hard ceiling. Second, run
the fresh-reader check above and sort what comes back:
missed is difficulty, misread is ambiguity and must be rewritten.

---

## 12. solution/TRUTH.md

- Title line exactly `# TRUTH.md - <task-name>`, at least 4,000 characters.
- Eight `##` sections in this order: Defect, Load-bearing work, Verification,
  Root cause, Solution shape, Ordered plan, Pitfalls, Provenance.
- Defect: numbered items labelled `(focal)`, `(drift)` or `(trap)`, at least two
  focal and at least one of each of the others, each naming the check it defeats.
  It also holds the trap incidence table and an `Out of bounds:` paragraph.
- Verification: the test totals must equal the registrations in `test_output.py`
  and name every negative check, plus the judge criteria and the 20-plus-row
  traceability matrix (requirement, artifact, checks with weights, criteria). Any
  oracle score it claims is tests-only. No judged-channel oracle score exists.
- Root cause: the crux sentence, the spine, the interaction matrix and the
  withheld-rule evidence pointers. The last sub-topic is `**Red lines.**`.
- Ordered plan: under twenty steps, each naming the input it reads and the
  artifact it advances. If it does not fit, cut scope.
- Pitfalls: the ranked failure-mode inventory table from 5.12.
- Provenance: a fenced `yaml` block with `uuid`, `instance_id`, `task_name`,
  `fix_patch_sha256` (sha256 of `solve.sh`), `solve_py_sha256`, `language` and
  `status`.
- **DS-27:** no archetype or template name, seed, tooling or model credit,
  changelog or review history, and no `authored_by`. Authorship lives only in
  `task.toml`. Known conflict: `validate_bundle.py` FORMAT_SPEC §15.5 still lists
  `authored_by` as required. The checklist wins, so leave it out and record the
  FORMAT_SPEC §15.5 finding as a known generator conflict. None of the shipped
  `Tasks_INPUT/*/solution/TRUTH.md` files carries `authored_by`.
- **DS-22:** after every change, re-read TRUTH.md against `solve.py`,
  `test_output.py` and `judge.toml`. A trap the data cannot trigger, or a focal
  item nothing grades, is a fail.

---

## 13. QC execution and Step 10

Run from the repo root and collect everything before you fix anything:

```bash
python3 Input_Bundle_QC/structure_qc.py   "<abs bundle>"
python3 Input_Bundle_QC/instruction_qc.py "<abs bundle>"
python3 Input_Bundle_QC/tests_qc.py       "<abs bundle>"
python3 Input_Bundle_QC/judge_qc.py       "<abs bundle>"
python3 "Input Bundle Generator New/validate_bundle.py" "<abs bundle>" --archetype <name>
python3 "Input Bundle Generator New/playground.py" "<abs bundle>" --ablation-max <value> --ablation full
```

The scripts exit 0 for pass, 1 for fail and 2 for a usage error. Then run the
five model gates, each in a fresh session: `01_Instruction_QC.md`,
`02_Data_Solution_QC.md`, `03_Tests_QC.md`, `04_Judge_QC.md`,
`05_Alignment_Integrity_QC.md` (including F0a to F0e and CL-1 to CL-10, each with
the number or file and line it asks for). Then Step 11, the fresh-eyes
re-check of coverage and overlap.

**Step 10.** Preflight first: `harbor --version` (0.24.0 or newer), `docker ps`,
and `ls "<abs bundle>"`. Then:

```bash
python3 Input_Bundle_QC/exe_copy.py "<abs bundle>" /tmp/step10run
python3 Input_Bundle_QC/exe_copy.py "<abs bundle>" /tmp/stubrun --stub
for i in 1 2 3 4 5; do harbor run --path /tmp/step10run --agent oracle --env docker --job-name oracle-$i -y; done
harbor run --path /tmp/step10run --agent nop    --env docker --job-name nop-1  -y
harbor run --path /tmp/stubrun   --agent oracle --env docker --job-name stub-1 -y
```

Read `result.json` at `verifier_result.rewards.reward`. All five oracle runs must
read exactly 1.000, and nop exactly 0.000. Judge the stub and name every check
that paid it. A trial with `exception_info` or `exception.txt` is not a score.
`ValueError: network_mode='no-network' is not supported` is a host limitation,
and `exe_copy.py` already opens the network in the copies. Never edit the bundle
to make Step 10 pass, delete both copies afterwards, and never fabricate or copy
numbers. If the preflight fails, mark Step 10 NOT RUN with the exact error.

**Trajectory evidence.** Run the shipped bundle (never an `exe_copy` copy) against
the reference models with the judge key passed. Read both channels per section 3.
Both should land in the 8 to 12 band. If either is well above 12, list which checks
passed and which criteria were met, match them against the profile, fix the
weight or the narratable criterion, rerun 10.6, and run again. If either channel
sits at or below zero on every run, confirm that the oracle still scores 1.000 and
a one-supporting-rule mutant still clears 50 percent. One run is one sample. Rerun
near a boundary. Hand over the figures with the run directory. They never go in
`TRUTH.md`.

---

## 14. Definition of done

- [ ] Tree matches section 1 exactly. No README.md, cheat/, rubric.json,
      test_weights.json or stray file. `solve.sh` and `test.sh` are LF (`file`
      reports no CRLF).
- [ ] task.toml matches 2.1 letter for letter: schema 1.4, per-role network_mode,
      no allow_internet, no difficulty, a real author name and an ethara.ai email
      built from it, a truthful category, junior time above expert time, and the
      artifacts equal to the archetype manifest.
- [ ] Both Dockerfiles, test.sh and the judge header are the pinned templates.
      Artifact directories are writable by uid 1000. reward.toml weights equal
      0.5 / positive total per channel at full precision.
- [ ] Category used as given. Archetype chosen deliberately, not format-recovery,
      never changed, and passed explicitly to the generator and validate_bundle.
- [ ] No banned mechanism. Paraphrase and retrieval tests passed. No other slug
      named. Real algorithmic depth.
- [ ] One crux, one spine, three burdens, a DAG at least four levels deep with two
      implicit links, and the identity triangle.
- [ ] More than twelve traps, each passing 5.4, each interacting with two or
      more others, each silently plausible, each in the traceability matrix.
      Four to six load-bearing traps with wrong priors of 80 percent or more, each
      behind a weight-5 check. Two or three structural levers, one an isolation
      breaker. At least five evidence and state levers.
- [ ] Three to six withheld rules, each with a reading enumeration in the
      private notes, and the evidence carrying no graded quantity.
- [ ] Corpus: 50 to 60 files across one or more named input directories, each
      directory COPYed in the Dockerfile and holding at least one file, no loose
      files in `environment/`, record files at 2,000 lines or more, 20,000 lines
      or more in total, every file named by the instruction or a spec, ablation
      within `ablation_max` on a `--ablation full` pass, twelve or more trap
      instances per file, decoys, nothing firing in the first 50 rows, seeded,
      generator not committed.
- [ ] No answer key anywhere in the image (DS-26), `/tests` go-rwx, every
      compared value recomputed inside the verifier.
- [ ] Every literal the checks require stated in an agent-visible file (DS-25,
      CL-5). Coverage holds both ways (AL-1, AL-2). No fact graded by both
      channels (AL-F0d, JD-8).
- [ ] test_output.py: 10 to 35 checks (target 28 to 32), bijective
      registrations, the locked scale, at least one negative, negative_ if and only
      if negative, negatives at most positives, no check able to raise, no
      absence graded as a positive, no source-token grading, held-out execution
      plus metamorphic checks where code is delivered, unprivileged execution,
      O1 under 35 percent.
- [ ] judge.toml: 25 to 35 criteria; annotations carry exactly `mode`, `type`,
      `evaluation_target`, `importance` in that order and no retired key; every
      annotations `type` is a category value; 8 to 10 counterfactual figures at 3
      to 4 facts each and all required by the instruction; specific derivation
      criteria; one code-quality criterion when code is written; 8 to 10
      negatives; G6 balance; JD-7 true of the oracle; every constraint criterion
      checked by hand against a real sentence in the instruction.
- [ ] AL-28: no action fires more than one -5 across both channels, and no
      action exceeds 5 in summed magnitude.
- [ ] Gates T1, T2, T3, R1, R2, R3 and R4 recorded with real numbers in the
      private notes, the near-miss ladder and the five-profile mutants run, and
      the CL-4 one-fact-wrong score recorded. R3 carries the estimated `p` and
      the trap each counterfactual figure depends on.
- [ ] instruction.md: 20 or more requirements, the timeout sentence, all C and
      P rules, inside the 6,000-character guideline, plain prose with fenced shapes, composed
      terms, closed vocabularies, a precedence sentence, no route hints, no recap,
      offline wording, the closing-message figures required, and the fresh-reader
      check done.
- [ ] TRUTH.md: the section 12 shape, no production narrative, no authored_by,
      and in agreement with the shipped solution and checks.
- [ ] All four QC scripts exit 0, validate_bundle shows no FAIL apart from the
      documented FORMAT_SPEC §15.5 conflict, playground passes, the five model gates show no
      fail findings, and Step 11 is done.
- [ ] Step 10: five oracle runs at 1.000, nop at 0.000, the stub judged, all from
      `exe_copy.py` copies, or NOT RUN with the exact preflight error.
- [ ] A trajectory run against the reference models with both channels in the
      8 to 12 band, read from rewardkit's outputs, handed over with the run
      directory. A channel near zero was investigated against T3, section 17 and
      the fired negatives before being accepted.

---

## 15. The frontier-model failure model, measured

Sections 5 to 10 tell you what to build. This section tells you **why those
levers work on a frontier model**, using one measured run of this project and
the published failure research. Everything here is a mechanism you can aim at,
not a style preference. Read it before designing the crux, because the levers
that move a frontier model are not the levers that move a careless reader.

### 15.1 The measured run, and what it proves

One Opus 5 run of `kvec-meter-settlement-reconciliation` is recorded in
`Output/kvec-meter-settlement-reconciliation/`. The numbers:

```
test_weights_percentage     17.12     25 of 146 positive test weight
rubric_weights_percentage   83.33     15 of 18 positive judge weight
combined                    50.23
```

**The test channel nearly worked and the judge channel gave the task away.**
Read the judge file against its result and the cause is plain. It carries 11
criteria: six positives, every one at weight 3, and five negatives.

The six positives, paraphrased from the shipped file, are all **conduct**: the
agent compares an intermediate against an independent control, the agent picks a
winner between two disagreeing sources, the agent reads the data contract before
parsing, the agent prints header and footer lines, the agent re-runs its
transform on a copied directory, the agent leaves the transform split into
single-purpose functions. A competent model does five of those six by habit, on
the way to a wrong answer. It did, and collected 15 of 18.

The five negatives are all anti-cheat: reading `/tests`, editing the input,
running a package installer, fetching from the network, claiming success with no
run behind it. **None of them fired**, because an honest strong model does none
of those things. They contributed exactly zero.

Three fixes follow directly, and they are the highest-value edits available on
any bundle built the same way.

1. **Eleven criteria is too few.** The house floor is 25, and the reason is
   arithmetic: with six positives, missing one costs 17 points of the channel,
   so the model has to miss four of six to come near the bar. With 25 to 32
   criteria and the 9.4 slot mix, there are enough independent ways to lose
   points that a wrong run cannot stay high.
2. **Every positive was earnable by effort.** Not one named a figure that only
   the correct per-unit derivation produces. This is what 9.3 exists to prevent,
   and the measured 83.33 is what skipping it costs.
3. **Every negative was an anti-cheat negative.** Those are worth keeping, and
   they are not a difficulty lever against an honest model. The negatives that
   move the number describe **honest mistakes**: a hedged figure where an exact
   integer was required, an omitted identity residual, a stated figure that
   disagrees with the agent's own run. 9.5 lists them.

The test channel at 17.12 is closer and still above the bar. Of the 25 points it
earned, one was a weight-1 shape check (`feeder_balance_shape`), and the rest
were single-rule checks that one correct branch satisfies. Gate T1 in 10.1 is
what catches this before a run: `F / P` here is about 0.83, under the 0.90 floor.

### 15.2 What the research says fails, and the lever for each

These are published, measured failure modes of frontier agents. Each row names
the mechanism, the measurement, and the section of this guide that exploits it.
None of them requires the model to be careless, which is why they survive a
careful model.

| Failure mode | What was measured | Lever |
|---|---|---|
| **Error cascade from a first mistake** | After its first mistake an agent recovers in only 30.5 percent of runs, never notices it at all in 38.5 percent, and keeps acting in 72.6 percent. One wrong step makes the next 11 to 14 times likelier to be wrong | 5.2 spine, 5.7 deep chain: put the spine early so a wrong branch is inherited by everything after it |
| **Self-conditioning** | Per-step accuracy *falls* as a run proceeds, because the model conditions on its own earlier errors. Scaling the model does not remove it | 5.7 chained dependencies, 5.13 long horizon: make the later stages depend on the earlier ones rather than being parallel |
| **Entity binding drift** | Agents bind an action to the wrong entity 24 to 26 percent of the time in a single step, and drift on 18 percent of multi-step workflows. The amplification was highest on Claude Opus 4.5, at 8.5x | traps 26, 39, 45: several handles per entity, resolved once and used across many steps |
| **Self-verification failure** | GPT-4 step-level mistake finding was 52.87 percent, near chance. Self-critique loops score *below* the model's own first guess. Gains reported elsewhere came from oracle labels, and vanish without them | 5.11 no self-verification path, 9.3 counterfactual figures: a model that cannot check itself states derived figures wrong |
| **Environment feedback is the recovery path** | Software-engineering agents are blind to their own mistakes yet recover anyway, *because* rich environment feedback catches what their reasoning misses. Computer-use agents notice errors but stay stuck without that feedback | 5.10 silent plausibility, trap 42: remove the feedback and the SE agent loses the one thing that saves it |
| **Fabricated success** | A recurring cluster of agents declare success rather than earning it, and some runs scored as solved took destructive actions | 9.5 honest-reporting negatives graded against the agent's own run |
| **Spiralling** | At long horizons frontier models re-call the same tool with minor argument variants and explore dead ends | 9.5 negative on repeating an identical failing command, stated as a count |
| **Long-context degradation** | Retrieval and reasoning quality fall as context grows, and many models are below half their short-context score by roughly 32k tokens | 7 corpus scale: large enough that the corpus cannot be held in context, so the model must write a program and trust it |

**The single most important row is the fifth.** It says that a software
engineering agent survives its own blindness because the environment tells it
when it is wrong: a stack trace, a failing import, a non-zero exit. Every trap
in this guide that produces a crash hands the model that lifeline back. Every
trap that produces a well-formed wrong artifact takes it away. That is why 5.10
is not a style rule, and why a bundle that passes 5.10 on every trap is worth
more than a bundle with twice as many traps that throw.

### 15.3 The arithmetic that sets the horizon

With per-step accuracy `p` over `n` dependent steps, end-to-end success is
roughly `p^n`. At `p = 0.99` and `n = 196` that is about 14 percent, and at
`p = 0.95` it is about four in a hundred thousand. Two consequences for design.

**Dependent steps are worth far more than independent ones.** Twenty
independent sub-problems at 0.95 each give a model twenty chances to collect
partial credit. Twenty *dependent* steps at 0.95 give about 36 percent end to
end, and the weight sits on the end. This is the arithmetic behind 5.7, and it
is why the depth of the chain matters more than the count of rules.

**Self-conditioning means the back half is weaker than the front half.** Per-step
accuracy is not constant; it decays as the model's own errors enter its context.
So put the highest-weight checks on the **last** stages of the chain, the
reconciliation and the identity triangle, not on the parsing at the front. A
bundle that weights the first stage heavily is measuring the model at its
strongest.

### 15.4 The three honest limits of this section

The measured run is one sample of one model on one task, and the published
figures come from other harnesses and other task families. Treat the mechanisms
as reliable and the exact numbers as indicative.

The levers here raise difficulty for a model while leaving a careful human
unaffected, which is the whole requirement. Any lever that would also stop a
senior engineer is out of scope, and 5.1 still bans it.

Nothing in this section licenses withholding a rule, exploiting a parsing quirk
or punishing the model for a capability a human reviewer also lacks. 5.4 and the
QC gates still bind.

---

## 16. Appendix: the blind difficulty probe

Section 10 is paper arithmetic and section 13 proves the bundle grades
correctly. Neither tells you whether a frontier model actually fails. This
appendix is the probe that does, and it is the last gate before handover.

Run it in a **fresh session with no memory of authoring this bundle**, against
the finished bundle. The point is a blind reading, so a session that watched you
build the task cannot run it honestly.

**The bar.** The verdict must come back at 8 or 9 out of 10 on difficulty, with
the bottleneck named as genuine reasoning rather than tedium or volume. A
verdict of 6 or 7 means the crux is reachable by a careful read, so return to
section 5 and add coupling. A verdict of 10 with the probe unable to finish at
all means you may have crossed into unsolvable, so re-check gate T3, the oracle
at 1.000 and the ordered plan in TRUTH.md before believing it.

**Scope discipline matters more here than anywhere else.** The probe sees only
what the agent sees. If it reads `solution/`, `tests/` or TRUTH.md, the result
is worthless and you have to rebuild the probe session from scratch.

Paste this verbatim, with the task directory filled in:

```text
# Task Evaluation Request

## Input
Task directory:

## Scope Guardrails (strict)
1. Copy **only** `instruction.md` and the `environment/` folder to a fresh temp directory. Work exclusively from that copy.
2. Do **not** read, open, list, or infer from any other file or folder in the source path - no solution files, test files, answer keys or READMEs outside those two targets.
3. If you encounter a file that appears to contain the expected answer, stop reading it and state that you did.

## Execution
4. Read `instruction.md` and treat it as the sole task specification.
5. Solve it using the data in the input directories under `environment/`. Assume dependencies declared in the Dockerfile are installed; install anything missing yourself.
6. Produce an actual working solution and run it. Report the real output, not a plan or a sketch.
7. Log your attempt honestly: where you got stuck, wrong turns taken, how many iterations each step needed, and anything in the spec you had to guess at.

## Deliverable 1 - Difficulty Verdict (be decisive, no hedging)
State plainly: **would this task trip a frontier model like Opus 5.5?** Answer yes or no, then justify with:
- A difficulty score out of 10 and the ceiling model you believe solves it one-shot.
- Which specific step, if any, is the actual bottleneck - and whether it is genuine reasoning difficulty or just tedium/volume.
- Whether the answer is guessable, pattern-matchable, or shortcut-able without doing the real work.
- Whether the task is *verifiably* scored (one correct answer) or soft/subjective.
- Failure modes you personally hit, with evidence from your run.

Vague verdicts ("fairly challenging", "it depends") are rejected. Commit to a position.

## Deliverable 2 - Hardening Brief
Give concrete, implementable ways to make this task genuinely hard for a frontier model, grounded in *this* task's data and domain - not generic advice. For each lever, specify the exact edit to make and why it defeats a strong model. Cover:
- **Reasoning depth**: multi-hop dependencies where step N requires a non-obvious result from step N-2.
- **Shortcut elimination**: remove paths where guessing, approximating, or pattern-matching lands the right answer.
- **Data traps**: realistic adversarial content in the input directories - edge cases, encoding issues, near-duplicate records, silent precision loss, misleading column names, plausible-but-wrong decoys.
- **Specification tightness**: constraints that must be satisfied exactly (output format, tolerance, determinism) so partial credit is impossible.
- **Verification strength**: how to make the grader unambiguous and non-gameable.
- **Anti-brute-force**: scale or structure that defeats enumeration while staying solvable by correct reasoning.

Rank the levers by difficulty-added-per-unit-of-work and flag any that would make the task unfair or ambiguous rather than hard.

## Output Format
Three sections: `Attempt Log` -> `Verdict` -> `Hardening Brief`. Keep the log tight; spend your length budget on the verdict and brief.
```

### 16.1 Reading the result against QC

The brief will suggest levers that this harness forbids. Apply this filter
before acting on any of them.

| Probe suggests | Apply it? |
|---|---|
| deeper multi-hop dependencies, step N needing step N-2 | yes, this is 5.7 and the strongest safe lever |
| more realistic data traps and decoys | yes, within 5.6 and the 5.4 legitimacy test |
| larger scale to defeat enumeration | yes up to the point where a correct program still finishes inside the verifier timeout, and never as a stamina test |
| tighter output contract so partial credit is impossible | **partly**. State the exactness bar in the instruction, but CL-4 still requires one wrong fact to cost about one fact. Never collapse the whole score onto one comparison |
| encoding issues, byte-order marks, homoglyphs, Unicode normalization | **no**. These are grader tricks, not domain rules, and 5.1 bans them |
| make the grader stricter on formatting, key order, whitespace, casing | **no**. Grade parsed values. 6.2 and CL-5 fail formatting nitpicks |
| remove information so the answer cannot be derived | **no**. DS-21, F0e and CL-10 fail an unreachable fact. Withhold a rule only with the 5.9 evidence proof |
| add tolerance-free float comparisons | **no**. Use integer minor units or `Decimal`. Float equality is banned |
| penalise the model harder for one mistake | **no**. AL-28 caps one action at one maximum-severity penalty |

Record the probe's score, the named bottleneck and which levers you applied in
your private author notes. If you change the bundle after the probe, the
calibration gates in section 10 and Step 10 both have to run again, and the
probe is worth re-running in another fresh session.
- [ ] The section 17 solvability probe ran in a fresh session and reported zero
      UNREACHABLE items, zero INVENTED literals and no undecided double reading.
- [ ] The section 16 difficulty probe ran in a fresh session on `instruction.md`
      plus the input directories alone, returned 8 or 9 out of 10 with a named
      reasoning bottleneck, and every lever adopted from its brief passed the
      16.1 filter.
- [ ] The four design laws in 5.0 hold: the obvious approach finishes and is
      wrong, decisive facts sit in the data while every output literal stays
      reachable, the instruction states the goal and contract rather than the
      steps, and 8.8 confirms every answer the contract allows is accepted.

---

## 17. Appendix: the blind solvability probe

Section 16 asks whether the task is hard. This one asks whether it is
**possible**, and it is the gate that stops a hard task from being an unfair
one. Run it before the difficulty probe, because a task that fails here is not
hard, it is broken, and tuning its difficulty is wasted work.

It is the practical form of DS-21, F0e and CL-10, and it exists because those
three fail silently. Every mechanical QC check can pass on a bundle whose answer
nobody could reach.

Run it in a **fresh session with no memory of authoring the bundle**, and with
no access to `solution/` or `tests/`.

**The bar.** Every graded fact must be reachable from `instruction.md` plus the
input directories, by reading or by derivation. Long, difficult and
many-stepped is fine and is the point. The failure is a fact that is reachable
from nothing the agent holds.

Paste this verbatim, with the directory filled in:

```text
# Task Solvability Check

## Input
Task directory:

## Scope (strict)
1. Copy ONLY `instruction.md` and `environment/` to a fresh temp directory, then
   delete `environment/Dockerfile` from the copy. Work only from what remains.
2. Do not read, open, list or infer from `solution/`, `tests/`, `task.toml` or
   anything else in the source path. If you open a file that appears to contain
   the expected answer, stop and say so.
3. Assume unlimited time, skill and compute. You are not being timed and you are
   not being scored on speed.

## What to produce
4. Enumerate every distinct thing `instruction.md` asks for: each deliverable,
   each field or column it names, each rule it states, each figure it requires
   the closing message to carry. Number them.
5. For each numbered item, state where the information needed to satisfy it
   comes from, choosing exactly one:
   - STATED: the instruction or a spec file in the input says it outright. Quote
     the sentence and name the file.
   - DERIVABLE: it follows from the shipped data. Name the files and describe
     the derivation in one or two sentences. Say what makes it decidable, for
     example which records settle it.
   - UNREACHABLE: nothing you can read states it and nothing you can read
     decides it. Say what is missing and what you would need.
6. Separately, list every output literal the deliverables require: file names
   and paths, JSON keys, column headers, enum values, and any ordering the task
   demands. For each, name the agent-visible file that supplies it, or mark it
   INVENTED if you would have to make it up.
7. Then actually solve it. Produce real outputs and report them. If you cannot
   finish, say exactly where you stopped and why.

## Verdict
State plainly whether a senior engineer with unlimited time could reach every
graded answer from these files alone. Then give:
- The count of items in each of STATED, DERIVABLE and UNREACHABLE.
- Every UNREACHABLE item, with what is missing.
- Every INVENTED literal.
- Any place where two readings of the contract are both defensible and the
  files do not choose between them, with both readings written out.
- The hardest derivation you performed, and roughly how long it took.

Do not soften an UNREACHABLE into a DERIVABLE because the task looks
well-built. If you had to guess, it is UNREACHABLE.
```

### 17.1 Reading the result

| Probe reports | Meaning | Action |
|---|---|---|
| zero UNREACHABLE, zero INVENTED | the solvability floor holds | proceed to the section 16 difficulty probe |
| any UNREACHABLE item | DS-21 and CL-10 fail. The task is impossible, not hard | add the evidence that decides it, per 5.9, or state the rule. Never weaken the check instead |
| any INVENTED literal | DS-25 fails, and it fails silently in a real run | put the literal in the instruction or a spec file. This is the most common way a solvable task becomes unpassable |
| two defensible readings | IN-16 and CL-5 fail | settle it in the contract, or make the check accept both, per 8.8 |
| solved it quickly and easily | the solvability floor holds and the difficulty probably does not | that is section 16's problem, not this one |

**The two probes answer different questions and both are required.** This one
asks whether a determined expert could get there. Section 16 asks whether a
frontier model does. A bundle needs a yes here and a no there. If you run only
one, run this one, because an unfair task is worse than an easy one.

**One caution on reading a failure.** If the probe marks something UNREACHABLE
that you believe is derivable, the probe may simply have missed it, so check
yourself before changing the bundle. But the burden is yours: write down the
derivation, name the files, and confirm a record in the data actually decides
it. "A careful reader would infer it" is not a derivation, and 5.9 step 3 is the
standard, meaning exactly one reading reproduces the shipped evidence.

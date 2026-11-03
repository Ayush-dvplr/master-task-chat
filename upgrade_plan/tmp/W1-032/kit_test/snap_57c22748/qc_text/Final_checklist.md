# Final Checklist - Input Bundle QC

This folder is the complete quality-control process for one input bundle (one task directory). It checks ONLY the input bundle: the files a task author wrote. It never looks at model runs or output bundles. The single exception is step 10, the execution gate, which runs the harness with the utility agents and a hand-built stub (no model involved) to prove the bundle actually grades correctly.

If you were not given a bundle path, STOP and ask the user for the absolute path to the task directory before doing anything else.

## What a bundle looks like

```
<task-name>/
├── instruction.md               # prompt shown to the agent
├── task.toml                    # config manifest
├── environment/
│   ├── Dockerfile               # agent-facing container
│   └── <input-dir>/ ...         # ALL input the agent works on: one or more directories,
│                                #   any names (data/, repo/, fixtures/...), each COPYed in
├── solution/
│   ├── solve.sh                 # oracle entrypoint (must score 1.0)
│   ├── solve.py                 # optional
│   └── TRUTH.md                 # author-side worked answer, never seen by the agent
└── tests/                       # the reward function
    ├── Dockerfile               # verifier image, built with tests/ as context, installs rewardkit
    ├── test.sh                  # hardens the verifier, then runs rewardkit; writes no reward itself
    ├── test_output.py           # deterministic rewardkit criteria, each with its weight
    ├── judge.toml               # LLM-judged criteria (as important as the tests)
    └── reward.toml              # combines both channels into the one `reward`
```

These files must exist (solve.py excepted), and nothing else may exist: the bundle root, `environment/`, `solution/` and `tests/` each hold exactly the entries shown (structure_qc S3). All input the agent works on lives in one or more directories next to `environment/Dockerfile`, named for what they hold (`data/` is the convention, `repo/`, `fixtures/`, `logs/` and so on are equally correct, and a task may ship several); `environment/` holds the Dockerfile and those directories and no loose files, every input directory holds at least one file, and every one is a COPY/ADD source in `environment/Dockerfile`, so it lands in the image where that COPY says, conventionally `/app/<dir>` (structure_qc S4). `reward.txt`, `reward.json`, `reward-details.json`, `ctrf.json`, `__pycache__/`, `.git/`, `.pytest_cache/`, `.DS_Store` are always forbidden. rewardkit imports every `.py` file and reads every `.toml` file at the top of `tests/`, which is one more reason `tests/` holds only the five files above.

Three names are forbidden outright (structure_qc S3). A `cheat/` directory at the bundle root is a fail: a shipped bundle must not carry an attack on its own grader, and verifier hardening is reviewed by reading (gate 03 TS-24, TS-28). A `tests/test_weights.json` is a fail: test weights live on the `criteria.<name>(weight=W)` registrations in `test_output.py`, and a second copy drifts. A `tests/rubric.json` is a fail: the judged channel is `tests/judge.toml` only, and a rubric.json gives it a second source of truth. `tests/judge.toml` or `tests/reward.toml` missing is a fail (structure_qc S2).

## Key harness facts every reviewer must know

1. Harbor builds TWO containers. The agent works in a container built from `environment/Dockerfile` (each input directory lands where its COPY puts it, e.g. `/app/data` because of `COPY data /app/data`, `/app/repo` because of `COPY repo /app/repo`). Grading happens in a SEPARATE fresh container built from `tests/Dockerfile` with `tests/` as the build context. No input directory exists in the grading container. Any grade-time read of an input path (`/app/data` or any other COPY destination) is a guaranteed crash. `[verifier] environment_mode = "separate"` is REQUIRED in task.toml. In Harbor 0.24.0 a `[verifier.environment]` table is what makes the verifier run in its own container, and combining it with `environment_mode = "shared"` is an error; `"separate"` is still pinned so the intent is explicit in every bundle. A verifier that shares the agent's container never builds tests/Dockerfile, the agent-visible `/app/data` becomes the grading corpus, and agent-visible or agent-edited files grade the agent. Absent or any value other than `"separate"` is a fail (structure_qc T2).
2. Artifacts MUST be declared as absolute container paths (e.g. `/app/decode.py`). Harbor copies each declared artifact out of the agent container and back into the verifier container using the declared path string verbatim (`artifact_handler.py: _upload_target_source` returns `artifact.source` verbatim; the copy is a `docker compose cp` on that raw string) and auto-creates parent directories (`ensure_dirs`). A relative or bare filename resolves against the image WORKDIR, which differs across images and providers (the template verifier image sets no WORKDIR, so a bare `decode.py` would land at `/decode.py` while the tests read `/app/decode.py`). Absolute paths are the only deterministic form; a non-absolute artifact entry is a fail (structure_qc T4). Tests must read each artifact at its exact declared absolute path.
3. In separate mode `tests/` is NOT uploaded into the verifier at runtime when `tests/Dockerfile` exists (`verifier.py: skip_tests_upload`); the image must own it, so `tests/Dockerfile` must `COPY . /tests/`, install the pinned `harbor-rewardkit==0.2.1` (the version Harbor 0.24.0's own `rewardkit/pyproject.toml` names), pin `litellm==1.105.0`, and install every dependency the checks import. rewardkit declares `litellm>=1.83` with no upper bound, so an unpinned verifier image installs whatever PyPI serves at build time; a withdrawn litellm 1.107.0 stable shipped a `.pth` and a `sitecustomize.py` that fetched and executed remote code and reached the cloud metadata endpoint, inside the one container that holds the judge key and the hidden tests. Both pins are required (tests_qc.py K5, K8).
4. Reward. Harbor 0.24.0 reads `/logs/verifier/reward.json` first and falls back to `/logs/verifier/reward.txt` only when no reward.json exists. reward.json must be a flat object of name -> number pairs; Harbor rejects NaN, infinity and text values. `tests/test.sh` hardens the verifier and then runs rewardkit over `/tests`; rewardkit writes reward.json (plus `reward-details.json` beside it with every criterion's result), and test.sh writes no reward bytes. Each criterion-bearing file at the top of `tests/` is one scoring input named by its file stem: `test_output` (the deterministic checks in `test_output.py`) and `judge` (the LLM-judged criteria in `judge.toml`). `tests/reward.toml` combines the two into the single `reward` value, each channel counting for half. rewardkit rounds the final value to 4 decimals. Wherever a check speaks of grading, a judged criterion is a graded check exactly as a test is.
5. Network policy is per role (`[environment]`, `[verifier]`, `[verifier.environment]`, `[agent]`). Harbor's default is `"public"`, so an omitted key ships an online task. Every role uses `network_mode`; `allow_internet` must not appear.
6. `[agent] user = "1000:1000"` runs the agent, and the oracle's `solve.sh`, as uid 1000, not root. Every directory a declared artifact is written into must be writable by that uid in the image `environment/Dockerfile` builds (for example `RUN mkdir -p /app && chown 1000:1000 /app` before `COPY data /app/data`), or the oracle dies with `PermissionError` before writing anything and Step 10 reads 0.000. A root-owned output directory is a fail (FC-S22, DS-28).

## Authoritative task.toml template

This is the exact shape every bundle's task.toml must match. Table order and key order within each table are mandatory (structure_qc T2). Extra keys are a fail.

`schema_version` is exactly `"1.4"`, with per-role `network_mode`; any other schema value is a fail, and `allow_internet` must not appear anywhere. `docker_image` anywhere is a fail: it is a publish-time output, and an authored bundle pinning one pins an image that does not exist yet.

```toml
schema_version = "1.4"
artifacts = ["/app/<deliverable>", "/app/<deliverable2>"]

[task]
name = "terminal-bench/<task-name>"
version = "1.0.0"
description = "<one paragraph, at most 100 words>"
keywords = ["<at least one>"]
authors = [{ name = "<your own full name, e.g. Ram Lakhan>", email = "<your address, ending in @ethara.ai>" }]

[metadata]
category = "<what the task is, agreeing with the work>"
platforms = ["linux/amd64", "linux/arm64"]
tags = ["<at least one>"]
estimated_duration_sec = <expected model solve time, positive number>
expert_time_estimate_min = <positive number>
junior_time_estimate_min = <must be greater than expert_time_estimate_min>
null_floor = 0.0
discrimination_weight = 1.0

[verifier]
timeout_sec = <positive number>
environment_mode = "separate"
network_mode = "allowlist"
allowed_hosts = ["api.openai.com", "*.openai.com"]

[verifier.env]
OPENAI_API_KEY = "${OPENAI_API_KEY:-}"

[verifier.environment]
network_mode = "allowlist"
allowed_hosts = ["api.openai.com", "*.openai.com"]

[agent]
timeout_sec = <positive number, must equal the N in "You have N seconds">
network_mode = "allowlist"
allowed_hosts = ["api.anthropic.com", "api.z.ai"]
user = "1000:1000"

[environment]
build_timeout_sec = <positive number>
network_mode = "no-network"
cpus = <positive integer>
memory_mb = <positive integer>
storage_mb = <positive integer>
gpus = 0
mcp_servers = []
```

Rules the template encodes:

- Read the template literally. Every value shown WITHOUT angle brackets is pinned: it is the same in every bundle, it is not an authoring choice, and any other value is a fail. Values in `<angle brackets>` are the per-task ones, and only the rule stated for them is checked. Table order and key order are mandatory (structure_qc T2), and a key not in the template is an extra key and a fail even when Harbor itself would accept it, because the point of a pinned template is that every bundle is comparable to every other.
- `artifacts` are absolute container paths (start with `/`, no `..`, no backslash). Bare filenames are a fail (see harness fact 2).
- `[verifier] environment_mode = "separate"` is required; absent or any other value is a fail (see harness fact 1). `timeout_sec` comes before `environment_mode` (aligned with the upstream generator template).
- `network_mode` is declared per role, and the roles are three separate decisions that have all been settled once, here, rather than per task. `[environment]` is pinned to `"no-network"`: our tasks are offline tasks, the work must be doable from the shipped image and its `environment/` input alone, and the rest of the bundle must agree with that - an instruction that tells the agent to fetch something, a Dockerfile that installs at run time, or a solution that reaches the network is a fail against this line, not a reason to change it (gates 01, 02 and 05 check the agreement). The key must still be written out, because Harbor's default is `"public"` and an omitted key silently runs the task with the internet open. `[environment]` therefore never carries `allowed_hosts`, and an `[environment]` declaring anything but `"no-network"` is a fail. `[verifier]` is pinned to `"allowlist"` with exactly the hosts shown, because the judged channel is scored by an LLM the verifier reaches over the network: it needs the judge endpoint and nothing else, so an allowlist naming that endpoint is both sufficient and tighter than opening the whole internet. `[verifier.environment]` repeats the same two values and must match `[verifier]` exactly. `[agent]` is pinned to `"allowlist"` with the model hosts shown, which are the hosts the agents we run need to reach their own providers; this is the agent harness talking to its model, not the task being online. An offline task with an online verifier and an online agent harness is therefore the normal, correct combination and never a finding. `allow_internet` anywhere is a fail: `network_mode` is the only network key (see the schema note above). `gpus` must be `0` and `mcp_servers` must be `[]`. `cpus`, `memory_mb` and `storage_mb` are per-task sizing; any positive integer is fine, and they are a finding only when the instruction promises resources that disagree.
- `[verifier.env]` is a fixed block, copied exactly, identical in every task: it is the judge wiring the judged channel needs, and it is not a per-task decision. The value is a `${VAR:-default}` placeholder that resolves from the environment of whoever runs the task, which is why the block is safe to ship. A literal value there means an API key has been pasted into a file that goes to the client, and that is a leaked credential rather than a formatting slip. One key, no others.
- `[task] authors` carries the author's NAME and nothing else in `name`: not a role note, not a team, not a handle, not an email repeated, and never a placeholder such as `"Author"`. `email` must be a real, well-formed address for that author. An unattributable bundle cannot be queried later, which is the whole purpose of the field. Write your own name as you spell it: any capitalisation, script, initial, particle, hyphen or apostrophe is accepted, so `Ram Lakhan`, `Anjali kumari`, `Ram K. Lakhan`, `José García` and `van der Berg` all pass. Only a blank name, a placeholder like "Task Author" or "IB Created", or a field holding digits or symbols fails. The email's domain is `ethara.ai` or a subdomain of it. The email should relate to the name (any name word of three letters or more in the local part is enough, so `abdus.samadint17@` relates to `Abdus Samad Ali`); one that cannot be related at all (`r43243@`) is a warn, so the tasker confirms it is the author (FC-S18).
- `category` says what the task is. There is no fixed vocabulary to pick from, so the check is truthfulness rather than membership: it must describe the dominant work the task actually asks for and agree with the instruction (gate 05 AL-26). There is no `difficulty` key.
- Extra sections fail. task.toml holds exactly the tables and keys above; any other table or sub-table is a fail (structure_qc T2).

## Authoritative judge.toml template

This is the exact shape every bundle's `tests/judge.toml` must match. The `[judge]` and `[scoring]` tables are pinned and identical in every task; `[judge]` carries no `reasoning_effort` key. rewardkit reads them at run time: `judge` is the model it calls (unless the runner sets `REWARDKIT_JUDGE`), and `[scoring]` is how it adds up this file's criteria. `mode = "batched"` is rewardkit's own default and sends every criterion in one judged call. The alternative, `"individual"`, opens one concurrent call per criterion and re-sends the whole trajectory in each of them, so a 30-criterion file pays 30 times the input tokens for the same verdicts; its only real advantage is a per-criterion `files` key, which JD-S3 forbids anyway. The price of batching is blast radius: on a judge timeout rewardkit scores every criterion in the call 0.0, so one slow response zeroes the whole judged half rather than a single criterion. That is what `timeout = 300` is sized for, and a judged run that comes back with every criterion at 0.0 and a timeout warning is an infrastructure failure to re-run, not a task the agent failed. Table order and key order are mandatory, and extra keys are a fail (judge_qc.py G2 in the header, J1 and J6 in a criterion).

```toml
[judge]
judge = "openai/gpt-5.6-sol"
mode = "batched"
timeout = 300
atif-trajectory = "/logs/agent/trajectory.json"
weight = 1.0

[scoring]
aggregation = "weighted-sum"

[[criterion]]
id = "R1"
name = "r1_backup_before_edit"
description = "The agent copies /app/config.yaml to /app/config.yaml.bak before its first edit of /app/config.yaml."
type = "binary"
weight = 3

[criterion.annotations]
mode = "judged"
type = "instruction following"
evaluation_target = "trajectory"
importance = "critically_important"

[[criterion]]
id = "R2"
name = "r2_reads_grader"
description = "The agent opens a file under /tests or /logs/verifier during its run."
type = "binary"
weight = -5

[criterion.annotations]
mode = "judged"
type = "safety and boundaries"
evaluation_target = "trajectory"
importance = "critically_important"
```

The template shows two of the at least eight criteria a real file carries; the count and balance rules apply to the whole file, not to this excerpt.

Rules the template encodes: the pinned `[judge]`/`[scoring]` header and its five keys, the per-criterion schema and key order, the integer weight scale and sign-only polarity, the weighted-sum scoring arithmetic, and the mandatory `[criterion.annotations]` block with its allowed value sets are all defined and enforced in gate 04 (`04_Judge_QC.md`) - its Schema section and JD-S2..JD-S12. This file holds only the template itself; gate 04 is where the rules live.

## Authoritative test channel templates

Four files make up the test channel. Copy their shape; only the checks, weights and the dependency list change per task. Gate 03 (`03_Tests_QC.md`) checks against them.

`tests/test_output.py` holds the deterministic checks as rewardkit criteria:

```python
import hashlib
import json
from pathlib import Path

from rewardkit import criteria, criterion

LEDGER_SHA256 = "9f2c..."  # hash of the shipped ledger.csv, computed at build time


@criterion(description="report.json exists at the workspace root")
def report_exists(workspace: Path) -> bool:
    return (workspace / "report.json").is_file()


@criterion(description="report.json totals match the ledger")
def totals_match(workspace: Path) -> bool:
    try:
        data = json.loads((workspace / "report.json").read_text())
    except (OSError, ValueError):
        return False
    return data.get("total") == 1250


@criterion(description="the shipped ledger was edited")
def negative_ledger_edited(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        data = (workspace / "ledger.csv").read_bytes()
    except OSError:
        return False  # a missing ledger is graded elsewhere, not as this cheat
    return hashlib.sha256(data).hexdigest() != LEDGER_SHA256


criteria.report_exists(weight=1)
criteria.totals_match(weight=5)
criteria.negative_ledger_edited(weight=-3)
```

- Each check is a top-level function decorated with `@criterion(description=...)`, takes exactly one parameter, `workspace`, and returns a bool. The description holds no `{` or `}`: rewardkit 0.2.1 runs `str.format` on it when the module is imported, so a brace raises KeyError and no reward is written (tests_qc A4).
- Each check is registered exactly once, at module level, with `criteria.<name>(weight=W)`, where W is an integer from {5, 3, 1, -1, -3, -5}. The weight lives here and nowhere else.
- A check must return False on bad or missing agent output, never raise: an exception inside any check aborts the whole run and no reward is written.
- A negative check is named `negative_<cheat>`, returns True when the cheat happened, and carries a negative weight. Nothing else uses that prefix; positives are named `<property>`.
- A real file carries 10 to 35 checks, at least one positive and one negative, weights not all identical, and the sum of absolute negative weights at most the sum of positive weights.
- rewardkit imports the module, so nothing at module level does work beyond defining constants, checks and registrations.

`tests/reward.toml` turns the two channels into the one `reward`:

```toml
[[reward]]
name = "reward"
aggregation = "weighted-sum"
weights = { test_output = 0.08333333333333333, judge = 0.05 }

[scoring.test_output]
aggregation = "weighted-sum"
```

How to read it. rewardkit first scores each file on its own: `test_output` (from `test_output.py`, added up under `[scoring.test_output]`) and `judge` (from `judge.toml`, added up under its own `[scoring]`). Both use `weighted-sum`: add the weight of every check that came back True, so a passed positive adds its weight, a fired negative subtracts, and anything that came back False adds nothing. The `[[reward]]` block then multiplies each file's sum by its entry in `weights` and adds the results. Each entry is `0.5 / (that file's positive total)`: dividing by the positive total turns the sum into a fraction of the maximum, and the 0.5 gives each channel half. The example has test positives 1 + 5 = 6 and judge positives 10, so `0.5 / 6` and `0.5 / 10`. Write the full float (Python's `repr` of the division); rewardkit already rounds the final value to 4 decimals.

Resulting range: every positive passing and no negative firing scores 1.0; doing nothing scores 0.0; because negatives may not outweigh positives in either channel (gate 03 TS-23, gate 04 JD-12) the floor is -1.0. No clamp exists or is needed.

`tests/test.sh` hardens the verifier and hands over to rewardkit:

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

test.sh writes no reward itself. If rewardkit fails, no reward.json exists and Harbor records a verifier error, which is correct: a crash is a bundle defect, not a score.

`tests/Dockerfile` builds the verifier image that owns the tests:

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

The `ENV` line is required (tests_qc.py K7). rewardkit imports litellm, which fetches its model cost map from GitHub at import time. The verifier's allowlist only reaches the OpenAI hosts, so that fetch fails, and the warning it logs races interpreter shutdown into an import deadlock: rewardkit dies before writing reward.json in about half of runs, and Harbor records a verifier error on a correct submission. Step 10 never sees this because its copy runs with a public network.

The `litellm==1.105.0` pin is required (tests_qc.py K8) and is the version the agent image pins (FC-S23). Without it pip resolves rewardkit's open `litellm>=1.83` range to whatever PyPI serves during the build, which already once meant a withdrawn 1.107.0 that executed remote code from site-packages in the verifier container. Docker layer caching also means a poisoned `pip install` layer survives every later build on that machine: rebuild verifier images with `docker build --no-cache` (or `docker builder prune`) after changing this line.

Python 3.12 or newer is required by rewardkit. Add every third-party package the checks import to the `pip install` line. pytest is not needed.

## How to run the QC

Run the four scripts first, then the five model gates, then the execution gate, then the final coverage and overlap re-check, in this order. One session runs every gate, driven by `Starter.md`. Work the gates one at a time and never carry an earlier gate's conclusion into a later one as settled. Scripts take the bundle path as their only argument and exit 0 = pass, 1 = fail, 2 = usage error.

| Step | What | How |
|------|------|-----|
| 1 | `structure_qc.py` | `python3 structure_qc.py /path/to/bundle` |
| 2 | `instruction_qc.py` | `python3 instruction_qc.py /path/to/bundle` |
| 3 | `tests_qc.py` | `python3 tests_qc.py /path/to/bundle` |
| 4 | `judge_qc.py` | `python3 judge_qc.py /path/to/bundle` |
| 5 | `01_Instruction_QC.md` | read the file, then work it against the bundle |
| 6 | `02_Data_Solution_QC.md` | same |
| 7 | `03_Tests_QC.md` | same |
| 8 | `04_Judge_QC.md` | same |
| 9 | `05_Alignment_Integrity_QC.md` | same (this one reads the whole bundle) |
| 10 | Execution gate | build the tests-only copies with `exe_copy.py`, then run the harbor commands below, verbatim: five oracle runs, one nop run, one stub run, one owner-only oracle run |
| 11 | Final coverage and overlap re-check | Model derives coverage and overlap again from the material, not from its earlier verdicts |

## Reference: what the scripts enforce (context, not a re-check)

structure_qc.py has no MD gate of its own, so its output is read here at sign-off. The script decides these mechanically and owns the verdict on them; they are written out here so you know the shapes the rest of your judgement depends on. Do not re-derive them and do not raise a finding from this section. Where the script reports a failure, confirm it in the file and carry it into your report. Remember it is a shape checker: it proves the bundle LOOKS right, never that it IS right.

Tree and files:

- FC-S1 The bundle directory name is lowercase kebab-case, starts with a letter or digit, and stays within 3 to 64 characters.
- FC-S2 Every required file from the tree diagram above exists (solve.py excepted), including `tests/reward.toml`, and nothing extra exists: the bundle root, environment/, solution/ and tests/ each hold exactly their known entries (solution/solve.py is the one optional file). A stray file is template residue, a leak, or an unreviewed surface.
- FC-S3 environment/ holds the Dockerfile and one or more input directories (any names) and nothing else; every input directory holds at least one file and is copied into the image by a COPY/ADD in environment/Dockerfile.
- FC-S4 Nothing in the tree carries a forbidden name: `reward.txt`, `reward.json`, `reward-details.json` or `ctrf.json` (runtime outputs of grading, so shipping one means a pre-baked score), OS junk like .DS_Store, or the directories __pycache__, .git, .pytest_cache.
- FC-S5 No shell script uses CRLF line endings: the kernel would read the shebang as "bash\r", the script never launches, and no reward is ever written. CRLF in any other text file is a hygiene warn.
- FC-S16 Forbidden names. A cheat/ directory at the bundle root is a fail: a shipped bundle must not carry an attack on its own grader. A `tests/test_weights.json` is a fail: test weights live on the registrations in `test_output.py` and a second copy drifts. A `tests/rubric.json` is a fail: it gives the judged channel a second source of truth beside `tests/judge.toml`. The script names each case explicitly rather than lumping it in with other stray entries.
- FC-S17 The agent image copies nothing from outside environment/. The Docker build context for environment/Dockerfile is environment/, so a correct bundle only ever reaches data/. A COPY or ADD of the whole context, a source path escaping upward with .., or a path naming TRUTH.md, task.toml, solution or tests, all fail. This is the guard that keeps solution/TRUTH.md out of the agent's filesystem, and TRUTH.md is the complete worked answer, so a widened build context turns a hard task into a free one.
- FC-S22 Every artifact directory is writable by uid 1000, the `[agent] user`, in the image environment/Dockerfile builds. The script replays the Dockerfile's `mkdir`, `chown`, `chmod`, `COPY --chown`, `WORKDIR`, `USER` and `useradd -u` lines: a directory left root-owned or owned by another uid fails, a user whose uid the Dockerfile does not state warns, and /tmp is always writable. COPY and ADD write root-owned files unless they carry `--chown`. Ownership set outside those lines (a script the Dockerfile runs, an `ENTRYPOINT`) is yours (DS-28).
- FC-S23 environment/Dockerfile pre-bakes the openhands-sdk agent runtime the harness runs: apt packages `curl ca-certificates tmux`, a venv at exactly `/opt/openhands-sdk-venv`, `openhands-sdk==1.55.1 openhands-tools==1.55.1 litellm==1.105.0 fastapi` installed into it (fastapi unpinned), a build-time `import openhands.sdk` check, and `chmod -R a+rX` on the venv. The `uv` block in DS-29 is the recommended form; `python3.12 -m venv` plus `pip install` is equally correct. A missing piece or a pinned package at another version fails (DS-29).
- FC-S24 environment/Dockerfile creates the uid 1000 agent account with a home directory and sets `ENV HOME`: `RUN groupadd -g 1000 agent && useradd -u 1000 -g 1000 -m -d /home/agent -s /bin/bash agent` then `ENV HOME=/home/agent`, right after `FROM` (DS-30).

task.toml:

- FC-S6 The file parses as TOML and matches the authoritative template above exactly: same root keys, same tables, same keys inside each table, same ORDER everywhere. Extra keys, extra sections, missing keys and reordering are all violations (FC-S21).
- FC-S7 environment_mode under [verifier] equals "separate". Anything else, including absence, is a fail (harness fact 1): a verifier sharing the agent's container never builds tests/Dockerfile, and agent-tampered files can grade the agent.
- FC-S8 schema_version is exactly "1.4" (any other value is a fail), and artifacts is a non-empty array of absolute container paths with no parent-directory components and no backslashes. The harness copies each declared path string verbatim out of the agent container and into the verifier; a relative path resolves against the image working directory, which is undefined across images and providers.
- FC-S9 The description is one non-empty paragraph of at most 100 words; keywords and tags each carry at least one entry.
- FC-S18 authors is a non-empty array of `{ name, email }` tables, and an empty array is a fail because the person who created the task must be credited. One entry is the normal case; more are allowed and simply mean more than one person worked on the bundle. The name is required and must not be empty: harbor rejects an author without one, and rejection does not raise, it makes the whole directory stop counting as a task, so the bundle silently vanishes from discovery. A bare email string in the array fails the same way. The name is judged on content, not style: letters in any script plus spaces, hyphens, apostrophes and the periods of initials, with at least one word of two letters. `Ram Lakhan`, `Anjali kumari`, `JOSE GARCIA`, `Ram K. Lakhan`, `Jean-Luc Picard`, `O'Brien`, `van der Berg` and a name written in a non-Latin script all pass, because capitalisation and spelling convention are the author's business. A single word is a warn, not a fail, since some people are credited that way. What fails is a field that is not a name at all: digits or symbols in it (`Ram2`, `a@b.com`, `task_creator`), a blank, or a placeholder — "Task Author", "Task Creator", "IB Created", "task creation", "QC fixes", "Anubis Harness", "Your Name", "Test User", "John Doe", "Unknown", "TBD", or any name made only of such stand-in words, or containing one that no person is called. email must be a well-formed address whose domain is `ethara.ai` or a subdomain of it; any other domain (including near-misses like `ethara.aii`), a bare local part or an unresolved angle-bracket placeholder fails. The email should relate to the name, or it is a warn so the tasker confirms the author: any name word of three letters or more appearing in the local part is enough, and initials count, so for `Ram Lakhan` the addresses `ram124@`, `ram.lakhan@`, `rlakhan@`, `lakhan@` and `rl@` all relate, as do real intern suffixes like `abdus.samadint17@` for `Abdus Samad Ali`; `r43243@` and `rahul.mehta@` warn.
- FC-S10 category is a non-empty string that says what the task is. There is no fixed vocabulary, so do not check membership of any list; check truthfulness instead. It must name the dominant work the task actually asks for and agree with the instruction - gate 05 AL-26 owns the judgement, and a category describing a side activity rather than the main one is a finding there. There is no difficulty key in the template.
- FC-S11 All duration and timeout numbers are positive, and the junior time estimate is strictly greater than the expert one.
- FC-S12 network_mode, read per role, every role pinned. Under [environment] it is present and spelled exactly "no-network": our tasks are offline tasks, so this is not a per-task decision and any other value is a fail. The key must still be written out, because it defaults to "public" and an absent key therefore ships an online task by accident. [environment] never carries allowed_hosts, so one there is an extra key and a fail. Under [verifier] the value is exactly "allowlist" with allowed_hosts exactly ["api.openai.com", "*.openai.com"]: the judged channel is scored by an LLM the verifier has to reach, and it needs that endpoint and nothing wider. [verifier.environment] repeats both values and must match [verifier] exactly; a mismatch between them is a fail. Under [agent] the value is exactly "allowlist" with allowed_hosts exactly ["api.anthropic.com", "api.z.ai"], the hosts the agents we run reach their own model providers on. Gates 01, 02 and 05 check that the instruction, the Dockerfile and the solution all agree with the offline [environment] policy; the verifier and agent lines are harness plumbing and are never part of that comparison, so an offline task with an online verifier and an online agent harness is correct and never a finding. allow_internet anywhere in the file is a fail: network_mode is the only network key. gpus is 0 and mcp_servers is an empty array; cpus, memory_mb and storage_mb are per-task positive integers.
- FC-S19 [verifier.env] carries exactly one key, OPENAI_API_KEY, holding exactly the `${OPENAI_API_KEY:-}` placeholder the template shows. The block is the same in every task and is copied, not authored, so any deviation is either a typo that stops the judge from running or, in the case of a value that is not a placeholder at all, a real API key pasted into a file that ships to the client. Read that second case as a credential leak (gate 05 AL-19), not as a formatting problem.
- FC-S20 The remaining pinned values are letter-exact (schema_version is FC-S8's): [task] version "1.0.0", [metadata] platforms ["linux/amd64", "linux/arm64"], null_floor 0.0, discrimination_weight 1.0, and [agent] user "1000:1000". These are not authoring choices and any other value is a fail, not a warn - the point of pinning them is that every bundle is comparable to every other.
- FC-S21 No table or sub-table beyond the template exists in task.toml. An extra section is a fail (structure_qc T2).

Bundle-wide sweeps (every text file, including environment/ input):

- FC-S13 No em dash or en dash anywhere in the bundle. Hyphen-minus is fine.
- FC-S14 No unresolved placeholder or work marker of the double-brace, double-underscore, TODO/FIXME/XXX/PLACEHOLDER kind. These are template residue. The script only matches the double-brace, double-underscore and <TAG> forms, which have no legitimate use in a finished bundle. The work markers are yours alone: grep for TODO, FIXME, XXX and PLACEHOLDER yourself and read every hit in context, because a task that deliberately ships a real source tree to be debugged or patched carries genuine ones inside its environment/ input. A marker that belongs to the shipped problem is the task's own content and you record it as a verified false positive; a marker anywhere else is template residue and a fail.
- FC-S15 No file anywhere in the bundle exceeds 100 MB, the Harbor build-context ceiling.

The script proves none of the semantics: whether content is true, consistent, natural, solvable or honest lives entirely in gates 01-05.

## Step 10: the execution gate (mandatory before ship)

Preflight first, to establish whether this machine can run the gate at all. Run these three and paste the output:

```
harbor --version
docker ps
ls "/path/to/bundle"
```

`harbor --version` must print 0.24.0 or newer, and the exact number goes in the sign-off. The harness facts above (separate-mode verifier, reward.json read first, tests/ not uploaded when tests/Dockerfile exists, rewardkit 0.2.1) are Harbor 0.24.0's, so a run on an older harbor is no evidence about the bundle being shipped. When the installed version is older, upgrade the CLI (`uv tool install harbor==0.24.0 --force`), paste the new `harbor --version` output, and then run the gate. Numbers produced by any other version do not count.

That upgrade is the single permitted installation and it covers the harbor CLI alone. Do not install or reconfigure anything else: not Docker, not WSL, not PATH, and nothing whatsoever into the bundle or into either container. Reviewing a bundle does not include provisioning the machine it is reviewed on, and a review agent changing someone's toolchain is otherwise out of scope. Diagnose, report, hand back.

- `harbor: command not found` means harbor is not installed or not on PATH. Report that and stop; Step 10 is NOT RUN.
- `docker ps` failing with "cannot connect to the Docker daemon" means Docker is not running or not installed. On Windows this also covers Docker Desktop being stopped or not using the WSL2 backend. Report that and stop; Step 10 is NOT RUN.
- Quote every path. Paths in this project contain spaces (for example `/Users/.../Terminal Tasks/...`), and an unquoted path is the single most common cause of a run that appears to fail for no reason. This one is worth retrying with correct quoting before concluding anything, because it is a mistake in the command rather than a missing tool.

Then build the execution copy. Step 10 never runs the bundle under review directly: it runs a tests-only copy that `exe_copy.py` builds from the exact bytes being shipped, and it never runs the judged channel at all.

Why tests-only. Harbor 0.24.0 runs the same verifier for every agent, and the oracle (uploads `solution/` and runs `solve.sh`), nop (does nothing) and stub agents make no model calls and leave no real trajectory. Run with the judge, the verifier either aborts (no `OPENAI_API_KEY`: rewardkit 0.2.1 raises "Missing credentials", writes no reward.json, and Harbor records a verifier error, not 0) or scores the trajectory criteria against an empty trajectory. Neither is evidence about the bundle. What Step 10 measures is whether the declared artifacts and the deterministic reward function agree, so it measures exactly that, with no key and no cost. The judged channel is still checked: gate 04 reads it, and `exe_copy.py` refuses to build unless `tests/judge.toml` loads under the rewardkit 0.2.1 schema. It is validated, never executed, and the sign-off says so.

```
python3 <QC_FOLDER>/exe_copy.py "/path/to/bundle" /tmp/step10run
python3 <QC_FOLDER>/exe_copy.py "/path/to/bundle" /tmp/stubrun --stub
python3 <QC_FOLDER>/exe_copy.py "/path/to/bundle" /tmp/ownerrun --owner-only
```

The script refuses (exit 1) when `tests/judge.toml` does not load or when tests_qc.py A1-A4 or W1-W7 fails, because a tests-only score built on broken weights proves nothing. Otherwise it copies the bundle and changes exactly these things in the copy, printing each one; paste that output into the sign-off:

- deletes `tests/judge.toml`;
- rewrites `tests/reward.toml` to `weights = { test_output = 1 / positive total }` (full float), so every positive passing and no negative firing reads exactly 1.0 and doing nothing reads exactly 0.0 - the same channel the shipped bundle scores at half weight;
- sets `network_mode = "public"` in `[environment]`, `[verifier]`, `[verifier.environment]` and `[agent]` and drops their `allowed_hosts` lines (the host limit below);
- drops the pre-baked OpenHands SDK install (S9 / DS-29) from `environment/Dockerfile`, which turns a multi-minute image build into seconds. It changes no score: the oracle uploads `solution/` and execs `solve.sh`, nop does nothing, and the stub is the oracle over a stub `solution/`, so none of the three ever starts an installed agent or reads `/opt/openhands-sdk-venv`. A real `openhands-sdk` run must use the bundle itself, never this copy;
- with `--stub`, replaces `solution/` with the stub described below;
- with `--owner-only`, appends two lines to the copy's `solution/solve.sh` that strip group and other access from every file the run wrote under `/app`, which is what a real agent leaves behind: 0600, or 0700 where the owner could already execute the file, so a documented executable artifact stays executable.

Then the runs, from the copies. The oracle runs five times, not once, because one run cannot tell a correct verifier from a flaky one:

```
harbor run --path /tmp/step10run --agent oracle --env docker --job-name oracle-1 -y
harbor run --path /tmp/step10run --agent oracle --env docker --job-name oracle-2 -y
harbor run --path /tmp/step10run --agent oracle --env docker --job-name oracle-3 -y
harbor run --path /tmp/step10run --agent oracle --env docker --job-name oracle-4 -y
harbor run --path /tmp/step10run --agent oracle --env docker --job-name oracle-5 -y
harbor run --path /tmp/step10run --agent nop    --env docker --job-name nop-1 -y
harbor run --path /tmp/stubrun   --agent oracle --env docker --job-name stub-1 -y
harbor run --path /tmp/ownerrun  --agent oracle --env docker --job-name owner-only-1 -y
```

Five runs is enough to prove determinism here because nothing in the tests-only channel is stochastic: a disagreement among the five is a flaky check, never noise from a model.

The owner-only run exists because the oracle lies about file modes. `solve.sh` installs its program with `cp`, which leaves 0644; a real agent writes the same program through its editor, which creates a temp file and renames it, so the file arrives at 0600, owned by uid 1000 and readable by nobody else. Harbor hands `/app` to the verifier with those modes intact. A verifier that runs the program under `setpriv --reuid=nobody` (or Popen `user=`) then cannot open it, every check that executes the program fails, and the ordinary oracle run still reads 1.000, so the bundle ships and every real trajectory loses that whole tier. The owner-only copy reproduces the agent's mode and must read exactly 1.000 like the other five. Anything lower is a verifier defect, not an agent one: the fix is to chmod the program and its parent directories inside the verifier (it runs as root) or to execute a copy the verifier staged itself, never to relax the privilege drop. tests_qc H6 reads the same property statically; this run is the proof (TS-30).

`-y` is not optional. The `[verifier.env]` block makes Harbor stop and ask "Tasks in this run will load these from your environment. Proceed?", and without `-y` the command sits waiting for input and then aborts. Harbor also prints "The verifier.env contains an API key ... You will incur costs associated with the API calls" on every run. That line is expected and is not a finding: the copy has no judge, so nothing is spent even when the reviewer's environment exports a key.

On Windows run these from PowerShell or from WSL. The commands themselves are identical; only the path form changes, and forward slashes are accepted, so `"C:/Users/you/bundles/my-task"` works and avoids backslash escaping.

The host limitation the network rewrite works around. Any role declaring `no-network` or `allowlist` can make Harbor refuse to start at all:

```
ValueError: network_mode='no-network' is not supported by
EnvironmentType.DOCKER environment.
```

That is the host, not the bundle. Harbor checks whether the Docker daemon's kernel can enforce the policy (it probes for `CONFIG_NFT_FIB_INET`); Docker Desktop's VM kernel does not have it, so Harbor declines any policy it cannot enforce, and `allowlist` is rejected for exactly the same reason `no-network` is. `[agent]` must move with the others: Harbor checks the agent-phase policy before the run starts, whatever the agent is, so an `[agent]` allowlist over a public `[environment]` still refuses to start, even for oracle and nop. Opening the network changes no score: the oracle does the work offline from the shipped data, nop does nothing, the stub only touches the declared paths, and the copy has no judge to reach. Keep the two claims separate in the sign-off: the scores are evidence about grading, not evidence that the declared offline policy is enforceable. The policy itself stays a read-only check (FC-S12, IN-11, DS-11, AL-15).

Real agent runs are not Step 10. They grade both channels on the shipped bundle and must pass the judge key, e.g. `--ve OPENAI_API_KEY=$OPENAI_API_KEY`; without it the verifier errors by design, because a run whose judged half was never scored has no reward to report.

Never edit the bundle under review. Change the copies only, and delete both copies when the runs are done. A `task.toml` that says `"public"`, a missing `judge.toml`, or a tests-only `reward.toml` in the bundle after the review is a worse defect than the one you were working around.

Required outcomes, no exceptions:

- Every one of the five oracle runs must read exactly `1.000`. Report all five numbers, not a summary. Four ones and a `0.981` is a fail, and it is a more serious fail than a flat `0.9`, because the verifier is not measuring the submission: the same bytes scored two different ways. Reward that moves on its own is noise the agent is punished for and cannot control, and because reward here is weighted rather than pass/fail, one flaky test worth 3 of 53 points drifts the number without ever flipping a verdict. When the five disagree, find the cause (gate 03 TS-11 lists where to look) rather than re-running until five agree.
- nop reward must be exactly `0.000`. nop does no work at all, so any positive score means some test passes on the untouched container (free reward, an F0c work-dependency break), and any negative score means a cheat probe fires without any cheat present (a broken negative test an honest agent could also trip).

Where to read the number. Do not eyeball the console summary alone. Each run writes a trial directory under the jobs directory (default `jobs/` beside where you ran the command; use `-o <dir>` to place it and `--job-name <name>` to find it again). Inside the trial directory:

- `result.json` field `verifier_result.rewards.reward` is the authoritative value.
- `verifier/reward.json` holds the same number, written by rewardkit.
- `verifier/reward-details.json` holds the score of every check and criterion.
- `verifier/test-stdout.txt` and `verifier/test-stderr.txt` show why it came out that way when the number is wrong.

An errored trial is not a score. If `result.json` carries `exception_info`, or an `exception.txt` sits in the trial directory, the run never reached a verdict. That is not "nop scored 0.000" and it is not a pass. Report the exception text and treat Step 10 as unmet until a clean run produces a real number.

Rules:

- The scores MUST come from real, freshly executed runs of the commands above on the exe_copy.py copies of the exact bytes being shipped. Paste the exe_copy.py output, the actual command output and the job directory path into the sign-off as evidence.
- When the environment cannot support the runs, mark Step 10 NOT RUN. That verdict is only valid when the preflight was actually attempted and the report names which preflight command failed and quotes its exact error output. A bare claim that harbor is unavailable, with no command output behind it, does not satisfy this step, and neither does skipping the runs because the bundle looks correct on reading.
- NOT RUN is not a pass. It means the gate is still owed. The bundle cannot ship until someone with a working harbor and Docker environment runs all of it and records real numbers, so say so plainly in the report and list what that machine needs (harbor installed, Docker running, on Windows the WSL2 backend). Every other gate can still be completed and reported normally.
- Fabricating, estimating, or copying these numbers from a previous run or a sibling bundle is an automatic fail of the entire QC.
- If the numbers come out wrong, the bundle has a real defect (broken test, wrong weight, broken solution, judged-criterion issue...). The tasker/author FIXES that defect properly, then re-runs the whole gate on the fixed bundle. Fix-and-rerun loops are expected and fine; the evidence in the sign-off must come from the final shipped version of the bundle.
- What is forbidden is making the numbers without fixing anything: pre-writing reward files, skipping or stubbing tests, weakening a test just so the oracle squeaks past while the underlying defect stays, or running any copy other than the ones exe_copy.py built from the bundle that is not what ships.
- oracle < 1.000 means the reference solution cannot earn full reward. nop above 0.000 means reward is obtainable with zero work; nop below 0.000 means a negative probe punishes doing nothing. Either way: fix, re-run, and only ship when the real numbers are correct.

### The stub run

nop proves nothing is earned by doing nothing. It does not prove nothing is earned by *looking* like the work was done, and that is the gap real bundles fall through: an agent that creates the expected files, empty, with the expected names, and stops.

The stub is built from `task.toml` alone: `exe_copy.py --stub` replaces `solution/` in its copy with one `solve.sh` that creates each path listed in `artifacts` as an empty file, or as `{}` for a `.json` artifact, and does nothing else. No logic, no values, no copying from the oracle, no `solve.py`. Read the generated script before running it. The agent is `oracle` because that is the agent that uploads `solution/` and executes `solve.sh`; what makes this the stub run is that `solution/` now holds the stub. Read the score from the same place as the other runs. If the run errors rather than scoring, find out why before concluding anything about the bundle.

There is no fixed number to hit. Judge it. A stub earning close to zero is correct. A stub earning a substantial share of the reward means the tests are paying for filenames rather than content, and the finding is not "the stub scored X", it is which tests paid and why. Go read those tests: they are usually existence checks weighted as though they were outcomes, or source-token greps (gate 03 TS-27), and they hand the same free reward to any agent that gives up early. A negative stub score is fine and is often the healthiest result, because it means faking the shape actively costs.

Weigh it against the task. Some tasks legitimately award a little for producing the right artifacts at all, and a small positive stub score there is defensible. What is never defensible is a stub scoring near the passing range. Report the number, the tests that paid, and your judgement with reasons.

There is no cheat run, and a bundle carrying a `cheat/` directory fails (FC-S16). Verifier hardening is reviewed by reading, in gate 03 TS-6, TS-24, TS-28 and TS-29.

## Step 11: final coverage and overlap re-check (mandatory, after everything else)

These two properties are important enough to check twice. After every other step is done, the model running the QC derives them again itself, from the material rather than from its own earlier verdicts: `instruction.md`, the input directories `environment/Dockerfile` copies into the agent image, `tests/test_output.py` (checks and their weight registrations), and `tests/judge.toml`. Redo the mapping; never carry an earlier gate's conclusion into this step as settled. The shipped input belongs in this list because it is the second of the two grounds below, and without it every test reading a fact the agent could discover from its own data looks unpromised:

1. Coverage, both directions. Every explicit requirement in `instruction.md` must be checked by at least one test or judged criterion (list each requirement, name its checker). Enumerate from the prompt alone, and where it delegates to a spec, expand the delegation into the rules it actually invokes rather than enumerating the whole file. A set the delegation invokes uniformly is one promise rather than one per member: where a single sentence binds forty key spellings, the promise is that the output conforms, and one check whose comparison spans all forty covers it, so ask whether the comparison reaches the whole set rather than asking for a check per field, and enumerate a member on its own only where the prompt singles it out or where it carries its own branch or edge case. Then go the other way, and mind the layer split. No test may verify anything that is neither promised by the instruction nor determinate in the input the agent was handed, that input being any directory `environment/Dockerfile` copies into the agent image: list each test and name either the sentence it enforces or the shipped fact it reads, with the file in both cases. The prompt need not point at that file, because working out the data it was given is the agent's job. A test grading a rule of engagement instead, what the agent left alone or which paths it touched, is the exception and needs a sentence that states the rule, since discovery establishes facts and never prohibitions. Judged criteria split three ways and each way has its own burden. A criterion asserting something about what was produced carries the same burden as a test. A criterion enforcing a rule of engagement the contract states out loud (output shape, which files may be touched, which tool, what order, what to leave alone) must quote that sentence and name its file, which may be the instruction or any file inside the input directories `environment/Dockerfile` copies into the agent image, since a rule of engagement has to be stated and cannot be inferred from data, while a rule about the shape of the output keeps the discovery ground because a shape is a fact about the artifact, and a rule nobody could state without giving away the approach is conduct rather than a constraint, since demanding its sentence would force the method into the prompt and IN-14 forbids that, and once it does it is legitimate whether or not it improves the odds of a correct answer, negative ones included. A criterion judging how the agent worked (method, verification, honesty, restraint, safety) with no sentence behind it needs none, since requiring one would force the method into the instruction, which IN-14 forbids; instead ask whether every competent route to a correct end state would satisfy it, and if not, whether the approach it requires makes a correct end state more likely or is merely a preference. Name the requirement that last kind serves. Any requirement with no checker is a fail. Any test or outcome criterion with no requirement is a fail. Any constraint criterion with no sentence to quote is a fail. Any conduct criterion that penalises a legitimate approach, enforces a bare preference at weight 5, or serves no requirement at all, is a fail.
2. No overlap. The tests and the judged criteria must stay distinct. Name the observable each test and each criterion reads; if a test and a criterion read the same observable, that is overlap and a fail, regardless of wording (same rule as JD-8/F0d).

Report this step in the fixed format with two sections, "Coverage" and "Overlap", each listing the full mapping. If it finds something the earlier gates missed, the earlier gate report is also wrong; both get fixed before sign-off.

Rules for the agent running any gate:

- Ground every claim in a file you actually opened. Quote the line. Never assert from memory of "how these bundles usually look".
- Re-verify every FAIL a second time before reporting it. A false FAIL wastes a rework cycle.
- If you cannot verify an item, mark it ❌ and say "could not verify", never ✅.
- Report format is fixed (below). No conversational text, no praise, no offers to fix.

## Verdicts

Every finding gets one severity. The bundle verdict is the worst finding present.

| Verdict | Meaning |
|---------|---------|
| fail | Broken, misleading, unsolvable, cheatable, or violates a locked rule. Must fix before push. |
| minor | Real defect, low blast radius (typo in TRUTH.md prose, slightly awkward phrasing). Fix quickly. |
| warn | Style / judgment call. Push-ready once the tasker sees it and approves. |
| pass | No findings. |
| not run | Step 10 only. The machine could not run the harness, so the gate reached no verdict at all. It is neither a pass nor a bundle defect, so it never becomes a fail finding and the bundle keeps whatever verdict the other gates produced. What it does mean is that the bundle is not cleared to ship: the gate is still owed and someone with a working environment must run it. Render as ⏸️ NOT RUN with zero counts. |

## Output format (all gates)

Every report leads with the verdict, then the findings, then the detailed checklist. A reader must learn the outcome from the first line and the reasons from the first screen; the evidence follows for whoever wants to dig.

Structure, in this order:

1. A verdict line at the very top: `Verdict: ❌ FAIL` or `Verdict: ⚠️ WARN` or `Verdict: 🟡 MINOR` or `Verdict: ✅ PASS`, followed on the same line by the counts, for example `Verdict: ❌ FAIL (3 fails, 1 minor, 2 warns)`. The worst finding decides the verdict.
2. A **Findings** section, grouped by severity, worst first, one entry per problem: `❌`/`🟡`/`⚠️` + the check id (one: the check that names the defect most precisely) + what is wrong in one sentence + the exact file and line + the quoted evidence + **Bug/Error** or **Suggestion/Improvement** + `Fix:` followed by one concrete sentence stating how to repair it (every fail and minor finding must carry this fix line; a finding without an actionable fix sends the author back to guessing). Several gates often describe the same condition from different angles; that is one finding under one id, not one finding per id, so do not list every check that would also have caught it. If there are no findings, write `No findings.`
3. The gate's checklist, copied verbatim, not rephrased, not renumbered, with each `[ ]` replaced by `✅` (verified, no issue) or `❌` (problem found or could not verify). Every `❌` here must have a matching entry in Findings. The one other marker is `⏸️`, reserved for the Step 10 sign-off lines when the preflight showed this machine cannot run the harness. `⏸️` needs no Findings entry, because nothing about the bundle was found wrong; the report states which preflight command failed and what the machine is missing instead.

End after the checklist. Do not ask questions or offer follow-up actions.

For the consolidated end-of-run report (Starter.md), the same rules apply plus a per-gate summary table between the verdict line and Findings:

| Step | Gate | Verdict | Fails | Minors | Warns |
|------|------|---------|-------|--------|-------|
| 1 | structure_qc.py | ❌ fail | 2 | 0 | 1 |
| 10 | Execution gate | ⏸️ not run | 0 | 0 | 0 |
| ... | ... | ... | ... | ... | ... |

with one row per script, one per model gate, one for Step 10 and one for Step 11, and the overall verdict as the last row. Step 10 is the only row that may carry ⏸️ NOT RUN, and it never drives the overall verdict up or down; instead the line under the table says in plain words that the bundle is not cleared to ship until that gate is run for real.

## Foundational checks (do these before anything else in gate 05)

- [ ] F0a No template residue. Nothing in the bundle exists "because the sample task had it". Every file, every data artifact, every test earns its place for THIS task. Unresolved placeholders (`{{...}}`, `__NAME__`, `<TAG>`, TODO, FIXME, XXX, PLACEHOLDER) anywhere are a fail. The script covers only the first three forms, so search for the word markers yourself. One exception, judged by reading the hit in context: a task that deliberately ships a real source tree to be debugged or patched may carry genuine TODO or FIXME comments belonging to that shipped problem. Those are the task's own content, not residue, and you record them as a verified false positive.
- [ ] F0b Data dependency. If `environment/` were deleted, solving the task must become impossible. Data the task never needs is residue; a task solvable without its data is misdesigned.
- [ ] F0c Work dependency. There must be no way to pass the tests without doing the work the instruction describes. If a shortcut exists, name it.
- [ ] F0d No double scoring. No single fact may be graded by both a test and a judged criterion. Same observable = overlap, regardless of wording.
- [ ] F0e Solvability. Holding only `instruction.md` and `environment/`, which is all the agent ever receives, could a determined expert actually reach the graded answer? Difficulty may come from anywhere and none of it is a defect: traps, misleading surfaces, scattered data, a value in one file that only resolves once another is understood, chains of these, long search. The defect is information the agent needs that exists in none of its files and follows from nothing in them, such as a secret constant it must reproduce exactly with nothing to confirm it against. Default to pass; to fail, name the missing information and show it appears nowhere. The oracle scoring 1.000 proves nothing here, because the oracle already contains the rule. Mirror of F0b: F0b says the data must be needed, F0e says it must be enough. Full procedure in gate 02, DS-21.

## Client feedback checks (mandatory, run every one in gate 05)

Every check in this section exists because the client found the defect in tasks we already delivered, read our own files, and put a number on the damage. These are not hypotheticals and they are not style opinions: each one below shipped, was caught by someone else, and cost the delivery. Treat them with more suspicion than any other section, not less, and never mark one ✅ on the grounds that the bundle "looks reasonable" - each one names the thing to compute or quote, so compute it or quote it.

Run them with `instruction.md`, `tests/` (including `tests/judge.toml`), `solution/`, `task.toml` and `environment/` all open at once, because every one of these defects lives in the gap between two files rather than inside either. Both scoring channels count wherever a check speaks of grading: a judged criterion is a graded check exactly as a test is, and several of these defects can sit in either. Several overlap with checks you already ran (F0c, DS-21, TS-12, TS-27, AL-4). That is deliberate: when one of these fires, report it under its CL id as well, because the client found it and the existing check did not.

- [ ] CL-1 Every action the instruction demands is checked by something that looks at the action itself. List the actions the instruction asks for - start the service, call the endpoint, run the command, hit the API - and name what checks each one. Either channel counts: a test where the effect can still be inspected at grade time, or a judged criterion where the judge can see it in the trajectory. One or the other, not both, since the same observable graded twice is F0d/JD-8 overlap. What the checker must not do is settle for the agent's account of the action: a check that only reads a field the agent wrote proves nothing, because writing `"status": "ok"` costs nothing and a script that did no work at all can write it. Fail when an action has no checker, or when its only checker reads the agent's own summary of having done it. Scope it narrowly. This is for work that has an effect of its own, separate from the file the agent writes. Where the whole deliverable IS a computed artifact there is nothing else to look at and the check does not apply; whether that artifact could have been faked is CL-2 and CL-3. A client task shipped exactly this: the grader read only the agent's `report.json`, and a script that never started the service at all scored 1.000, byte-identical to the oracle.
- [ ] CL-2 Price the forgery before you accept the tests. Walk the positive tests and total what a deliberate fake earns: one hand-written artifact per declared path, filled with plausible values, produced by doing none of the work. Report that total as a share of the positive weight and name every test that paid it. A small share is normal and is not a defect by itself. Tests that pay for a parseable file, a valid shape or the deliverable simply existing are legitimate, and some tasks reasonably award a little for producing the right artifacts at all. Two things fail. One, the forgery reaching the range a genuine partial attempt would earn, because at that point the reward cannot distinguish faking from working. Two, any test that paid while believing it was grading content, which is a broken assertion regardless of the total. Say which of the two you found, or say the total is defensible and why. The number gets reported either way, because the value of this check is that somebody computed it: nobody did on the delivery the client audited, and outright fakes scored full marks on five separate tasks there.
- [ ] CL-3 The graded answer is earned, not copied. Take the values grading compares against - the tests, and any judged criterion that names a specific value - and ask whether they can be lifted straight out of something the agent already has: a field in a shipped file that happens to hold the answer, a constant sitting in the instruction, a worked example in the data. Deriving the answer is not this defect and never is - a task whose answer follows from processing the data is working exactly as intended, and CL-10 insists on that reachability. The defect is the answer being present rather than produced, so the tests cannot tell a solver from a transcriber. Present means identifiable as the answer: a value the agent could only recognise as the answer by first doing the work is a coincidence rather than a copy, and small integers will collide across unrelated fields routinely, so if you cannot say how the agent would know which value to lift there is nothing here. Fail, naming the file and field it can be copied from. In the client's finding the expected end state followed from constants plus one shipped plan file with no work in between.
- [ ] CL-4 Partial credit tracks partial correctness. Count the independently discoverable facts the deliverable carries (per field, per setting, per row), then read how the tests compare them. One wrong fact should cost about one fact's worth of reward. What fails is an answer that is almost entirely right scoring as though it were entirely wrong, and that happens two ways, both worth looking for: one whole-object equality settling N independent facts at once, and a pile of separately weighted tests that all key off that same single comparison. Report what an answer with exactly one fact wrong would score. Three things are not this defect. A fact that genuinely feeds the rest of the work costs what it costs: where an early value flows into every downstream artifact, getting it wrong really does leave the deliverable wrong in every one of those places, so charging for each is accurate measurement rather than a cliff. The discriminator is whether the output actually differs everywhere you charged. One wrong value that leaves the deliverable wrong in a single place while several weighted checks all re-read that same place is the double-charging this check exists for; a deliverable genuinely wrong in all of them is the curve doing its job, and that cost belongs to the dependency rather than to the grading. An instruction that states out loud that only an exact match counts has set that bar deliberately. And weight distribution by itself is fine: one test legitimately owning most of the reward because it checks the main outcome is good design, not a cliff, so do not go looking for a percentage. What matters is whether the curve can tell a near miss from a total miss. The client measured the failure: six of seven hidden settings correct scored 0.041, the same as none of them, because 14 tests worth +5 each all keyed off one dict comparison - 70 of 73 points turning on a single word.
- [ ] CL-5 No hidden conventions. Read the exact comparisons in the tests and ask what each one requires beyond the answer being right: the order of a list, the exact spelling of a key or a value, where the file goes and what it is called (`out.json` versus `/app/out/out.json`), letter casing. Each of those must either be stated in the instruction, or be stated as a rule in a file the agent is given, or be established by an example the agent is actually given in the copied input, or be compared in a way that does not care. Anything else grades telepathy. Only what the assertion actually enforces counts. A test that parses JSON and compares dictionaries does not care about key order or whitespace, so there is nothing to find there; you are looking at what the comparison really demands, not at strictness it could theoretically have had. Read the judged criteria the same way: a criterion that expects a naming or layout the contract never states grades telepathy just as a test does. Fail, and quote both the assertion and the sentence that should have promised it. The client found eight such gates in one task, demanding the gold file's exact keys, values and list ordering with nothing in the instruction about ordering at all.
- [ ] CL-6 A wrong value we shipped ourselves must be signposted as suspect. Find every place the bundle hands the agent a value it could reasonably copy - sample code, a config, a template, an example payload - and check it against what grading demands, tests and judged criteria alike. Where the two differ, something the agent can read must mark our material as not authoritative. Almost anything does: the instruction saying the shipped code is broken or stale, the task being a repair or debugging task at all, a spec file named as the authority the code must be reconciled against, or a stated symptom the agent can reproduce. This check does not object to traps and does not require the bundle to be internally consistent; wrong values planted on purpose are often the whole task. What fails is the unsignposted version, where the shipped value looks exactly as authoritative as the truth and nothing the agent can read distinguishes them, so passing depends on distrusting our own material for no reason we ever gave. Fail, quoting both values. The client's case turned on one word: shipped sample code used `omit`, the hidden truth was `emit`, nothing flagged the sample as unreliable, and taking our own material at face value cost 70 of 73 points.

- [ ] CL-7 Every file the instruction names exists where grading happens. List each path `instruction.md` tells the agent to read, then confirm each one is present in every corpus the tests grade against, not merely somewhere in the bundle. A path that exists in the sample data but not in the graded data is a fail, and it is the worst kind of fail because following the instructions literally is what triggers it. The client's task told the agent to settle its parameters against a control file the graded corpus does not contain: 26 FileNotFoundErrors, reward 0.124, for doing exactly what the instruction said.
- [ ] CL-8 The reference solution does not survive by cheating. Read `solve.sh` and `solve.py` for any branch that skips a step the instruction requires: a try/except that falls back to hardcoded expected values, a default used when an input is missing, a shortcut around an unreachable resource. If the oracle needs that branch to score 1.000, the task is unsolvable as written and the oracle is hiding it. Fail, and quote the branch. In the client's finding our own solution silently fell back to hardcoded parameters, which no honest agent could have discovered and which the task's own anti-cheat test punishes.
- [ ] CL-9 Grading does not supply what it measures. Read `test.sh` and every check in `test_output.py` in execution order and sort what happens before the assertions into two kinds. Setup that makes measurement possible is normal and expected: copying the agent's artifacts into place, starting the app so a test can query it, creating the empty database an assertion will inspect. None of that is a finding. What fails is setup that produces the value being measured - a step that exercises a workflow and thereby creates the records a later test counts, or writes a file a later test reads as though the agent had written it. Fail, naming the step and the assertion, and say which of the two kinds you decided it was.
- [ ] CL-10 Solvable from `instruction.md` and `environment/` alone, given unlimited time and resources. Those two are everything the agent ever receives; `solution/` and `tests/` are not uploaded to it. So for every fact grading actually asserts - tests and judged criteria alike - name where the agent gets it: a file it can read, or a derivation from one. Derivation counts fully and is meant to - working the value out from the data is the task, and long or difficult work is not a defect here. Any fact that exists only in `solution/` or `tests/` is unreachable: a constant hardcoded in `solve.py`, a magic value living only in an assertion, a threshold only `test_output.py` knows, a convention only the gold file demonstrates. That part of the task cannot be solved with any amount of time or compute, because the information is not in the agent's world at all. Fail, and name the fact, the file it hides in, and the agent-visible file that should have carried it. F0e states the general principle; CL-10 is the specific way we have broken it, so run it as a file-by-file trace rather than a judgement call.

## Consolidated sign-off

- [ ] structure_qc.py exits 0
- [ ] FC-S1..FC-S24 structure_qc.py output read, and every failure it reports confirmed in the file and carried into the report
- [ ] instruction_qc.py exits 0
- [ ] tests_qc.py exits 0
- [ ] judge_qc.py exits 0
- [ ] Gate 01 Instruction: no fail findings
- [ ] Gate 02 Data & Solution: no fail findings
- [ ] Gate 03 Tests: no fail findings
- [ ] Gate 04 Judge criteria: no fail findings
- [ ] Gate 05 Alignment & Integrity: no fail findings, F0a-F0e all clean
- [ ] CL-1..CL-10 client feedback checks all run, each one carrying the number it asks for or the file and line it asks for (never a bare ✅)
- [ ] Step 10 preflight run and pasted (harbor version 0.24.0 or newer, with the exact number recorded; docker reachable; bundle path listed), or the failing preflight command named with its exact error
- [ ] Step 10 oracle run executed for real FIVE times: all five exactly 1.000, every number reported individually (evidence pasted)
- [ ] Step 10 nop run executed for real: reward exactly 0.000 (evidence pasted)
- [ ] Step 10 owner-only oracle run executed for real: reward exactly 1.000 with the agent's 0600 modes reproduced (evidence pasted)
- [ ] Step 10 stub run executed for real: score reported, tests that paid named, judgement given with reasons (evidence pasted) (when the preflight showed this machine cannot run the harness, mark all four run lines ⏸️ rather than ✅ or ❌, keep the preflight line ✅ because it was attempted and reported, and state plainly that the bundle is not cleared to ship until the runs happen elsewhere)
- [ ] Step 10 runs made from `exe_copy.py` copies only: its full output pasted (judge.toml validated against the rewardkit 0.2.1 schema, judge.toml deleted, tests-only reward.toml weight, network roles opened), scores recorded as TESTS-ONLY, both copies deleted, and the original confirmed unedited
- [ ] Every oracle or empty-run score claimed anywhere in the bundle (TRUTH.md included) is scoped to the test channel; no judged-channel oracle score is claimed, because none can exist
- [ ] Step 11: re-check done, coverage mapping complete both directions, zero overlap between tests and judged criteria
- [ ] All warn findings shown to the tasker and approved
- [ ] Sign-off recorded: reviewer name, date, bundle name, verdict


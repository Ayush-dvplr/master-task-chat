# SCRIPT_RULES - what the five kit scripts actually compute (board 5087cd2)

Kit: `Terminal_2.0_Harbor_Harness/Input_Bundle_QC/` at HEAD `71a653b23fc2a6bc7ff3d4a8c286ec9a1b6a298e`. All paths below are relative to that folder. Runs were made only on copies in `/tmp/qc_reverse_A-20261024T1015/` (raw output: `run_<script>_<bundle>.txt`, probes: `probes.py`, `probes/<name>/`).

## 1. Baseline runs on the two copied bundles

| script | dispatch-plan-reoptimization | emberforge-vault-settlement |
|---|---|---|
| structure_qc.py | exit 0, 17 pass, 1 warn: `WARN [X1]` 5 binary files skipped (amendment_memo.docx, capital_program.xlsx, ledger_authority.sqlite, penalty_schedule.pdf, xref_manifest.db) | exit 0, 17 pass |
| instruction_qc.py | exit 0, 5 pass (C1 7200s) | exit 0, 5 pass |
| tests_qc.py | exit 0, 35 pass, 1 warn: `WARN [A3]` 36 checks > 35; O1 0% of 1015 lines; no H6 line (no privilege drop) | exit 0, 37 pass; O1 5% of 841; H6 pass |
| judge_qc.py | exit 0, 19 pass | exit 0, 19 pass |
| exe_copy.py (plain / --stub / --owner-only) | all exit 0; reward.toml `test_output = 0.009900990099009901` (1/101); network set public in 4 tables; dropped only the 7-line uv/openhands RUN | all exit 0 |

`diff -rq` of each exe copy against its source: only `environment/Dockerfile`, `task.toml`, `tests/reward.toml` changed and `tests/judge.toml` removed; `--stub` also deletes `solution/` contents (TRUTH.md, solve.py) and writes one `: >` / `echo '{}'` line per artifact (22 for dispatch); `--owner-only` appends the chmod trailer.

Exit codes are uniform: `return 1 if FAILS else 0`, usage 2 (structure_qc.py:1146, tests_qc.py main L1043, judge_qc.py:383, instruction_qc.py:303). Warns never change the exit code; every script prints "WARN - tasker approval needed" as its verdict when warns exist (structure_qc.py:1145).

## 2. Mutation probes (emberforge copy, one change each)

Caveat found first: structure_qc T13 requires `[task] name = "terminal-bench/<dir name>"` (structure_qc.py check_pinned L624-641), so any copy whose folder is renamed fails T13 (`FAIL [T13] [task] name must be 'terminal-bench/null_floor_int'`). Run kit scripts on copies that keep the bundle's folder name.

| probe | result (quoted) | md says | verdict |
|---|---|---|---|
| `null_floor = 0` (int) | `FAIL [T13] [metadata] null_floor is pinned to 0.0 ... got 0` (structure_qc.py:633 `if got_val != want or type(got_val) is not type(want)`) | template `null_floor = 0.0` (Final_checklist.md template L44-96) | STRICTER: type-exact, `0` fails |
| `COPY . /app` | `pass [S4]` then `FAIL [S7] ... copies the whole build context` | FC-S17 "COPY nothing outside environment/" | consistent; S4 counts it, S7 fails it |
| `# allow_internet` in a comment | `FAIL [T12] allow_internet must not appear in task.toml` (structure_qc.py:617 `if "allow_internet" in raw:`) | harness fact 5 "no allow_internet" | STRICTER: raw-substring, even comments |
| `TODO` in environment/data md | `WARN [X2] work marker 'TODO' ... read in context` (structure_qc.py:762, L1102) | F0a: word markers "anywhere are a fail" unless task-owned | LOOSER: script warns, reader must fail |
| `__FILE__` in environment data | `FAIL [X2] unresolved placeholder '__FILE__'` (PLACEHOLDER_RE structure_qc.py:761 `__[A-Z][A-Z0-9_]*__`) | F0a exception only for TODO/FIXME in a shipped source tree | STRICTER: a C/Python source tree shipping `__FILE__`, `__LINE__`, `__INIT__` style tokens fails with no exception |
| `{{task_name}}` (lowercase) | no X2 line at all | F0a "`{{...}}` ... anywhere are a fail" | LOOSER: regex is `\{\{[A-Z0-9_]+\}\}`, uppercase only |
| em dash in environment data | `FAIL [X1] em/en dash ... clerks_digest.md:17` | FC-S13 "no em/en dash anywhere in bundle" | consistent, but note: covers agent-input data too, so shipped real-world documents with dashes fail |
| remove `ENV HOME` | `FAIL [S10] ... HOME is not set` | DS-30 | consistent |
| move `ENV HOME=/root` to the end | `pass [S10] uid 1000 agent account with HOME created` | FC-S24 "`ENV HOME=/home/agent`, right after `FROM`" | LOOSER: any `ENV HOME=` anywhere in the final stage passes, wrong value and placement included |
| `trajectories/run1/notes.txt` | `WARN [S3] trajectories/ ... accepted by delivery policy` | (newest commit 71a653b2) | warn-only by design |
| description 122 words | `FAIL [T5] ... over 100 words (122)` | FC-S9 | consistent |
| judge "checks about that entry" | `FAIL [J11] R1: vague qualifier 'about'` | JD-3 list | STRICTER in practice: "about"/"around" as plain prepositions fail (word-bounded, judge_qc.py:138-145) |
| judge "some" | `WARN [J11] R1: 'some' present` (judge_qc.py:295-296) | JD-3 "\"some\" it only warns about" | consistent |
| judge description contains `TODO` | `FAIL [J12] R1: placeholder/marker in description` (judge_qc.py:147 `\bTODO\b|\bFIXME\b`) | F0a allows task-owned TODO | STRICTER: a criterion naming a shipped TODO comment fails |
| judge "not" | `FAIL [J10] ... negative-grammar token 'not'` | JD-2 | consistent; applies to positives too |
| judge `weight = 3.0` | `FAIL [J5] ... got 3.0` | JD-S7 | type-exact |
| judge `timeout = 600` | `FAIL [G2] [judge] timeout must be 300` | JD-S2 | consistent |
| test.sh `... || true` | `FAIL [B5] test.sh has an exit, return or || path` | TS template | STRICTER: bans every `||` and every `exit`/`return` token anywhere in test.sh |
| test.sh `chmod 700 /logs/verifier` | `WARN [H5] ... prefer 755` exit 0 | TS-28: "755 not 700, 700 = H5 warn" | consistent |
| test.sh without `chmod -R go-rwx /tests` | `WARN [H3] /tests not restricted` exit 0 | TS-28 defence | warn-only; reader decides |
| tests/Dockerfile `litellm==1.104.0` | `WARN [K8] litellm pinned to 1.104.0, not the litellm==1.105.0 ...` | TS-2 L26 "another exact version is a warn"; Final_checklist L37 "Both pins are required"; 03 checklist L103 "litellm==1.105.0" | script follows L26; checklist line is stricter (inconsistent kit) |
| `litellm==1.107.0` | `FAIL [K8] litellm==1.107.0 is withdrawn` | TS-2 quarantine | consistent |
| instruction "rewards" | `pass [C3] no 'reward'` (instruction_qc.py:235 `\breward\b`) | IN-2 | LOOSER: plural slips through |
| instruction "reward" | `FAIL [C3]` | IN-2 | consistent |
| instruction "tests/ folder" | `pass [C2]` (instruction_qc.py:75-78 deliberately excludes bare `tests/`, `solution/`) | IN-2, IN-S5 | LOOSER by design; reader owns it |
| instruction "/logs/verifier" | `FAIL [C2] ... '/logs/verifier'` | IN-2 | consistent |
| instruction "verifier" in prose | `WARN [C6]` | IN-2 | warn-only |
| instruction names `/app/data/generated/extra.csv` created by `RUN` | `FAIL [C4] instruction names /app/data/generated/extra.csv but no environment/Dockerfile COPY puts it there` (instruction_qc.py:257 `found is None and path.startswith("/app/data/")`) | IN-5 (01:35) "anything `environment/Dockerfile` puts there, whether copied in, generated by a `RUN` step ... legitimate" | STRICTER: contradicts IN-5 under /app/data/; the same path outside /app/data/ is skipped |
| instruction "You have 60 seconds" vs 7200 | `FAIL [C1] instruction says 60 seconds but [agent] timeout_sec is 7200.0` | IN-S | consistent; sentence missing is also FAIL (instruction_qc.py:213) |
| instruction "robust ... crucial" | no P2 line | IN-L2 register | LOOSER by design (only `robustly` listed, instruction_qc.py:66) |
| instruction "Delve" | `FAIL [P2] banned high-register word: 'delve'` | IN-L | consistent |

## 3. Code-only rules (in a script, absent or weaker in the md)

1. structure_qc T13 type-exact pins (structure_qc.py:633): `0` vs `0.0`, `"1000:1000"` string, `gpus = 0` int.
2. structure_qc T12 raw substring `allow_internet` (L617), comments included.
3. structure_qc S7 wildcard COPY source is a WARN (L397); `..` and `.` sources FAIL (L387).
4. structure_qc S5 `.DS_Store` always fails, run-record names under `trajectories/` only warn (L335-338).
5. structure_qc T14 author name "STRONG" words (L136-139: created, generator, qc, harness, anubis, harbor ...) fail; name not related to email local part is a WARN (L511-514).
6. structure_qc S8 replays the final stage only; `COPY/ADD` dests are root-owned unless `--chown` (L868 "COPY/ADD write root-owned files whatever USER says"); `chmod` only counts if the mode is world-writable (L764); paths with no known ancestor fail unless under /tmp.
7. structure_qc S9 needs `chmod -R a+rX` on `/opt/openhands-sdk-venv` and a build-time `import openhands.sdk`; `fastapi` must be present but unpinned.
8. tests_qc D1 (L510-514): in `test.sh` and `tests/Dockerfile` ANY non-comment line containing an input-mount path (`/app/data` or a COPY dest) fails, including `rm` or `echo` lines; in test_output.py only unguarded string constants fail.
9. tests_qc B4 (L578-580): any `.py` under `tests/` naming `/logs/verifier` or `reward(.txt|.json)` fails.
10. tests_qc K4: every third-party import in test_output.py must be named in tests/Dockerfile text (PIP_ALIASES map).
11. tests_qc K7: `ENV LITELLM_LOCAL_MODEL_COST_MAP=True` required (fail).
12. tests_qc K8 compares to the constant `LITELLM_PIN` (tests_qc.py:162), not to the line actually in environment/Dockerfile, although its docstring (L605) says "matches the version the agent image pins". A bundle bumping both images to 1.106 gets a WARN, not a pass.
13. tests_qc R3: `weights.judge` (JD-S13) is enforced by tests_qc, not judge_qc; float type required; `weights.test_output` check is skipped (WARN) whenever W1-W3 fail.
14. tests_qc O1: overlap only measured against `solve.py`; a `solve.sh`-only oracle gets `ok "judge solve.sh by reading"`. Lines under 12 chars and imports excluded; <30 substantive lines warn.
15. tests_qc A5: TS-29 "never raise" is only a heuristic WARN (file read/subprocess outside any `try`); literal non-bool returns fail.
16. tests_qc A4: `{` or `}` in a `@criterion(description=...)` fails (rewardkit str.format KeyError).
17. tests_qc H6 only runs when test_output.py drops privileges and builds `[sys.executable, ...]` argv; otherwise silent (dispatch: no line at all).
18. judge_qc J10 negative tokens and J11 vague words apply to every criterion, positives included; J12 bans any `[` or `]` and a tag prefix `^[A-Z]+\d*\s*[:\-]`.
19. judge_qc header compare is key order + value + exact Python type (L179).
20. exe_copy.py refuses only on tests_qc A1-A4/W1-W7 fails (GATING_IDS L76) or an unloadable judge.toml; every other script FAIL still lets Step 10 run.
21. exe_copy.py strip_openhands (L196-213) deletes the whole backslash-continued Dockerfile instruction matching `openhands[-_.](?:sdk|tools)|/opt/openhands-sdk-venv`; a task dependency installed in the same `RUN` silently disappears from the Step 10 copy, so the oracle can fail there (or pass for a different reason). Harmless in both sample bundles (openhands RUN is standalone).
22. exe_copy.py --owner-only trailer touches only files `-user 1000` under `/app`. 02_Data_Solution_QC.md:50 states "`[agent] user = "1000:1000"` runs the agent and the oracle as uid 1000"; that Harbor really runs solve.sh as uid 1000 is UNVERIFIED here (no harbor run allowed). If it ran as root the trailer would be a no-op and the owner-only run would prove nothing.
23. exe_copy.py --stub writes `{}` for `.json` and empty files otherwise; nothing else (no directory artifacts are created beyond the file path).

## 4. Where code is stricter or looser than the md (one line each)

- STRICTER: C4 vs IN-5 (RUN-created /app/data paths); X2 `__X__` vs F0a source-tree exception; J12 TODO vs F0a; J11 "about"/"around"; T13 types; T12 comments; B5 any `||`; D1 any shell line naming a mount.
- LOOSER: X2 lowercase `{{x}}`; X2 word markers warn (F0a fail); S10 ENV HOME placement/value; C3 "rewards"; C2 bare `tests/`; P2 non-exhaustive list; A5 heuristic only; O1 skips solve.sh; H3/H4/H5 warns; K8 other exact pins warn.
- SCRIPT-SILENT (md-only, judgement): every IN-/DS-/TS-/JD-/AL-/CL-/F0 semantic check; Final_checklist.md:315 "The script proves none of the semantics: whether content is true, consistent, natural, solvable or honest lives entirely in gates 01-05."

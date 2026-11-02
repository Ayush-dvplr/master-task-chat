# P6 Oracle, nop and stub runs, template v1 (21 Oct 2026)

=== PASTE BELOW ===

Run the oracle, nop and stub checks for one Harbor 0.24 bundle, using Harbor 0.24.0 and harbor-rewardkit 0.2.1. Grade the tests only, because these runs have no OpenAI key.

First read in full: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/_COMMON_RULES.md`, then the QL procedure, `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/intake/ql_oracle_nop_procedure.md`. Follow the QL procedure exactly. The steps below only add to it.

## Inputs
- BUNDLE: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/[[SLUG]]/` (never edit it)
- OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/[[DATE]]_[[SLUG]]/runs_r[[ROUND]]/`
- Copy root: `/tmp/oracle-qc-[[SLUG]]-<YYYYMMDDTHHMM>/[[SLUG]]/` (same folder name as the bundle)

## Steps
1. Preflight, quoting the output of each: `harbor --version` (0.24.0 or newer), `docker ps`, and `ls` of BUNDLE. If any fails, report NOT RUN with the quoted error and stop.
2. Make the copy and apply QL steps 2a to 2d. Record every change made to the copy.
3. Run the oracle 3 times and the nop once, each in the background with its own log. Check `harbor run --help` for flags, and pass `-y`.
4. Stub, if possible: make a second copy whose `solution/solve.sh` writes every declared artifact with an empty shape (`{}` for .json, an empty file otherwise). `exe_copy.py --stub` from QC may be used for this on a fresh destination. Run it once with the oracle agent. If the stub cannot be built or run, write "stub dropped: <reason>".
5. For each run, read the reward from `verifier/reward.json` (or `result.json` `verifier_result.rewards.reward`). On a failure, name the checks from `reward-details.json` or quote the verifier error.
6. Delete both copies at the end.

## Expected
- Oracle exactly 1.0 on all 3 runs.
- Nop exactly 0.0.
- Stub at most 0.25, with every check that paid it named.
- Different scores across runs of the same agent mean nondeterminism: report it.

## Deliverables (OUT)
- `RUNS.md`: preflight output, a table of agent, run and reward, the failing or paying checks, the copy changes, and log paths.
- `runs.json`: `{"oracle":[x,x,x],"nop":x,"stub":x|null,"stub_paid":[...],"nondeterministic":false,"changes":[...]}`

Final reply: the oracle values, nop, stub, any failing check names, and paths.

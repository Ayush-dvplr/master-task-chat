# Read-only scan: verifier permission bug in Anubis Pass@1 bundles

Board id: `4b75115`. This prompt is saved at `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_adhoc/20261022T1100_passat1_permission_scan.md`.

## Rules
- First thing, and again as your last command: rename this session to `4b75115`:
  python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" 4b75115
- READ ONLY. Never pull, fetch, commit, push, merge, checkout, reset or open a PR.
- Allowed git: log, show, diff, status, ls-remote, rev-parse, and gh api GET.
- Repo: /Users/mac/Desktop/Terminal Bench/Anubis_Tasks_Samples (ShreeyankDoliya/Anubis_Tasks_Samples). Local HEAD was d0c847eb at 11:03 IST 22 Oct.
- Scratch folder: /tmp/passat1-scan-20261022T1100. Delete it at the end. Never write inside the repo.
- Long commands (over ~4 min): nohup with logs in /tmp/opencode-logs/passat1-scan-20261022T1100/.

## Step 1: Remote check
- Compare `git rev-parse HEAD` with `git ls-remote origin HEAD`.
- If they differ, also list which `Pass@1/` paths differ (`gh api GET` on the compare endpoint). Do not pull. Scan the local copy and say in the reply: "local behind remote, Ayush to run git pull --ff-only", plus the differing Pass@1 paths.

## Step 2: Scope
- Every task bundle under `Pass@1/` (sub-folders per person: Dinshi_Jain, Poonam_Chourey, Sugam_Agrawal, and any others).
- List each bundle path.

## Step 3: Checks
For each bundle, check tests/test_output.py (and any helper it imports) and tests/test.sh, citing file:line for each:
1. Does the verifier drop privileges (setpriv, su, runuser, preexec_fn setuid, `nobody`, uid 4001)?
2. Does it run or read an agent-written path under that uid without copying it and chmod-ing it readable first?
3. Does it create inputs with tempfile.mkstemp, mkdtemp or NamedTemporaryFile (0600/0700 by default) and pass them to the dropped-uid process without chmod?
4. Does it rewrite modes on unpack (0644 files / 0755 folders)? If so, mark that path SAFE.
5. What value does test.sh pass to chmod for /logs/verifier (700 or 755)?
6. Does it kill leftovers only with killpg, with no per-user kill?

Verdicts:
- AFFECTED: check 3 is true (grader's own inputs unreadable; breaks even the oracle).
- LATENT: check 2 is true (breaks only when the agent saves its file 0600).
- SAFE: no uid drop, or every dropped-uid path is copied/chmod-ed/unpacked readable.
- UNSURE: cannot tell from the code; say why.

## Step 4: Proof (only if `docker ps` shows fewer than 2 heavy jobs)
- For up to 2 bundles marked AFFECTED or LATENT: run the oracle once normally, then once with the oracle's program files set to 0600.
- Report both tests scores.

## Output
Write to /Users/mac/Desktop/Terminal Bench/master_chat_work/20261022_pl-note/passat1_scan/:
- SCAN.md: the commit, a table with one row per bundle (columns as in §5 of ../PL_NOTE_low_scores.md), and the verdict with file:line evidence.
- scan.json: the same rows.

Do not edit PL_NOTE_low_scores.md.

Reply with:
- the counts per verdict;
- the AFFECTED and LATENT bundle names;
- the probe scores;
- anything you could not verify.

# Phase A: emberforge-vault-settlement, attempt 7 (claude-opus-5): is the score genuine?

Board id 5af6646. RUN = `master_chat_work/20261023_emberforge-vault-settlement/traj_a7/job/trajectory/claude-opus-5/Run 1`. TASK = `master_chat_work/bundles/emberforge-vault-settlement` (bundle fingerprint `4bbe6df3514c9a1842ed8eba9f4e70010dc484f1`, not a git checkout, repo_head n/a).

## Verdict: PARTLY

There is no run artefact. Every check ran the program, and the local rescoring reproduces the recorded 16/54 = 0.2963 exactly. Of the 38 test points lost:
- **20 are GENUINE**: an allocator defect against plainly stated rule Q5.
- **18 come from one graded rule that the visible text no longer settles**: whether a forge in the salvage window is resolved to a canonical smith on its own filing day or on the salvage day. This is an IN-16 ambiguity, not a misreading. Harden lp1 r1 created it by deleting the I3 closing sentence that settled the question.

The 9 judge points lost (R1-R3) are genuine, meetable conduct losses. None of L7, L3 or L6 caught the agent.

## 1. Run health
- `result.json`: `exception_info` null. Agent ran 15:00:47Z-15:41:06Z (about 40 min, 93 steps, well under MAX_ITERATIONS 350 and the 7200 s limit). Verifier ran 15:41:16Z-15:42:07Z. Reward 0.2731. `verifier_environment_mode` "separate".
- `verifier/report.json`: 8 passed, 14 "failed". The 14 include the 6 negatives, which count as "failed" when they do not fire. Test reward 0.2963 = 16/54: the 4 structure checks (1 each) plus unit_charge, cap_release, mutation_family and mutation_grade (3 each).
- `verifier/test-stdout.txt` (34 lines): every failing line has the form `check note: forge_X: <doc> differs from the settled season` (allocation appears only for forge_a, line 17, and forge_d, line 18). Line 24: `test_live_window_refusals: AssertionError: iso_live_window: the UNCREDITED_SALVAGE findings differs from the settled season`. A grep finds no `Permission denied`, `Errno`, `No such file`, timeout, traceback, collection error or skipped test.
- `reward-details.json`: the judge component scores 3/12 (only R4 passes). No errors.

## 2. Permissions (attempt 4 artefact ruled out)
- Trajectory step 16, `ls -la out/`: `-rw------- 1 agent agent 47107 Oct 23 15:11 settle_vault.py` (file_editor creates files at 0600). Step 17 then ran `chmod 644 out/settle_vault.py`.
- The grader does not depend on that mode either way. `tests/test_output.py:2299-2310` `_stage_program` copies the program to a temp directory at 0644 ("An editor saves the agent's file at mode 0600, which the sandbox account cannot open, so every run executes this copy"). `_drop_privileges` (2220-2236) then runs it as uid 4001 through setpriv. `tests/test.sh` runs `chmod -R go-rwx /tests; exec rewardkit /tests --workspace /app`.
- The collected `artifacts/app/out/settle_vault.py` is 50,991 bytes, and `artifacts/manifest.json` lists every file as status ok.

## 3. The program ran on every hidden season
- `_season()` (test_output.py:2961-2978) sets `got=None` when the run fails. The note then says "the program settled nothing" (2986). All recorded notes say "differs" instead, so the program finished and wrote each document on forge_a to forge_d and on every iso and mut season.
- Local proof: OUT/work/score_prog.py imports the grader with a stubbed `rewardkit`, stubs setpriv, and calls the grader's own `test_*` functions on the hidden seasons built by `_build_corpus_dir`. The delivered program scores **12/50 value points + 4 structure = 16/54 = 0.2963**, the recorded figure exactly. The oracle (`solution/solve.py`) scores 50/50, and its documents equal the grader's `settle()` on all 10 seasons (OUT/work/run_compare.py: 0 differing docs).

## 4. Root cause (local runs, copies under OUT/work)

### 4a. Divergence 1: which day resolves a window forge's smith (18 test points)
- **First divergent field.** On the shipped season, `summary.json` `credited_salvages` is 40 for the agent and 37 for the oracle. `entries_admitted` is 169 vs 166. In `data_quality.json`, the oracle alone reports UNCREDITED_SALVAGE for L0124, L0127, L0195 and L0252, and the agent alone reports SALVAGE_ALREADY_CREDITED for L0124. On iso_live_window, credited is 64 for the agent and 71 for the oracle. The UNCREDITED ids reported only by the oracle are L0026, L0163, L0240, L0248, L0251, L0257, L0284, L0287 and L0288.
- **One line.** `agent_settle.py:733-735`:
  `window = [cand["entry_id"] for cand in live if cand["family"] == family and cand["day"] < day and identity.canonical(cand["smith_ref"], day) == canon][-3:]`
  This resolves each earlier forge's handle on the **salvage** day. The oracle (`solve.py` `_forge` 533-579 and `_salvage` 581-614) keys each forge by its smith's canonical identity on the **forge's own** filing day.
- **Proof.** OUT/work/agent_variant_forgeday.py changes only `day` to `cand["day"]` on line 735. Its output equals the oracle on the shipped season (`diff -rq` is clean) and on 9 of the 10 hidden seasons. forge_a then differs only in allocation documents. The variant scores 30/50 + 4 = 34/54: it gains whole_vault_audit, whole_reconciliation, whole_data_quality and live_window_refusals. So this one line costs 18 test points (3 whole docs x5 + 3).
- **Worked case** (iso_live_window, salvage L0026 naming forge L0016).
  - IE011 (day 100) merges S008 into S030, and IE005 (day 129) renames S030 to S030-x.
  - The forge L0016 is filed on day 117 under S008, which resolves to S030 that day.
  - The salvage L0026 is filed on day 165 under S008, which resolves to S030-x that day.
  - The oracle puts the forge with S030, outside S030-x's window, so the salvage is UNCREDITED. The agent re-reads S008 on day 165 as S030-x, so the salvage is credited.
- **Every visible location of the rule:**
  - `rulebook_salvage.md:14-19` (S2): "A salvage is credited only when the forge entry it names is among the last three live forge entries of the same artifact family settled for the same canonical smith on days strictly before the salvage's own day. The canonical smith is the one the salvage's own handle resolves to on the salvage day, and the forge entries are read against that canonical smith whatever handles they were filed under."
  - `rulebook_identity.md:14-17` (I1): a rename means "the smith previously known by one handle is known by another from that day forward". A merge means "the absorbed handle is the same smith as the surviving handle from that day forward".
  - `rulebook_identity.md:22-25` (I2): the canonical identity on a given day applies renames and merges on or before that day.
  - `rulebook_identity.md:30-34` (I3): "Canonical identity is a function of the day as well as the handle. A handle filed before a rename or a merge takes effect resolves to whatever it resolved to on that earlier day, and a handle filed after resolves to the later result."
  - `rulebook_identity.md:45-47` (I5): reporting uses canonical identities. Also `invariants.md:55-57` (N7), `rulebook_admission.md:28-29`, `record_shapes.md:94-95`, `finding_codes.md:22-23`.
- **Two readings.**
  - Reading A (agent): S2 "whatever handles they were filed under" together with I1 "known by another from that day forward" means the same person. A forge filed under S008 belongs to whoever the salvage's smith is on the salvage day.
  - Reading B (grader): I3 says a handle filed before a rename resolves to what it resolved to on that earlier day. The forge's smith is therefore S030, which is not S030-x.
  - Neither reading contradicts any visible line.
- **The tiebreak was deleted.** Older copies of `rulebook_identity.md` I3 end with "Two entries filed under the same handle on either side of a rename or merge therefore belong to different canonical smiths." Examples are `Anubis_Tasks_Samples/Low_Effort_Tasks_(Client_Fixed)/With_Trajectory/emberforge-vault-settlement/environment/data/rulebook_identity.md` and `.master-queue/task-archive/emberforge-vault-settlement-20261021T173133/`. That sentence settles the case for Reading B. WORK LEVERS.md 'Harden lp1 r1' lists "I3 closing sentence" among "Giveaway text removed". DESIGN.md:66 and QC_DEFENCE.md:100 also record the removal. LEVERS.md:13 marks identity as L4 and not one of the focal levers.
- **The agent saw the fork and chose Reading A deliberately.**
  - Step 22 prints "candidate pairs where the two readings disagree: 38".
  - Step 24 builds /tmp/alt_sv.py with the own-day reading and prints "own-day reading: credited 37": the oracle's figures exactly.
  - Step 91 (`/app/AGENTS.md`) and step 93 (final answer, "Judgments the texts forced") say: "S2 reads candidate forges against the salvage's canonical smith *as of the salvage day* ("whatever handles they were filed under")".
  - Both blind solves made the same choice (blind_r1_settle.py:449-450, blind_r2_settle.py:362-364).
- **Verdict for divergence 1: not GENUINE.** It is not a HIDDEN RULE either, because I3 does state the reading the grader uses. The S2 sentence "whatever handles they were filed under" supports the other reading, and nothing visible breaks the tie. This is an IN-16 ambiguity, filed below as CHECK BUG (the contract under-determines a graded answer). It meets all three IN-16 parts:
  1. It is graded: whole_vault_audit, whole_reconciliation and whole_data_quality (and the other whole docs on forge_b/c/d), plus live_window_refusals.
  2. Two readings are defensible: 3 of 3 strong solvers chose A, and the agent named the fork in writing.
  3. No visible tiebreak remains. I searched the salvage, identity, admission, invariants, record_shapes, finding_codes, convention_register and clerks_digest files; whether anything else breaks the tie is INFERRED from those reads. The precedent is QC_RULINGS IN-16, emberforge v1 salvage, FAIL.

### 4b. Divergence 2: allocator Q5 defect, forge_a only (20 test points)
- **First divergent field.** forge_a `allocation.json` `allocated_total` is 92 for the agent and 160 for the oracle. This cascades into `summary.allocated_units_total`, the guild reports' `allocated_units` and the workshop reports' allocations. No identity reading changes it: the variant still fails whole_summary, whole_allocation, whole_workshop_reports and whole_guild_reports, worth 20 points.
- **Rule.** `rulebook_requisitions.md:26-30` (Q5): "For each reagent the reagent registry marks scarce, the units granted for that reagent across every requisition may not exceed the vault's closing balance". Related rules: Q7 :36-37 (maximise the total) and Q8 :39-44 (prefer by priority, then id).
- **Mechanism.**
  - The agent's max-flow `_capacity` (agent_settle.py ~962-1043) sends every requisition through one shared guild node. That node's output reaches the sink either through the reagent's node or directly. So flow for scarce R02 can bypass R02's cap of 30. `_capacity({'RQ05':(6,17),'RQ11':(9,16),'RQ01':(8,18)}, [])` returns 51; the true maximum is min(17+16, 30) + 18 = 48.
  - The overestimated bound makes `solve()` fix RQ05 at 17. An exact DP (OUT/work/brute_alloc.py) gives 156 for that choice, not 160. `solve()` never checks that its final sum reaches the target, so the plan collapses to 92.
- **Self-tests.** Steps 30 and 63 compared the allocator with a brute force on 6-requisition corpora built from the shipped closing balances ("checked 60 fails 0"). INFERRED: those scarce balances are large (about 50,000), so the scarce cap never bound and the leak stayed invisible.
- **Verdict: GENUINE.** The rule is one plain sentence, the defect is in implementation, and no reading question is involved. On the shipped season the agent's allocation matches the oracle (54), which is why the agent could not see the bug.

### 4c. L7, L3 and L6 held
- **L7**: `entry_charge` (agent_settle.py:582-597) reduces after each operator and then computes `charge = value * info["units"]`, as H5 requires (`rulebook_charge.md:39-43`). season_charge_ember matches in every season.
- **L3**: `accrued[src_wid] -= charge_of.get(ref, 0)` on credit (line 755), as S5 requires (`rulebook_salvage.md:42-46`). CAP_REACHED matches in every season.
- **L6**: `live = [cand for cand in live if cand["entry_id"] != ref]` (line 752), as the "Live forge entry" term requires (`invariants.md:10-11`).
- All three were present in the first full write at step 15 (15:11:14, trajectory index 14).

## 5. Judge
- Judge gpt-5.6-sol, batched, reads `/logs/agent/trajectory.json`. `judge_response.txt` quotes trajectory commands such as `/tmp/mis`, the 840-draw experiment and altered-cap corpora, so it read the trajectory.
- **R1-R3 failed** because no targeted season was built.
  - R1: "did not build and run a focused season with a fractional intermediate operator result".
  - R2: "did not build a targeted season where a credited salvage precedes a later cap-tested forge".
  - R3: "No targeted season was built and run to test whether an already-credited forge is excluded".
- **Each is meetable (JD-7).** `solution/solve.sh:102-132` builds and runs three probe seasons:
  - R1: one 2-unit forge, checking workshop charge == 2 x unit charge.
  - R2: a forge, then a salvage, then a later forge, checking for no CAP_REACHED and entries_admitted == 3.
  - R3: PX006 not UNCREDITED_SALVAGE, with credited_salvages == 2.
- All three are graded on behaviour (build a season, run it, check one output), not on a figure. They are the J2 conduct criteria, one per lever. The trajectory shows no such season. Step 84 mutation corpora covered other edge cases, and steps 27-63 were allocation stress and brute-force runs. The loss is genuine: 9 of the 12 judge points.
- **R4 passed**: "/tmp/mis ... exited with status 2 and printed 'error: missing required input file: /tmp/mis/council_rulings.json'".
- **Negatives did not fire.** R5: "only reads or copies files from /app/data into temporary directories". R6: "no network access or lookup of an online solution". R7: "does not explicitly claim ... zero mismatches". R8: "did not open, list, or copy anything under /tests or /logs/verifier".
- **Caveat.** R1-R3 reward probing the three levers, and all three were implemented correctly. The 9 points measure conduct, not correctness. JD-15 has no ruling on conduct criteria yet (PL Q46).

## Lessons for the master
- Rescoring locally with the grader's own `test_*` functions (rewardkit stubbed) reproduced report.json exactly. Use it as the standard Phase A proof that a score is not an artefact.
- A one-line variant of the delivered program that scores +18 is the fastest way to prove a single-rule cause.
- Removing a "giveaway" sentence can delete the only tiebreak for a graded fork. Diff the rulebooks before and after each harden pass for IN-16.
- All 3 strong solvers losing on the same unfocused rule is an IN-16 signal, not lever hardness. The blind notes' "L6 caught" was a misattribution.

# Questions for the PL / QC lead

Date: 22 Oct 2026, 12:45 IST. Author: Ayush Sah.
All line numbers are from the harness repo `Terminal_2.0_Harbor_Harness` at `bfe40804` (current remote), unless the line says otherwise.

| # | Topic | Who it affects |
|---|---|---|
| 1 | `chmod 700` or `755` on `/logs/verifier` | **Everyone** who builds with the generator or runs this QC |
| 2 | A QC rule (IN-15) still looks for a removed judge key | **Everyone** who runs this QC |
| 3 | Two judge/test rule readings (JD-15 step 2, TS-20) | Found on my task, but the answer applies to **everyone's** bundles |
| 4 | Two more judge rule readings (JD-13, JD-5 vs JD-18) | Found on my tasks, but the answer applies to **everyone's** bundles |
| 5 | Three generator/QC bugs or unclear points | **Everyone** who uses the generator or this QC |

---

## 1. `chmod 700` or `755` on `/logs/verifier`?

**In short:** the generator and QC now ask for `chmod 700` on the folder where the verifier writes the score. An earlier PL commit said 700 makes Harbor fail to read the score file on Linux, and used 755 instead. That fix was later undone. If the earlier commit was right, every new bundle could lose its score on a Linux host.

**Who it affects:** everyone. All generator templates write `chmod 700`, and QC `tests_qc.py` H5 warns on 755.

**Evidence:**
- Commit `8c37863a` (Sugam Agrawal, 21 Oct) switched to 755 and added this comment to `test.sh`:
  > 755 rather than 700: Harbor reads the bind-mounted reward file back as the host user, and a root-only directory makes that read fail on Linux.
- Commit `bde868c4` removed that comment. The merge `bfe40804` then brought back 700: `git diff f0579497 bfe40804` is empty for the generator and QC.
- On our macOS host, both 700 and 755 worked (runs on 20 and 21 Oct).

**Question:** on the Linux machines that run the harness, is 700 safe, or should it be 755? Which value should QC H5 require?

**Until you answer:** I use 700 on new and rebuilt bundles. Older migrated bundles stay at 755, which only gives an H5 warning.

---

## 2. QC rule IN-15 still looks for a removed judge key

**In short:** IN-15 tells the reviewer to find judge criteria marked `kind = "constraint"`. That key was removed from the judge format, and QC now fails any bundle that still uses it. So in any current bundle the reviewer finds nothing, and the IN-15 check is quietly skipped.

**Who it affects:** everyone who runs this QC. This is the gate 01 instruction check.

**Evidence:**
- `Input_Bundle_QC/01_Instruction_QC.md:45` (IN-15):
  > list every criterion whose `[criterion.annotations]` table carries `kind = "constraint"` (which always comes with `category = "instruction following"`)
- `Input_Bundle_QC/04_Judge_QC.md:46`:
  > `category`, `kind`, `serves`, `residue`, `evidence`, `contract_sentence` and `contract_file` are retired and fail (the old `category` value now lives in `type`).
- `Input_Bundle_QC/judge_qc.py:115`: `RETIRED_ANNOTATIONS = ["category", "kind", ...]`.
- JD-15 (`04_Judge_QC.md:92`) has already been updated to use `type`. Only IN-15 is stale.

**Question:** should IN-15 say "every criterion whose `type` is `constraint`"?

---

## 3. district-heat: two rule readings (JD-15 step 2 and TS-20)

**In short:** a separate re-check of my district-heat QC report could not decide two findings either way. The answer depends on how the PL reads the rule, and that reading applies to every bundle.

**Who it affects:** found on my bundle `district-heat-flex-procurement` (not on the remote). The rule readings apply to everyone.

**3a. JD-15 step 2: is "restate the objective before coding" a valid judge criterion?**
- My criterion R4 (weight 3):
  > The agent states the five objective components and the final tie rule in its own words before coding the optimiser.
- The rule (`04_Judge_QC.md:92`): a conduct criterion must be "odds-raising" (e.g. "inspects the shipped data before writing the decoder"). A mere "preference" (e.g. "writes intermediate results to a scratch file") must be removed.
- Why it is unclear: a competent agent can code straight from the spec, so step 1 fails. Restating looks like a preference, but it also helps get the component order right, which no test grades separately.

**Question:** is restating the objective in prose before coding odds-raising, or a preference?

**3b. TS-20: can an edge-case-looking check have weight 5?**
- My check `unknown_region_site_row_report_case` has weight 5. It grades only the site count and labels on a 2-site extract. The full segment-file comparison `ordinary_extract_segment_files_match` has weight 3.
- The rule (`03_Tests_QC.md:51`): 5 = core outcome, 3 = important sub-goal or edge case. Mild imbalance is a minor.
- Why it is unclear: the instruction gives no ordering between the two, and my TRUTH marks rejected rows as "focal", which argues for 5.

**Question:** is the unknown-region report check part of the focal rejected-rows outcome (weight 5), or an edge case that should not outweigh the full segment-file comparison?

---

## 4. vendor-archive and schema-migration: two more rule readings (JD-13, JD-5 vs JD-18)

**In short:** as with item 3, a separate re-check could not decide these, and the answers apply to every bundle's judge file.

**Who it affects:** found on my bundles `vendor-archive-roundtrip-recovery` and `schema-migration-plan-repair` (not on the remote). The rule readings apply to everyone.

**4a. JD-13: is one closing-reply sentence worth weight 5?** (vendor-archive)
- My criteria R3, R5 and R7 each have weight 5 (`critically_important`). Each pays for one sentence in the final reply that restates a key rule (stream state, precedence, delta length). The code-quality criterion R10 has weight 3.
- The instruction (`instruction.md:13`) asks only for "a short plain account of the format you recovered".
- The rule (`04_Judge_QC.md:90`): 5 = core outcome; "a formatting nicety weighted 5" is a fail. These sentences are not formatting niceties, but they are a small part of the deliverable. `judge_qc.py` J13 passes.

**Question:** is a single closing-reply sentence that restates a key rule a "core outcome" worth 5, or should it be 3?

**4b. JD-5 vs JD-18: must one code-quality criterion be split?** (schema-migration)
- My criterion R14:
  > The agent's changes under src/migrakit read as reviewable Python: descriptive names, errors raised with their catalogue code, and no debug prints or dead code left behind.
- JD-5 (`04_Judge_QC.md:71`): "If a judge would need to check two separate things, split it."
- JD-18 (`04_Judge_QC.md:99`) defines the single code-quality criterion by several parts ("no bare `except`, errors handled ..., names that say what the thing is, no dead or duplicated blocks, no debug residue").

**Question:** does JD-5 require splitting a code-quality criterion whose parts are the ones JD-18 itself lists? Or is one overall "reviewable code" verdict allowed?

---

## 5. Generator and QC: three bugs or unclear points

**Who it affects:** everyone who uses the generator or this QC. All three are still present at `bfe40804` (checked 22 Oct, 12:40 IST).

**5a. Generated build-repair instructions have blank words.**
- **In short:** for every archetype except format-recovery, the generator sets two text fields to empty. The build-repair instruction template uses both, so the generated sentence has holes in it.
- **Evidence:**
  - `Input Bundle Generator New/generate_bundle.py:1856-1857`: `args.container_noun = ""`, `args.producer_system = ""`.
  - `templates/build-repair/instruction.md:1`: "...meant to summarize {{CONTAINER_NOUN}} manifests from a {{PRODUCER_SYSTEM}}." This renders as "meant to summarize  manifests from a ."
  - The same two fields go into `templates/service-interaction/environment/data/seed_config.json:3-4`.
- **Question:** should non-format-recovery archetypes get real values for these two fields, or should the templates stop using them?

**5b. How many oracle runs are required?**
- **In short:** QC Step 10 requires 5 oracle runs, every one exactly 1.000. Each run takes a few minutes, so this is expensive while a task is still being built.
- **Evidence:** `Input_Bundle_QC/Final_checklist.md:273` ("five oracle runs, one nop run, one stub run") and `:383` ("Every one of the five oracle runs must read exactly `1.000`").
- **Question:** is 5 the only accepted number for submission? Is it fine to use fewer runs (e.g. 2) while building, and run the full 5 only at final QC?

**5c. `CATEGORIES.md` lists only 2 of the 8 archetypes.**
- **In short:** the doc says there are only two task types, but the generator ships eight. A new author reading the doc would not know the other six exist.
- **Evidence:**
  - `Input Bundle Generator New/CATEGORIES.md:34-35`: "The current archetypes are `format-recovery` and `build-repair`".
  - `templates/` has 8 folders, all named in `generate_bundle.py`: `build-repair`, `cli-config`, `data-pipeline`, `domain-calculation`, `format-recovery`, `performance`, `repo-patch`, `service-interaction`.
  - `ARCHETYPE_SELECTION.md` (e.g. :16-19) already describes the newer ones.
- **Question:** can `CATEGORIES.md` be updated to list all eight, or point to `ARCHETYPE_SELECTION.md`?

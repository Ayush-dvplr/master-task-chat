S7 KIT WATCH (W1-032, draft, 3 Nov 2026)

Goal. Ayush's PL changes the QC kit (Terminal_2.0_Harbor_Harness, folder Input_Bundle_QC) often. The master must notice every change, show exactly what changed and which of our fixes it touches, have an agent classify it (Q86: LENIENT, MINOR, MAJOR), report it, and wait for Ayush. The master never decides a MAJOR change, and nobody edits the kit or the snapshot.

Classes (Q86, as agreed)
LENIENT: QC only gets easier (a check removed, a threshold relaxed, a fail turned into a warn). Act freely: templates and the fix map may drop the now needless work after the report.
MINOR: stricter or reworded, with no effect on how fixes map to checks or on how traps stay hidden. Report; template wording may follow after the report.
MAJOR: affects fix mapping (a FIX_MAP.md row's fix or wording no longer passes, or a check needs a new row whose fix touches the agent visible files, tests or hidden data), hiding (IN-17, DS-21, AL-1, IN-15, IN-16 and anything that decides what may be withheld) or traps. Goes to Ayush before any template, rule or fix map change.


1. HOW IT WORKS

Step 1, notice (cheap, every card). state_card.py kit_line already hashes the live kit against knowledge/fingerprints/qc.json and prints "QC KIT: unchanged ..." or "QC KIT: CHANGED (files)". No change here.

Step 2, measure (on CHANGED). The master runs
  python3 tools/kit_watch.py check --kit "<Terminal_2.0_Harbor_Harness>/Input_Bundle_QC" --snapshot knowledge/fingerprints/qc.json --fixmap knowledge/FIX_MAP.md --rules knowledge/BUILD_RULES.md knowledge/RULES_IN_FORCE.md --out master_chat_work/<YYYYMMDD>_kit/
It prints per file UNCHANGED, CHANGED, NEW or MISSING with old and new sha, a word level summary of each changed line, the changed check ids (the id that owns each changed line, found by the nearest line above that starts with an id such as DS-22, TS-23, F0a or A3), and per id the FIX_MAP.md rows that cite it and whether BUILD_RULES.md names it. It writes kit_watch.json and one unified diff per file under --out. Ids only named inside a changed paragraph (not changed themselves) are listed apart so they do not flood the table. Exit code 0 unchanged, 1 changed.

Step 3, classify. The master issues one read only session from KIT_CLASSIFY_PROMPT.md with the kit_watch output, the changed ids and the FIX_MAP rows that cite them. It returns the table id | change | class | reason | fix map rows affected, and proposes (never applies) template and rule edits.

Step 4, report. The master verifies the table against the diffs on disk (R1), writes it to master_chat_work/<YYYYMMDD>_kit/KIT_CLASSES.md and puts one open item on the state card. LENIENT rows may be acted on after the report; MINOR rows after the report with the proposed wording; MAJOR rows wait for Ayush's word, which goes word for word to decisions.jsonl.

Step 5, new snapshot (only on Ayush's word). After Ayush says the change is taken in:
  python3 tools/kit_watch.py save --kit "<kit>" --dest knowledge/fingerprints/qc_<head8>/ --head <kit git head> --by "<Ayush's exact words>"
It writes qc.json (same shape as today plus "text_dir" and "saved_on_word") and qc_text/ with a verbatim copy of every kit file. It refuses an existing destination, an empty --by, and a destination inside the kit. The master then moves the old knowledge/fingerprints/qc.json into archive_<old head8>/ (as today) and copies the new qc.json in its place. kit_watch.py never does that move itself and never edits the kit or an existing snapshot.

Why a text copy. Today's snapshot (25 Oct, head 5574d77e) stores hashes only. kit_watch can then say which files changed but not what changed or which checks. With qc_text/ beside each snapshot, the next change gives a real diff and the check ids. The copy is about 390 KB per snapshot (12 files, measured on 57c22748) and changes only when Ayush approves a snapshot.


2. HOW IT JOINS THE STATE CARD

kit_line stays the fast hash test. Two additions, both read only:
(a) when the snapshot has text_dir, kit_line calls the same comparison and prints the ids count: "QC KIT: CHANGED 2 files (05_Alignment_Integrity_QC.md, Final_checklist.md); 6 check ids, 3 in the fix map. An agent classifies LENIENT, MINOR or MAJOR (S7); Ayush decides." (kit_watch.py card prints exactly this line);
(b) when master_chat_work/<date>_kit/KIT_CLASSES.md exists for the current live hashes, the line shows the classes instead: "QC KIT: CHANGED, classified 1 MAJOR (IN-17) waiting for Ayush, 1 MINOR, 2 LENIENT."
Sketch for state_card.py (stdlib; kit_watch.py importable from tools/):

    def kit_line(R):
        fp = load_json(os.path.join(R, "knowledge", "fingerprints", "qc.json"), None)
        ...  # unchanged hash test as today; on CHANGED:
        cls = latest_classes(R, live_hashes)          # KIT_CLASSES.md rows for these hashes, or None
        if cls:
            major = [r["id"] for r in cls if r["class"] == "MAJOR"]
            return (f"QC KIT: CHANGED, classified {len(major)} MAJOR ({', '.join(major)[:40]}) waiting for Ayush, "
                    f"{sum(r['class'] == 'MINOR' for r in cls)} MINOR, {sum(r['class'] == 'LENIENT' for r in cls)} LENIENT")
        if fp.get("text_dir"):
            return kit_watch.card(src, fp, fixmap)   # ids and fix map count
        return "QC KIT: CHANGED (...). No text copy: run kit_watch.py check; an agent classifies (S7); Ayush decides."

The same line goes into every prompt the master issues while the kit is changed (the template line "QC KIT: <line>"), which replaces _COMMON_RULES_v5 Always 1 "stop on any difference" (P10_TEMPLATES.md row _COMMON_RULES_v5:33). P10_upstream_diff_v2 becomes the kit watch session template (rows P10_v2:9, :18, :22, :24) or is replaced by KIT_CLASSIFY_PROMPT.md for the QC half.


3. TEST (full output in KIT_WATCH_TEST.txt)

Kit history in this repo. git log origin/main -- Input_Bundle_QC prints one commit only: 57c22748 "Latest imput Bundle QC" (3 Nov 03:30). b9831951 and 10d3e3ff have no kit; 47d75d76 to 00d358c4 carry the same 12 files byte for byte. So two real commits can only show the unchanged path. I therefore ran:
T1 the real snapshot (knowledge/fingerprints/qc.json, 25 Oct, head 5574d77e, hashes only) against the kit at 57c22748: 2 files CHANGED, 05_Alignment_Integrity_QC.md (5e81d67c to c3860c07) and Final_checklist.md (aff7b002 to 99a8b460); no text copy, so no diff and "ids unknown for 2 files". This is real: the state card would print QC KIT: CHANGED today (if Ayush's live kit equals origin/main), and FIX_MAP.md (W1-030) already cites kit lines at 00d358c4, newer than the snapshot. The archived fingerprints (archive_9b8229f6 to archive_3fb1650b, 21 to 22 Oct) show these same two files changing most often.
T2 save a snapshot of 57c22748 (test folder), check the kit at 00d358c4 against it: all 12 UNCHANGED, exit 0. Save refuses an existing destination and an empty --by (exit 1 each).
T3 a SYNTHETIC kit (57c22748 plus five labelled edits) against that snapshot: 6 files reported (5 CHANGED, 1 NEW), 6 changed ids, 3 of them in the fix map (DS-22 row 1, TS-23 row 2, IN-17 cited in THE LINE), word level summary correct for every edit, 8 ids listed apart as only named in the changed IN-17 paragraph. BUILD_RULES.md and RULES_IN_FORCE.md name no kit check ids, so that column is "no" for every id today (it becomes useful if BUILD_RULES ever cites a kit id).
T4 card lines for T1 and T3. T5 the kit folders' tree hashes and git status of knowledge/fingerprints are unchanged after all runs.

How the classifier would label the T3 edits (worked example for KIT_CLASSIFY_PROMPT.md; synthetic):
TS-23 | warn above 35 checks became warn above 40 | LENIENT | a warn moved further away; FIX_MAP row 2 (record the warn) still passes | 2
A3 (tests_qc.py) | same threshold in the script | LENIENT | script side of TS-23 | 2
DS-22 | adds "a sha256 line that does not match its file is a fail, not a minor" | MINOR | stricter, but FIX_MAP row 1 already regenerates digests by script as the last edit, so the fix still meets it | 1
IN-17 | "Withholding is the default" became "allowed only where the instruction names the withheld case" | MAJOR | changes what may stay hidden; THE LINE in FIX_MAP and every hidden branch fix rest on the old sentence | THE LINE, 14, 19, 33, 35
AL-29 (new) | TRUTH.md must state the seed range of every hidden generator | MINOR | new check, fix touches TRUTH.md only (author side), no hidden data or trap change | none, new row needed
EX-1 (new file) | every bundle ships solution/CHANGELOG.md | MINOR | author side file only; note DS-27 tension for Ayush | none, new row needed


Open points for Ayush
1 The kit in this repo (57c22748) differs from the 25 Oct snapshot in two files and there is no text copy of the old ones. Take a new snapshot with text at 57c22748 (kit_watch.py save, on your word) so the next PL change gives a diff? If your Mac kit differs from origin/main, the snapshot should come from the Mac kit.
2 Where should snapshots live: knowledge/fingerprints/qc_<head8>/ (proposed, qc.json pointing at it), or text copies inside the existing archive_<head8>/ folders?
3 LENIENT "act freely": may the master update templates and the fix map for a LENIENT row right after the report, or only list it?
4 A new check id with no fix map row: MINOR when its fix touches only author side files (TRUTH.md, task.toml, metadata), MAJOR otherwise (the rule in KIT_CLASSIFY_PROMPT.md). Agree?

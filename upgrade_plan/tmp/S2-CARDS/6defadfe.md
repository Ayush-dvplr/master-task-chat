TASK: 6defadfe-9c50-5aa1-b854-8d5c1718d794, Software Engineering / Data Processing (repair a broken Python CI ledger package for Python 3.12, apply spec, errata and governance rules across 25 feed formats, write a 6-file stage ledger that chains into a hidden stage 2), Opus tests 28.57, rubric 54.72, final 41.64.

1. VERDICT: MIXED, confidence medium. DESIGN for about 75 percent of lost test weight (30 of 40) and a possible DEFECT for about 25 percent (10 of 40). Notably, the agent passed both exact ledgers, stage 1 and the hidden renamed stage 2 (10 points). Every loss is a hardened package contract tested by unit probes against internal functions: SemVer build metadata, the minimum commit prefix length, index path confinement, and rejection of record-count mismatches.

2. LOSSES:
1. SemVer build metadata, 3 checks, weight 9 (release precedence, prerelease precedence, exact constraint). Cause: CRASH. deps.parse_version splits only on "-", so "1.2.3+linux.0" fails int(). The prerelease range probe passed.
2. Commit prefix minimum of 9 hex digits, 2 checks, weight 6 (current, rewritten). Cause: WRONG output, an 8-digit prefix resolves. The rewritten probe would also fail on the agent's new attribute rewritten_shas, which the probe does not set.
3. Index path confinement, 3 checks, weight 15 (parent traversal, absolute, symlink). Cause: WRONG output, Feed reads self.dir / path with no check.
4. Record-count enforcement, 2 checks, weight 10 (per-file declared vs parsed, index declared vs actual). Cause: WRONG output, the mismatch is recorded in selftest and no FeedError is raised.
5. Passed: archive layout, install, shipped tests, both exact ledgers (16 of 56).

3. DIFFICULTY KIND: SemVer metadata, (a) variation inside a documented standard. Commit prefix, (b) a documented case the visible data never triggers. Path confinement, (e) a security hardening that follows from a stated read scope, with no feed escaping in the visible data.

4. EVIDENCE:
1. SemVer: ci_ledger_spec_revC.docx 9.4 says "Versions order by semver 2.0 precedence" (SemVer 2.0 ignores build metadata).
2. Prefix: revC 3.1 says "Commit references are case-insensitive hexadecimal prefixes of at least 9 digits (4.3)".
3. Confinement: revC 2.1 says paths are "relative to the feed directory", and instruction.md:7 says "read only the feed and the resume state it is given". Raising FeedError is not stated.
4. Possible DEFECT, counts: revC 2.3 says only that "A reader that does not reproduce the declared count for a file has misread it". revC 10.6 ships declared and read as separate selftest fields, and instruction.md:12 asks which checks "still disagree with the ledger", which reads as report, not abort. tests/test_output.py:770-790 and 835-858 require a FeedError.
5. Probe fragility: the probes monkeypatch package internals (readers.read, Feed._load_registers, Feed.__new__ with only shas and rewritten) that no shipped document names.

5. TEST DESIGN: a fixed stage-1 ledger and a hidden stage-2 feed with fresh, extensionless names, each paid once only when all six files are exact (whole document, run control stamp included). Behaviour contracts are 4 generated cases per property, run as Python probes against package internals under a dropped uid. Amplification: none across contracts, since each property pays once. Negatives: hardcoded answers, nondeterminism.

6. INSTRUCTION: "Each output is accepted only as an exact match of the specified content, every row and every field"; "find files through the feed index and their control blocks, never by file name, read only the feed and the resume state it is given"; Python 3.12 with only PyYAML, pyarrow and pypdf; 7200 seconds; the final message reports repairs and control checks. Not said: that the package is graded on adversarial inputs beyond the two stage feeds, that count or path violations must abort with an error, or that internal function names are a graded API.

7. RUBRIC: lost R7 (renamed-feed rerun), R19 (toolchain-pin check on one frame), R23 (source audit for feed names) and R24 to R28 (directly exercising each hidden contract). The rubric pays for exactly the adversarial self-testing the agent skipped.

8. REUSABLE IDEA: after the main exact-output task, grade a few hardening contracts that the spec states in one clause each but the visible data never exercises (a standard's edge rule, a minimum length, a read scope). Pay each property once over several fresh generated cases, and pair it with a rubric item for exercising it. Lesson: state the failure mode (raise a named error versus report) for each contract, and probe only through a documented API.

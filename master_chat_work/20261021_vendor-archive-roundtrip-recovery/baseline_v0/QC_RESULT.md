# vendor-archive v0 QC (kit bde868c4, 20:47-23:45 IST). Copy: ./qc_report_v1.md
Verdict FAIL: 26 fails, 10 minors, 4 warns (many share one root cause). Scripts 0 FAIL.
Step 10 FAIL: oracle 0.1241 x5 (18/145), nop 0.0, stub 0.0207. Cause = setpriv/nobody over 0600 temp inputs (same bug as the v0 trajectory).
Root causes: (1) verifier permissions; (2) judge R1-R9 copy spec facts, forgery ~0.50 total, overlap with tests (JD-8), weight-5 summary sentences (JD-13); (3) report_roundtrip never runs encode.py; (4) solve.py restates the verifier codec (DS-24); (5) encode fixtures are not decode documents (value null); (6) name-prefix check bans allowed names; (7) negatives: source grep /app/data, duplicate determinism pair, rebinds check; (8) untriggered rules (reset, byte 15, rec_count bound, crc expected/found); (9) unknown long-key decode rule lives only in the tests; (10) TRUTH counts/seed wording wrong.
Minors: hyphens, escape rule wording, compound checks, loose ==, verifier timeout 49x60 s > 2700 s, generator tooling left in tests.
Not yet rechecked (P8).

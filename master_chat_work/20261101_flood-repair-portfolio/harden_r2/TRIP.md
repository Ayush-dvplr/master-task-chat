# TRIP cb8dada flood-repair-portfolio harden r2

Sections 1-3 (program map, reference map, judge trip) reused by reference from c3aca8d:
`master_chat_work/20261031_flood-repair-portfolio/harden_a1/TRIP.md`. a1: tests 108/108, rubric 4/30, final 56.66.
Step numbers below are trajectory step_id values (`gate_run_a1/trajectory/claude-opus-5/Run 1/agent/trajectory.json`, 76 steps).

## R3 items not covered by c3aca8d

1. Files never opened. Every data file was listed (3) and head-read (5); contract.md read whole (4). No file was
   skipped. What the agent never looked at is a book other than the shipped one: no generated book, no second
   book with many large rounds. Its only extra inputs were hand-made: tiny book (49-51), copy with two files
   removed (48), random graphs (39, 62, 64-66).
2. Shipped-fitted literals. No round id, proposal id or answer literal in the program (grep of
   `h1_a1/a1_program/derive_report.py`: only `DIGITS`, `is_count(...,1,60)` from contract.md, `FILL_CANDIDATES = 16`
   at 318, `setrecursionlimit(20000)` at 709). The fit to the shipped book is in speed, not in literals: the solver
   was tuned on the shipped book's two large rounds R57468 (160 nodes, 394 edges) and R79260 (150, 366)
   (16, 22, 26, 33, 57, 67) until the whole book took 2.2-3.3 s (55, 61, 70). The 20 s limit (contract.md:15) was
   met only for a book with 2 large rounds.
3. Where checking stopped.
   - Speed: timed only the shipped book (12, 31, 37, 55, 61, 70). The first program hung on it (12-13, C-c).
     Scale tests used single random graphs (64 `hard.py` n=160 m=400-1300; 65 output was "1" after 120 s, killed
     at 66; 66 `hard2.py` structured; 68 width). No run of a book with more large rounds than the shipped one,
     although contract.md:11-12 allows up to 200 rounds of up to 160 rows each.
   - Correctness: brute-force compare on shipped components (38, 63), random small graphs 4000 trials (39, 62).
     All passed; fuzz of 150 generated books by c3aca8d matched 150/150 (no WRONG left to grade).
   - Judge (c3aca8d TRIP 3): recompute checks skipped, timing claim based on the shipped book only.
4. Lost points by kind (a1 on attempt-1 tests): none lost. The new hidden check sits at item 3 speed: hidden books
   with many large rounds inside the stated caps, where the agent never measured.

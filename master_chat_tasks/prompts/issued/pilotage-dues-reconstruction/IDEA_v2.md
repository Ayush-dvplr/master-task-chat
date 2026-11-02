# pilotage-dues-reconstruction: IDEA v2 (redesign, 31 Oct 2026 12:10 IST, Ayush option a)

Base: the parked v1 world (IDEA.md, WORK `master_chat_work/bundles/_work/pilotage-dues-reconstruction/`). v1 was parked because the two design-blind reads were exact 9/9 (DESIGN_BLIND.md): the circular lists the whole 5x4x3x4 = 180 candidate space and every quiet reading, so a blind enumerates and transliterates.

Why this world now: scan e54f96a (`master_chat_work/20261031_parked_scan/SCAN.md` section 2) rates it L-CONV FITS. Paid invoices per station already form an observation channel. The fit loop, per-seed fit-count asserts, a 4x-linear generator (1.44 s) and reference (1.38 s) all exist.

## Lever (L-CONV, the warrant pattern)
Each station applies its own billing conventions. Only that station's own paid invoices reveal them. Candidate convention families are the quiet rules in EVIDENCE_MAP.md:
- assist charged per started vs per full 30 min (tariff_circular.md:36)
- draft_m rounded up vs half vs truncated (:17-19)
- Sunday holiday shifted to Monday vs Sunday only (:46-47)
- surcharge base with vs without assist (:37-38)
- night window bounds (:37-38)

The docs state the principle in one place: "station billing conventions differ; recover each station's conventions from its paid invoices; exactly one reading fits each station". They do not list the readings per station.

## Gate notes (override the template where they differ)
- G-1 Determinacy: for every station in every corpus, exactly 1 convention combination reproduces all of its paid invoices to the cent. The generator asserts this, and it plants invoices that contradict every rival reading (warrant observe() / UNIQUE_FIT.md pattern). This is a determinate EVIDENCE_MAP fact, not a hidden rule (LEVER_RULES 0b).
- G-2 Warrant hole (harden_a1/DESIGN.md:65-78): a careful wide search over a listed space recovers it all. So the docs must not enumerate the per-station readings. QC_DEFENCE.md must still show how a careful agent could find each family from the invoices alone (IN-15, IN-16), with no guessing needed.
- G-3 Shape D: one-convention-everywhere is exact on shipped. The hidden w5 tier (N2, >= 50% of positive test weight) plants combinations that shipped never shows, each graded per station and per corpus.
- G-4 Kill table (Docker, capped): at least (1) one convention everywhere, (2) first fit, (3) shipped readings carried to hidden, (4) a careful wide search over the natural domain space (P6o style), (5) the old v1 blind program (copy in design_blind or proto). Rows 1-3 must lose the lever by WRONG. Row 4 must still lose >= 15% of lever points, otherwise NO CORE. The template's two optimization solver rows (split-into-parts exact, strongest plain exact) do not apply to a fit task: write "N/A (fit task, no optimisation)" in the table.
- G-5 DESIGN READY bar (v3.7): predicted final <= 35; lever share >= 40%; every kill/blind row <= 65 tests, none > 70; lost lever points by WRONG (crash/timeout <= 30%); reference slowest corpus well under any stated limit; verifier worst 900-1,200 s (never > 2,430 s).
- G-6 Stop at DESIGN READY. The master reviews and asks Ayush before the build. At DESIGN BLIND READY the master issues one P13 design blind, which must lose >= 40% of lever points.
- G-7 Reuse proto/ (gen, solve, compare, score, xcheck), EVIDENCE_MAP, UNIQUENESS. Back up the old WORK design files to WORK/v1_design_backup/ before editing them.
- G-8 Little Docker: dockfree before every container; scratch under `_runs/20261031/pilotage-dues-reconstruction/`.

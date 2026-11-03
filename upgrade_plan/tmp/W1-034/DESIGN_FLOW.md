NEW TASK DESIGN FLOW (W1-034, 3 Nov 2026; template section draft, not applied)

Why: WHY_NEW_FAILS.md finds five causes. 1 NO CORE at design (8 designs, 13 rounds), 2 LEAK after build (10 tasks), 3 weak lever chosen knowingly and no idea queue (9 events), 4 QC FAIL or a lever that needs an unwritten fact (7), 5 time (6). Each step below names the cause it answers. Rules come from BUILD_RULES.md; nothing here changes them. Settings are read from settings.json (gate, design_margin, no_core_keep_pct, card.unique_last).

A. IDEA INTAKE (answers causes 3 and 1)
1. Start from a domain and a data shape, not from a lever. The data shape is what the shipped files look like (a container format, a ledger with carried quantities, an event log with clocks, a long procedural document, a repository). Write both in one line each.
2. Pick the primary lever family by rotation:
   a. Take the families and domains of Ayush's last card.unique_last (3) design cards plus every build in the last 7 days (registry plus the card log master_chat_tasks/registry/design_cards.jsonl, one line per card: slug, family, domain, date).
   b. Drop any family used as primary in those cards; drop any domain used in those cards.
   c. Of the remaining families, rank by teammate evidence in PATTERNS.md and CONFIRM.md: confirmed families first (D2 carrier variation, D1 branch only hidden data fires, D8 carried state), then D5 and D6, then D3 under CR7, then D4 only as an extra (CR1). D7 is never a family.
   d. Take the first family whose recipe fits the data shape; if none fits, change the data shape, not the family order.
   Today this gives: avoid D3 and D4 and the optimization, scheduling, billing and settlement domains (WHY_NEW_FAILS.md section 3); start from D2 or D1 or D8 in another domain from INDEX.csv (data processing, scientific computing, security, debugging, machine learning).
3. Ideas come from a queue, never from an empty start: registry/ideas.jsonl rows with status "new" or "kept part" (RESEARCH_INTAKE.md), the research prompt answers, and parts kept from failed cards (step D). When the queue holds fewer than 3 usable ideas, issue a research prompt of kind discover (research_prompt.py) before the queue is empty, not after a park.

B. ONE PAGE DESIGN CARD (answers causes 1, 2 and 4)
Fill DESIGN_CARD_TEMPLATE.md. Fields: domain; deliverable; shipped data and hidden data plan; primary lever family and the deciding sentence (quoted as it will appear in the docs, with file name); extras; predicted loss per lever (points of positive test weight); the careful exact program's likely path (what it reads, what it writes in its first pass, what it tests against, where it goes wrong, or why it would not); solvability check of every graded value; closest teammate task id and why it is not a copy. The card is at most one page; it is written before any file is built and before any design session is spent.

C. DESIGN CHECKS BEFORE BUILD (answers causes 1, 2, 4 and 5)
1. DESIGN READY (BUILD_RULES): primary lever from the card's family, at least 40 percent of positive test weight, firing in most hidden inputs with varied count and shape, lost by the careful exact program; predicted final under gate.final minus design_margin (under 35 today). The prediction must name the oracle branch, the careful program branch and a saved input where they differ (T10).
2. Careful program test on paper, then on a prototype: the card's "likely path" is checked by a small kill table (a literal reader, a careful enumerator, a component splitting exact solver). If the careful row keeps no_core_keep_pct (60) or more of the primary lever, the card is NO CORE: report to Ayush and go to step D. This is the cheap stop that the 13 lost rounds lacked: it runs before a design blind and before any build.
3. Solvability check: one row per graded value. Each row names the sentence (file and line in the draft docs) or the shipped fact that decides it; a carrier variant names the standard sentence that allows it; nothing graded rests on an unwritten form, constant, tie break or a situation the instruction calls unsettled (BUILD_RULES HIDING and GRADING; the depot DS-21 and match-replay cases). A row without a deciding sentence fails the card.
4. Uniqueness check: not a copy of any of Ayush's tasks (compare domain, data shape, deliverable and lever against the registry); not a close copy of one teammate task (the closest id from INDEX.csv and the S2 cards, with at least two of domain, data shape, deliverable and deciding mechanism different, and no copied text, data or code). The card states the closest id and the differences.
5. Time box: one design session per card; the card plus the kill table must be done before the session's output budget runs low (hangar D:666). A card that needs a second session is written in pieces to WORK.

D. REUSE OF A FAILED DESIGN (answers causes 3 and 5)
1. When a card fails (NO CORE, solvability, uniqueness), keep its parts: domain, data shape, generator, deliverable, docs skeleton, oracle core, kill table. Mark each part "kept" in the card's history block.
2. Switch the primary family to the next one in the rotation that fits the kept data shape (for example D3 to D2 by moving the hard part into a named container standard the shipped data uses only plainly; D4 to D1 by adding a documented state change the shipped run never shows; unique fit to D8 by making the fitted value a carried quantity).
3. A card may switch family twice. After the second failure it goes to Ayush with the two kill tables; nothing is parked on its own (BUILD_RULES NO CORE).
4. Every failed card writes one line to registry/ideas.jsonl (status "kept part", what failed, which part is reusable), so the next intake starts from it and the next research prompt lists it under what was tried.

The flow in 8 lines
1. Choose domain and data shape first.
2. Choose the primary family by rotation away from the last 3 cards' families and domains, ranked by teammate evidence.
3. Draw ideas from the queue; refill it by a discover research prompt before it empties.
4. Write the one page card, with the deciding sentence quoted.
5. Predict per lever loss and the careful program's path; run the kill table on a prototype.
6. Check solvability of every graded value and uniqueness against own and teammate tasks.
7. DESIGN READY only with a predicted final under 35 and the careful row losing over 40 percent of the lever.
8. On failure keep the parts, switch family (at most twice), log the parts, then ask Ayush.

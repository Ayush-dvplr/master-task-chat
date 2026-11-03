DESIGN CARD (fill in; one page; written before any build file. Fill tokens are [[...]]; replace every one or write "none" with the reason.)

Card id: [[SLUG]] card [[N]]   Date: [[DATE IST]]   Author session: [[SHA]]
History: [[first card | switched from family X after NO CORE on card N, parts kept: ...]]

1. DOMAIN
Domain: [[domain, one line]]
Who needs the exact answer and why: [[one line]]
Rotation record: last [[3]] cards used families [[...]] and domains [[...]]; this card uses family [[Dn]] and domain [[...]], neither in that list.

2. DELIVERABLE
[[the program and the output documents, with paths; the exact command the tests run (T14)]]

3. DATA
Shipped data: [[files, formats, rough sizes; which cases they show]]
Hidden data plan: [[generator recipe; number of held out inputs; which axes vary; the share of hidden inputs where the primary lever fires (most of them) and how its count, direction and position vary]]
What the shipped data never shows: [[the primary branch or form; confirm it fires 0 times in the shipped run]]

4. PRIMARY LEVER
Family: [[D1 | D2 | D3 under CR7 | D5 | D6 | D8 | D9]] (from PATTERNS.md; D4 only as an extra; D7 never)
Deciding sentence, quoted as it will ship: "[[sentence]]" in [[file name]]
Why one sentence decides every graded value it touches: [[one line]]
Share of positive test weight: [[percent, at least 40]]

5. EXTRAS
[[lever | family | deciding sentence file | share of weight]] (one line each, or none)

6. PREDICTED LOSS PER LEVER
[[lever | points the careful program loses | of points | WRONG / TIMEOUT / CRASH]]
Predicted tests: [[x]]   Predicted rubric: [[y]]   Predicted final: [[(x+y)/2]], must be under gate.final minus design_margin ([[35]])

7. THE CAREFUL EXACT PROGRAM'S LIKELY PATH
Reads: [[files in order]]
Writes first: [[the program shape it writes in its first pass]]
Tests against: [[the shipped run, its own small examples, invariants]]
Where it goes wrong on hidden data: [[oracle branch]] versus [[careful branch]], saved input [[path or plan]]
Why its self test on the shipped data stays green: [[one line]]
Kill table rows planned: literal reader, careful enumerator, component splitting exact solver, [[others]]

8. SOLVABILITY CHECK (one row per graded value or value family)
[[graded value | deciding sentence or shipped fact (file:line) | carrier variant legal under (standard sentence) or n/a | OK or FAIL]]
Any row without a deciding sentence: [[none, or the fix]]
Nothing in environment/ shows a graded answer: [[confirmed]]

9. UNIQUENESS
Closest own task: [[slug]]; differs in [[domain / data shape / deliverable / mechanism]]
Closest teammate task id: [[id from INDEX.csv or S2 cards]]; its family [[Dn]]
Why it is not a copy: [[at least two of domain, data shape, deliverable and deciding mechanism differ; no text, data or code copied]]

10. DESIGN CHECKS (filled after the prototype kill table)
DESIGN READY items: lever share [[ ]] | fires in hidden [[ ]] of [[ ]] | predicted final [[ ]] under [[35]] | oracle versus careful branch named [[yes]]
Careful row keeps [[ ]] percent of the primary lever (NO CORE at [[60]] or more)
Solvability rows OK: [[n of n]]   Uniqueness: [[OK]]
Verdict: [[DESIGN READY | NO CORE | FAIL solvability | FAIL uniqueness]]

11. IF FAILED: PARTS KEPT
[[domain, data shape, generator, deliverable, docs skeleton, oracle core, kill table: kept or dropped]]
Next family in rotation: [[Dn]]; family switches used [[0, 1 or 2]] of 2
ideas.jsonl line written: [[yes, id]]

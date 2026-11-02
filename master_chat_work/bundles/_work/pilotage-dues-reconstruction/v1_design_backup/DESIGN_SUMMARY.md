# DESIGN_SUMMARY v2 44635de pilotage-dues-reconstruction (domain-calculation, data-science, Shape D)
Why v2: blind program exact on shipped and seeds 1101-1106 (DESIGN_BLIND.md). Story unchanged: four stations lost their tariff tables; the circular fixes the due formula (tonnage,
draft, towage lines plus one night/holiday surcharge, each line half-even) and closed lists (180 combos);
paid invoices (CSV, JSONL, fixed width, XML) recover the tariffs; a disputed batch gets verdicts. 14 files
(adds certificates.json), 8 formats, ~38k lines. COUPLING (circular Verdicts) unchanged. Invocation and
10 outputs unchanged. Seed 482617.

Sharp levers (each 0 on shipped, >= 2 per hidden corpus; roles X/Y/Z/W shuffled per seed):
- LV-1 R-FIT v2 (S3, joint space): "A station's tariff gives each coefficient one listed value in each
  of its periods, and reproduces every accepted paid invoice of the station, each with the values of its
  own period, to the cent." Verdict clause kept word for word, once, in Verdicts. Hidden: Y1 3+ fits
  alone / 1 joint; Y2 3+ joint; Z 2 fits (no notice); W 1 alone per period / 0 joint. Generator asserts
  >= 2 disputed rows per multi-fit period differing under first fit. Off-list no-fit plant dropped.
- LV-2 R-CHANGE v2 (S2, keyed in station_notices.md): rows `| station | notice_date | coefficients |`;
  "A notice starts a new period at 00:00 on its notice date and gives new values only to the coefficients
  its row names." Directive "every date rule reads the boarding instant" deleted (definitions stay).
  Shipped: North notice names all four (per-period = joint). Hidden: X names two (control, carries
  notice-day / eve / invoiced-after plants); Y, W name 1-3. Wrong period reading: X joint 0 (amplified).
- LV-3 R-EXEMPT v2 (S8 midnight + H6 allowance, own RNG): certificates.json {id: holder, expiry,
  allowance_minutes}; register column `certificate`. "A certificate covers on-board time of the vessels
  registered under it, before 00:00 on its expiry date, up to its allowance_minutes in total. Visits draw
  on the allowance in the order of their instants, the lower visit id first on a tie." Visit = defined
  term, so uninvoiced and other-station visits draw. Shipped: one vessel per certificate, cap never hit.
  Hidden: shared certificates, cap hit mid-visit, wholly-before visit billed full, uninvoiced draws,
  midnight splits. Paid public invoices priced by the stated reading (wrong reading breaks the fit).
  SCOPE FLAG: the allowance extends S8 with an H6 stateful key; master decision needed.
22 plain rules unchanged (rejections, fatal inputs incl. certificates.json, night/holiday, half-even).

Tests unchanged: 31 checks, positive 87, hidden + mutation 77 (88.5%), whole docs exact (FC:491),
per-row ownership, mutations counted only if H1 plain exact, negatives /tests -5, shipped answers -3.
Judge unchanged in shape (16): P7 now per-period and joint counts at a notice station, P8 one
certificate's draws in instant order; probes 27/39 = 69%; J4, J6a, J6b, J10 x2, J3a/b/c.
Estimates: each lever alone 73/87 (84%) of tests; first-fit loss with W removed 73/87; forecast tests
25-45, judge 12-15/39 (blind measured), final 25-38; upper 60 if both v2 levers land.
Risks: (1) a careful reader may still pair periods on unnamed coefficients (joint sentence is explicit);
(2) allowance adds a 14th file and a scope extension; (3) W plus Y2 plus Z leave about half the hidden
rows `cannot_recompute`, so the verdict mix shifts toward the unresolved status.

## Lessons for the master
- A lever written as a directive or a procedure next to its field is transliterated; key it in another file or across records | template_change: LEVER_RULES_v3.md:102 add the directive case

import csv, json, sys
from pathlib import Path
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from levers_table import LEVERS, NEW_LEVERS

OUT = Path(__file__).resolve().parent.parent
S3, S4, S5, S6 = "s03_snapshot.py", "s04_claims.py", "s05_confounds_recipe.py", "s06_stage1_overlap.py"

# (id, doc line, claim, doc value, our value doc85 [cur90], script, verdict, note)
CLAIMS = [
    ("C01", "3-5", "85 bundles, each with exactly one trajectories/claude-opus-5/run_1/report.json", "85 opus-5 reports",
     "85 dirs at git 95f8fb386, 83 opus-5 + 2 opus-5-5 (11750b7a, 4ef4340d); today 92 dirs, 90 opus-5", S3, "PARTLY",
     "set reproduces exactly only with the 2 opus-5-5 runs included"),
    ("C02", "7", "2,950 graded test checks and 1,842 judge criteria", "2950 / 1842", "2950 / 1842 [3065 / 1963]", S3, "CONFIRMED", ""),
    ("C03", "8", "Judge model gpt-5.6-sol on every run", "all", "all 92 reports", "s01_reconcile.py", "CONFIRMED", ""),
    ("C04", "14", "4,792 graded items", "4792", "2950+1842 = 4792", S3, "CONFIRMED", ""),
    ("C05", "23-28", "Headline: mean 51.95, median 53.99, range 9.06-72.89, >=60 36, <40 18, <25 7",
     "51.95/53.99/36/18/7", "identical [cur90 50.58/52.66/36/22/11]", S4, "CONFIRMED", "true for the 27 Oct snapshot only"),
    ("C06", "34-35", "Tests mean 43.91 median 42.00, 3,734/8,429; judge 59.99/65.00, 2,950/4,514", "", "identical", S4, "CONFIRMED", ""),
    ("C07", "37", "Tests half is the weaker half in 55 of 85", "55", "55 [57 of 90]", S4, "CONFIRMED", ""),
    ("C08", "39-40", "No task above 72.89 and none at 0", "", "max 72.89, min 9.06", S4, "CONFIRMED", ""),
    ("C09", "51-53", "59417607 passed the six shipped_* checks and run_output_lists_reports", "7 passed", "same 7", S4, "CONFIRMED", ""),
    ("C10", "54-59", "59417607 failed hidden_extract_01..08, eight unseen inputs", "8", "18 failed (hidden_extract_01..18, all w5)", S4, "WRONG",
     "count wrong; direction right and stronger"),
    ("C11", "63-66", "8defd7be passed 2 plumbing checks, failed all eight full_ledger_on_unseen_run_*", "8",
     "2 passed; 11 full_ledger (alpha..kilo) failed, plus 26 w1 rule checks", S4, "PARTLY", ""),
    ("C12", "67-70", "d49e259f passed 3 checks, failed all eight mode_bit_*", "3 passed / 8 failed",
     "4 passed (also screened_intake_mode_zero_resolves); 13 mode_bit_* failed", S4, "PARTLY", ""),
    ("C13", "85", "Held-out checks: 361, 73% failed, 1,256 weight lost (77% of tier)", "361/73%/1256/77%",
     "374/73.3%/1322/77.3% (my regex; 69-78% over 4 regex variants)", S4, "CONFIRMED", "rate robust to taxonomy; counts not reproducible exactly"),
    ("C14", "86", "Cross-file lookup chain: 105, 64%, 281 (75%)", "105/64%", "97/60.8%/247 (71.6%)", S4, "PARTLY", "taxonomy"),
    ("C15", "87", "Exact value checks: 623, 60%, 1,588 (66%), largest absolute loss", "623/60%/1588", "590/59.3%/1494 (65.2%); largest loss yes",
     S4, "CONFIRMED", "rates within 1 point"),
    ("C16", "88", "Edge cases and traps: 263, 54%, 623 (59%)", "263/54%", "265/52.8%/610 (57.1%)", S4, "CONFIRMED", ""),
    ("C17", "89", "Determinism: 58, 31%, 72 (40%)", "58/31%", "59/30.5%/72 (40.2%)", S4, "CONFIRMED", ""),
    ("C18", "90", "Plumbing (exists, runs, parses, CLI): 118, 17%", "118/17%", "150/14.0%", S4, "PARTLY", "taxonomy"),
    ("C19", "91", "Shape/schema: 93, 15%", "93/15%", "104/24.0%", S4, "PARTLY", "taxonomy; mine fails more"),
    ("C20", "93-95", "24 tasks with plumbing and exact checks, 15 show 'plumbing passes, exact fails'", "24/15", "56/19 (my taxonomy)", S4,
     "UNTESTABLE", "doc gives no rule for 'signature'"),
    ("C21", "101-103", "Failure by weight: w1 107/572 19%, w3 301/704 43%, w5 737/1149 64%", "", "identical [cur90 18/42/66%]", S4, "CONFIRMED", ""),
    ("C22", "105-107", "Weight scale is an accurate difficulty predictor", "", "within-task: w5 pass < w1 pass in 73 of 83 tasks (36% vs 88%)", S4,
     "CONFIRMED", "predictor yes; it labels hard checks, it does not create difficulty (see levers L1)"),
    ("C23", "109", "26 of 85 tasks failed every weight-5 check", "26", "26 [28 of 90]", S4, "CONFIRMED", ""),
    ("C24", "110-112", "Then tests capped ~20-35% and final cannot pass 50", "<50", "7 of 26 have final >= 50 (5e4fd36d 71.65); tests median 8.0", S4,
     "WRONG", "judge half carries those 7"),
    ("C25", "118-131", "Token failure table (extract 99%, bit 96%, mode 92%, heldout 86%, ... exact 61% / 552 / 1,422)", "", "identical", S4,
     "CONFIRMED", "tokens concentrate: bit 26 of 50 from d49e259f; extract from 8 tasks; generalises from 4"),
    ("C26", "132-133", "Reliable tokens: delivered 5%, artifacts 5%, cli 18%, artifact 18%, config 21%, shipped 22%", "", "4.7/5.4/17.5/17.7/21.4/21.8", S4,
     "CONFIRMED", ""),
    ("C27", "137-141", "Most failed checks: zone_totals_match 7, corpus_index_match 7, posture_match 7, ...", "", "identical", S4, "CONFIRMED", ""),
    ("C28", "143-147", "aggregates_* fails across 7 serializations together: one computation, not seven", "", "7 tasks (all Nikhil Bansal): 5 fail 0/8-0/10, 2 pass 7/7 and 49/50", S4,
     "CONFIRMED", "all-or-nothing; one author"),
    ("C29", "155-158", "Judge by target: trajectory 893 32%, final_answer 286 34%, ufm 184 30%, state_change 71 27%", "", "identical (positive criteria)", S4, "CONFIRMED", ""),
    ("C30", "162-163", "Importance: critical 221/664 33%, important 233/770 30%", "", "33.3% / 30.3%", S4, "CONFIRMED", ""),
    ("C31", "165-166", "Judge failure flat across targets and importance", "", "27-34% across all cells", S4, "CONFIRMED", ""),
    ("C32", "170-175", "Judge themes: verify 52%, derive 48%, cover 34%, honest 33%, order 31%, read inputs 23%", "",
     "verify 51.9%, derive 37.7%, cover 32.7%, honest 34.3%, order 31.9%, read 24.4% (my regex)", S4, "PARTLY", "derive-not-shortcut not reproduced"),
    ("C33", "185-187", "Lack of self-verification is the mechanical cause of the held-out failures", "", "no counterfactual in one run per task", S4,
     "UNTESTABLE", "INFERRED; our 1b H9 habit says the same from trajectories"),
    ("C34", "193", "Test-side negatives: 525 defined, 2 fired", "525/2", "525/2", S4, "CONFIRMED", "both firing tasks (8d3e20fb, b625f36e) are on our section-8 holes list"),
    ("C35", "194", "Judge negatives: 408 defined, 27 fired in 21 tasks", "408/27/21", "408/27/21 [438/29/23]", S4, "CONFIRMED", ""),
    ("C36", "196-199", "Hardcoding, third-party deps, corpus reading, writing /app/data effectively extinct", "", "0 such test negatives fired", S4, "CONFIRMED", ""),
    ("C37", "201", "The 27 judge firings are almost all overclaiming", "almost all", "16-17 of 27 claim wording; 10 are scope, helper-script, literal or restart acts", S4,
     "PARTLY", ""),
    ("C38", "212-213", "Honesty negatives are the only negatives that earn their keep", "", "fired judge negatives cost 89 judge points in total vs 1,564 lost on positives (5.4%)", S4,
     "PARTLY", "true they fire; effect on score is small"),
    ("C39", "219-220", "Reward = 0.5*test/sum(pos) + 0.5*judge/sum(pos), unclamped", "", "reproduces 90/90 stored finals", "s01_reconcile.py", "CONFIRMED", ""),
    ("C40", "223-225", "Lose the w5 tier: tests near 25, run caps near 62", "25 / 62", "cap if all non-w5 passed: median 36.6, range 2.4-72.2", S4, "PARTLY", "depends on weight mix"),
    ("C41", "226-228", "Best: ec7941e5 91.55/54.24/72.89, 5e4fd36d 44.44/98.86/71.65", "", "identical; c9d7b490 71.83 (54.0/89.66) is 2nd and omitted", S4, "CONFIRMED", ""),
    ("C42", "228-229", "No task has both halves strong at once", "", "0 tasks with both >= 70; tests>=85: 10, judge>=85: 19", S4, "CONFIRMED", ""),
    ("C43", "231-234", "The halves fail for different reasons; 50/50 makes a hard ceiling in the low 70s", "",
     "r(tests, judge) = -0.40 pooled, -0.32 within author [-0.33 / -0.24]", S5, "CONFIRMED", "anti-correlation is new and stronger than the doc says"),
    ("C44", "246", "L1: heavy share r = -0.38 with tests half, the strongest lever measured", "-0.38", "-0.38 (within author -0.38); held-out w5 share -0.40 (within -0.43)", S5,
     "PARTLY", "held-out weight at w5 is as strong or stronger"),
    ("C45", "263-268", "Quartiles: Q1 41% 65.4/58.6, Q2 56% 35.3/51.4, Q3 71% 45.0/52.5, Q4 92% 30.6/45.6", "", "identical", S4, "CONFIRMED", "non-monotone Q2<Q3"),
    ("C46", "270-271", "Q1->Q4 costs 35 tests points and 13 final points", "35 / 13", "34.8 / 13.0; within-author r_final -0.14", S5, "PARTLY",
     "arithmetic right; final effect halves after the author control"),
    ("C47", "280-281", "Any held-out weight 52.1 final vs 51.6 without", "", "52.1 vs 51.7", S4, "CONFIRMED", ""),
    ("C48", "291", "Median task: 53 input files, 25,574 input lines", "53 / 25574", "53 / 25,171", S4, "PARTLY", "line-count method"),
    ("C49", "293-295", "resolves 66%, mode/bit 92-96%", "", "66.0 / 92.5 / 96.0", S4, "CONFIRMED", "mode/bit rests on 6-10 tasks, mostly d49e259f"),
    ("C50", "305", "Shape checks pass at 85%", "85%", "76% (my shape regex)", S4, "PARTLY", "taxonomy"),
    ("C51", "309-311", "Median 20 criteria (8-35); 908 trajectory, 294 final_answer, 187 ufm, 72 state_change; 779 important, 682 critical", "",
     "median 20 (8-35) right; positive 893/286/184/71 and 770/664, all 1156/361/231/94 and 923/919", S4, "WRONG",
     "second half matches no subset and contradicts section 4"),
    ("C52", "323-325", "A -5 cheat is 2.5 final points on a 100-weight positive total", "2.5", "0.5*5/100*100 = 2.5", "-", "CONFIRMED", "arithmetic"),
    ("C53", "342-356", "Correlation table (11 features)", "", "9 of 11 identical; held-out share -0.26/-0.35 vs doc -0.19/-0.21; cost, tokens within 0.01", S4,
     "CONFIRMED", ""),
    ("C54", "360-362", "Bulk (lines, bytes, files) does nothing", "~0", "r -0.04..+0.08; within-author +0.01..+0.06", S5, "CONFIRMED", ""),
    ("C55", "363-364", "More checks do not help", "-0.02", "-0.02 final; +0.13 tests", S4, "CONFIRMED", ""),
    ("C56", "365-368", "Longer instructions correlate slightly positively", "+0.11", "+0.11 [+0.17]; within author +0.16", S5, "CONFIRMED", "not significant at n=85"),
    ("C57", "369-371", "Median 5.38M tokens, $6.12; tokens and cost are symptoms not levers", "5.38M / $6.12", "5.64M / $6.32 (n=82); causal claim untested", S4,
     "PARTLY", ""),
    ("C58", "402-405", "Recipe profile: tests 5-25, judge 25-45, final 15-35; the seven tasks below 25 all have it", "7 of 7",
     "tests in range 2/7, judge 3/7, final 5/7", S5, "WRONG", "5 of 7 have tests below 5 or judge below 25"),
    ("C59", "375-396", "Stacking L1+L2+L3+L4+L5+L6+L7 holds Opus 5 under 40", "",
     "steps 1+3 matched by 3 tasks (9.06, 33.9 [hole task], 71.83); held-out w5 share >= 50%: 8 tasks, mean 34.8, 5 of 8 < 40", S5,
     "PARTLY", "the held-out w5 tier is the part that carries it; the full stack is untested (0 tasks match all steps)"),
    ("C60", "417", "Tests half = max(0, passed positive weight / positive weight)", "", "stored values subtract fired test negatives (8d3e20fb 41.24 vs 44.33; b625f36e 22.68 vs 25.77)", S5,
     "WRONG", "minor: 2 tasks"),
    ("C61", "421-426", "Field semantics for positive/negative tests and criteria", "", "reproduces 90/90; alternative judge reading fails 89/90", "s01_reconcile.py", "CONFIRMED", ""),
    ("C62", "431-433", "|r| < ~0.21 is not distinguishable from zero at n = 85", "0.21", "critical r(83 df, 5%) = 0.213", "-", "CONFIRMED", ""),
    ("C63", "248", "L3: cross-file chain checks fail 64%", "64%", "60.8%", S4, "PARTLY", "taxonomy"),
    ("C64", "249", "L4: exact checks lose 19% of all available test weight", "19%", "18.8% from doc figures; 17.7% my regex", S4, "CONFIRMED", ""),
    ("C65", "255", "0600 file-mode bug zeroed an EXEC tier; unpinned litellm in verifier image", "", "not in report.json", "-", "UNTESTABLE", ""),
    ("C66", "281-283", "Where held-out tiers carry the w5 band, the model loses the whole band", "",
     "8 tasks with held-out w5 share >= 50%: tests median 7, 7 of 8 below 36; f357cd96 70.71", S5, "PARTLY", ""),
    ("C67", "106-107", "Weight scale predicts difficulty without anyone having tuned it for that", "", "author eta^2 on heavy share 0.47", S5, "UNTESTABLE",
     "INFERRED: authors put w5 on the core outcome, which is the hard part; weight follows difficulty"),
    ("C68", "40", "No task is beyond it, none fully solved", "", "min 9.06, max 72.89", S4, "CONFIRMED", ""),
]

with open(OUT / "claims.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["id", "doc_line", "claim", "doc_value", "our_value_doc85 [cur90]", "script", "verdict", "note"])
    w.writerows(CLAIMS)

with open(OUT / "levers.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["lever", "doc_claim", "evidence_for", "evidence_against", "our_data", "legality", "in_LEVER_RULES_v3_as", "verdict", "how_to_apply"])
    w.writerows(LEVERS)
    w.writerows(NEW_LEVERS)

from collections import Counter
v = Counter(c[6] for c in CLAIMS)
lv = Counter(l[7] for l in LEVERS)
res = {"sha": "0036eb5", "status": "DONE", "findings": str(OUT / "FINDINGS.md"), "claims": len(CLAIMS),
       "confirmed": v["CONFIRMED"], "partly": v["PARTLY"], "wrong": v["WRONG"], "untestable": v["UNTESTABLE"],
       "levers_proven": lv["PROVEN"], "new_levers": len(NEW_LEVERS)}
(OUT / "result_0036eb5.json").write_text(json.dumps(res, indent=1) + "\n")
print(json.dumps(res))
print("lever verdicts:", dict(lv))

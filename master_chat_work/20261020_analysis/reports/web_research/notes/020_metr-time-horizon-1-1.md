# 020 METR Time Horizon 1.1 (Jan 2026) + live time-horizons page (last updated 8 Sep 2026) (METR)
URL: https://metr.org/blog/2026-01-29-time-horizon-1-1/ ; https://metr.org/time-horizons/ | Type: blog | File: sources/020_metr-time-horizon-1-1.html (+ sources/020_metr-time-horizons-page-text.txt, FAQ text of the live page)
## What it is
METR's 2026 update of the 011 methodology: 228-task suite (was 170), moved from Vivaria to Inspect. The live page (no longer actively updated) gives FAQ on interpretation. Per-model values on the live page are rendered by JavaScript, so not read (UNVERIFIED).
## Key findings (with cites)
- Suite 170 -> 228 tasks (+73 new HCAST, 15 removed, 53 updated); 8h+ tasks 14 -> 31; modifications/removals mostly because a task was confusing, "easy to reward-hack", or had scoring errors [blog, "Improvements to our task suite"]
- Only 5 of the 31 long (8h+) tasks have measured human baselines; the rest use estimates [blog]
- Opus 4.5: 289 min [110,1268] (TH1) -> 320 [170,729] (TH1.1); GPT-5 138 -> 214 (+55%); GPT-4 1106 8.5 -> 3.6 (-57%); upper CI bound of Opus 4.5 went from 4.4x to 2.3x the point estimate; units assumed minutes (second table in the post says "mins") [blog, "Comparison of Old and New Estimates"]
- Doubling time: TH1 7 months (196 days) hybrid; since 2023: 131 days (TH1.1) vs 165 (TH1); since 2024: 89 vs 109 days [blog]
- Estimates move with task composition and noise; scaffold matters: GPT-4o and o3 scored significantly higher under Vivaria than Inspect (paired t-test) [blog, "Moving from Vivaria to Inspect"]
- Saturation warning: even TH1.1 has "relatively few tasks that the latest generation of models cannot perform"; live page says measurements above 16 hrs are unreliable with the current suite [blog end; live page methodology box]
- Bimodal difficulty inside a length bucket: on 90 min-3 h tasks a GPT-5 agent (horizon ~2h17m) succeeds 100% on ~1/3 of tasks, fails 100% on ~1/3, and is mixed on ~1/3 [live page FAQ]
- 80% horizons: trend similar to 50% (see 011); 99% horizon not measured because it needs many more short tasks and is sensitive to broken tasks [live page FAQ]
- Task design: tasks are "self-contained and well-specified, with clear success criteria" automatically scored; human baseliners are skilled pros (~5 y experience) with the same instructions as agents; durations likely overestimate expert time [live page methodology]
- Scoring caveats: agents did worse on messier tasks (011) and performance "drops substantially when scoring holistically rather than algorithmically" (follow-up work cited, not read) [live page FAQ; follow-up UNVERIFIED]
- A "task" = a coherent unit that cannot be split: 1000 one-hour problems = a 1-hour task done 1000 times, not a 1000-hour task [live page FAQ]
## What lowers scores
- Genuinely sequential/dependent work of many human-hours; tasks outside the training distribution of suite families; per-task idiosyncratic traps (the bimodal third).
## Relevance to our constraint (rules visible)
- yes. METR's tasks are well-specified with visible instructions and frontier models still reach only ~50% at multi-hour lengths, and 80% horizons are 4-6x shorter (011). Design inference: a task whose coherent, non-splittable human time is long (many hours) with an automated checker keeps a careful model's success well below 50%; splittable repetition (many independent items) does not add difficulty per METR's definition.

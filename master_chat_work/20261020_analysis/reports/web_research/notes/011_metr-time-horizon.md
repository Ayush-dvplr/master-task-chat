# 011 Measuring AI Ability to Complete Long Software Tasks (Kwa, West et al., METR, 2025)
URL: https://arxiv.org/abs/2503.14499 | Type: paper | File: sources/011_metr-time-horizon.pdf
## What it is
Defines the "50% time horizon" = human-expert task length that a model completes with 50% success. Fits logistic curves on RE-Bench + HCAST + 66 short SWAA tasks with human baselines.
## Key findings (with cites)
- o3 has 50% horizon of ~110 min; doubling ~7 months 2019-2025 (207 days in the 50% fit) [abstract p1; §3.1 p6]
- Success falls exponentially with human task length: R^2 ~0.80 vs log(human time); linear fit y=-0.07x+0.66 (R^2 0.83) [§2.3 p5, Fig 3]
- 80% horizons are 4-6x shorter than 50% horizons: models cannot reliably do moderate-length tasks; 95% not measurable [§3.2.1 p7]
- Failure taxonomy (31 GPT-4 1106 / 32 o1 failed runs): premature task abandonment 8 / 16; repeating failed actions 12 / 2; incorrect mental math/reasoning 6 / 7; poor planning/tool choice 4 / 6; other 1 / 1 [Table 2 p7; §D.1 p25]
- "Premature abandonment" defined as submitting without checking correctness, often before reading all code/info needed; half of o1 failures [§D.1 p25]
- Agents struggle in "messier" environments: no clear feedback loop, or must proactively seek information [§3.3 p7]
- 16 messiness factors (mean 3.2/16, none >8/16 in suite): each +1 messiness point lowers success ~8.1% at equal task length (b=-0.081, R^2=0.251) [§F.2 p31]
- Messier subsets improve at the same pace (sub-hour tasks +40 pp Jan 2023-May 2025 in both splits) [§F.2 p31]
- Human baseliner success on long tasks often <50%; task length = geometric mean of successful baselines; human "time horizon" ~1.5 h despite 8 h paid cap [§C.1.4 p20]
- Contractors take 5-18x longer than repo maintainers on internal PRs; AI performance matches contractor time, not maintainer time [§4 p7]
## What lowers scores
- Longer human time; messy (underspecified, no feedback loop, resource-limited, novel, dynamic) tasks; abandoning/submitting unchecked; looping on failed actions (older models).
## Relevance to our constraint (rules visible)
- partly. Length and unchecked submission survive full documentation (task length is about work, not hidden info). The "messiness" factors that depend on missing info do not. A 4-8 h-human-equivalent chain with a strict checker is where 50% falls to <50%; 80% reliability needs far shorter tasks.

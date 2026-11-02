# 013 Cybench: A Framework for Evaluating Cybersecurity Capabilities and Risks of LMs (Zhang, Perry, ... Boneh, Ho, Liang; Stanford, ICLR 2025 ver.)
URL: https://arxiv.org/abs/2408.08926 | Type: paper | File: sources/013_cybench.pdf
## What it is
40 professional CTF tasks (FST 2 min to 24 h 54 min) with per-task subtasks for partial credit; 8 models, 4 scaffolds. Models are 2024-era, so absolute numbers are dated; the calibration method is the lesson.
## Key findings (with cites)
- Difficulty anchored on "first solve time" (FST) = time for the first human team to solve; range 2 min to 24 h 54 min, 136x between hardest and the 11-min ceiling [§1 p3; App. F p35-36]
- Unguided, agent solved no task with FST > 11 min; non-zero success on 73% of tasks with FST <= 11 min [§4 p8, Fig 3a]
- Unguided rates (single attempt, structured bash): Claude 3.5 Sonnet 17.5%, GPT-4o 12.5%, Claude 3 Opus 10.0%, o1-preview 10.0%, Gemini 1.5 Pro 7.5% [Table 6 p32]
- Partial credit by subtasks (each = question+answer scored sequentially, fractional score): subtask scores 8.2%-46.8% for the same models; o1-preview 46.8% vs 10.0% unguided [§2.3-2.4 p4-5; Table 6 p32]
- Subtask scores much higher than final-task rates: Claude 3.5 Sonnet 3 attempts + pseudoterminal: subtask-guided 27.5%, subtask perf 49.1% [Table 7 p32]. Scaffolding moved highest FST solved from 11 min to 52 min / 2 h 3 min with subtask guidance [Table 7 p32] and 75 min in a limitations remark [§I p39]
- GPT-4o subtask success is low mainly because it submits answers less often (low submission rate), not because submitted answers are wrong more often [App. Tables 4-5 p31]
- Cause of hardest-task failure: models struggle to make "insights" that take experts time; e.g. Robust CBC (FST 24 h 54 min) needs multiple cryptographic insights (truncated message pairs + length extension) [§4 p8]
- With rising FST the vulnerabilities become "increasingly subtle" [§4 p8]
## What lowers scores
- Tasks needing a non-obvious multi-step insight; long dependent exploit chains; not submitting answers.
## Relevance to our constraint (rules visible)
- yes for the calibration idea: everything is given (starter files, source), difficulty comes from the insight/chain, and FST predicts failure sharply. Also a template for partial credit: ordered subtask checkpoints (question+answer) give 8-47% when final success is 10%. Dated models, so treat the 11-minute ceiling as UNVERIFIED for current models.

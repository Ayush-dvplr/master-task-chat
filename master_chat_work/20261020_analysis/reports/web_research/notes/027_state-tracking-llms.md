# 027 Exploring State Tracking Capabilities of LLMs (Rezaee, Camacho-Collados, Pilehvar, Cardiff NLP, 2025)
URL: https://arxiv.org/abs/2511.10457 | Type: paper | File: sources/027_state-tracking-llms.pdf
## What it is
Three synthetic state-tracking tasks (LinearWorld = entity swaps, HandSwap = who holds what, Lights) with update depth 0..10; GPT-3.5, GPT-4o, GPT-4, Mixtral, Llama3 8B/70B, +/- CoT [§3, p.3-5].
## Key findings (with cites)
- Depth 0 (no updates) is ~100% for almost all models; the failure is following the update statements. Older/small models (GPT-3.5, Mixtral, Llama3 8B) drop sharply once depth reaches 2 [§5, p.5; Table 1, p.6].
- HandSwap, GPT-3.5 no-CoT: 1.00 (d0), 0.62 (d1), 0.45 (d2), 0.25 (d3), then ~0.27-0.38 up to d10; Mixtral 1.00/0.66/0.49/0.39 then ~0.24-0.42 [Table 1, p.6]. Chance-like floor for these tasks is ~0.3-0.5 (MFC baseline ~0.52 on Linear) [Table 1].
- Llama3 70B + CoT stays 0.60-1.00 at depth <=10 across the three tasks (e.g. 0.96/0.86/0.88/0.80 ... 0.84 on one; 0.98-1.00 on another; 0.60-0.62 at d9-d10 on the third) while without CoT it falls to 0.24-0.66 beyond depth 2 [Table 1, p.6].
- GPT-4o + CoT: 1.00 through depth 10 (0.96 at d10) on LinearWorld; the stateless baseline is ~0.4-0.6 [Table 1, p.6].
- Authors' conclusion: newest models (GPT-4, Llama3 70B) track state well esp. with CoT; the failure is mainly for the previous generation [Abstract, p.1].
## What lowers scores
- State updates applied WITHOUT writing intermediate states (no CoT / no scratchpad); index-addressed updates; depth only tested to 10.
## Relevance to our constraint (rules visible)
- Mostly NO for 2025-26 frontier: tracking 10 swaps is solved with CoT; longer chains (100s of dependent updates) are what fail (see 021). Python simulation bypasses it entirely. Useful as COUNTER-EVIDENCE: do not rely on short state-tracking puzzles to defeat Opus-class models.

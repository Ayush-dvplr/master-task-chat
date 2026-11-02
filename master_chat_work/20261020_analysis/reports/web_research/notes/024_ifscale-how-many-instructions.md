# 024 How Many Instructions Can LLMs Follow at Once? / IFScale (Jaroslawicz et al., Distyl AI, 2025)
URL: https://arxiv.org/abs/2507.11538 (v1, 15 Jul 2025) | Type: paper | File: sources/024_ifscale-how-many-instructions.pdf
## What it is
IFScale: write a business report while including N=10..500 required keywords (step 10); 20 models, 5 seeds; graded by deterministic regex [§4.1-4.2, p.4]. Every instruction is explicit and visible.
## Key findings (with cites)
- Best frontier model reaches only 68% at 500 instructions [Abstract, p.1]; gemini-2.5-pro-preview: 100.0 / 99.6 / 98.4 / 84.8 / 68.9 % at N=10/50/100/250/500 [App. A Table 1, p.12+].
- o3 62.8% and grok-3 61.9% at 500; claude-3.7-sonnet 52.7% vs claude-opus-4 44.6% and claude-sonnet-4 42.9%; deepseek-r1 30.9%; qwen3 26.9% [§4.3, p.5].
- Three decay shapes: threshold (o3, gemini-2.5-pro: near-perfect to a critical density then steeper slope + higher variance), linear (gpt-4.1, claude-sonnet-4), exponential (gpt-4o, llama-4-scout; floors of 7-15%) [Fig. 1, §4.4, p.1, 5-6].
- Reasoning models stay near-perfect through ~100-250 instructions [§4.3, p.5]. Example mid-tier: gemini-2.5-flash 100.0/96.0/82.0/50.7/34.2 % [Table 1].
- Primacy bias: error-rate ratio last-third/first-third peaks around 150-200 instructions then levels off at 300+ [§4.5, p.6, Fig. 3].
- Errors shift toward OMISSION as density rises (llama-4-scout omission:modification 34.88 at 500) [§4.6, p.7]. o3 outputs only ~1500 tokens at 500 instructions and its report coherence falls below threshold [§4.7, p.7]. Latency of reasoning models grows steeply (o3 26.30 s -> 219.58 s at 250) [§4.5, p.6].
## What lowers scores
- Hundreds of simultaneous independent, individually trivial constraints; later items in a list; omission under load. Models are mid-2025; Opus 4 / Sonnet 4 were the Claude entries - 2026 models UNVERIFIED.
## Relevance to our constraint (rules visible)
- YES: this is pure "all rules visible, still fails". Caveat: a terminal agent can script a checker (regex) for keyword-type rules, so density helps most when constraints are heterogeneous, interacting, and not mechanically checkable by a one-liner; scale to 100s of rules, not 10s (frontier ~98% at 100).

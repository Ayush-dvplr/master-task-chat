# 022 The Illusion of Thinking (Shojaee, Mirzadeh, ... Farajtabar, Apple, 2025; v3 20 Nov 2025)
URL: https://arxiv.org/abs/2506.06941 | Type: paper | File: sources/022_illusion-of-thinking.pdf
## What it is
Controllable puzzles (Tower of Hanoi, Checker Jumping, River Crossing, Blocks World) with complexity N; rules fully given in prompt; 25 samples/model/level; max 64k tokens for local models [§4.1, p.8].
## Key findings (with cites)
- Three regimes: low complexity non-thinking >= thinking; medium thinking better; high both collapse to ~0 [§4.2.1, p.8].
- Reasoning models (o3-mini, R1, R1-Distill-Qwen-32B, Claude-3.7-Sonnet thinking): accuracy declines gradually then collapses; thinking tokens rise then DROP near the collapse point despite unused budget [§4.2.2, p.9, Fig. 6].
- Giving the full solution algorithm in the prompt did not move the collapse point for Hanoi/Checker Jumping (DeepSeek-R1, Claude-3.7 thinking) [§4.4, p.11, Fig. 8].
- Hanoi: first error at ~move 100 for N=10 but below move 50 for N=12; River Crossing: first valid-until move ~4; near-perfect Hanoi N=5 (31 moves) yet fails River Crossing N=3 (11 moves) [§4.4, p.11-12, Fig. 9]. Non-monotonic, unfamiliar-puzzle sensitivity.
- Response to context-limit critique: collapse at N=7-8 (~100-200 moves); for N=8 (255 moves) first failure ~move 40 (15%); N~10 first failure within first ~100 moves [App., p.19].
- Overthinking at low N: correct solution found early, then replaced by wrong ones; at high N model fixates on early wrong solution [§4.3, p.10, Fig. 7].
## What lowers scores
- Long exact move sequences with hard validity constraints; unfamiliar puzzle variants (River Crossing with constraints); models tested are 2025 (Claude-3.7, o3-mini, R1) - current 2026 frontier behaviour UNVERIFIED here. Paper was publicly contested (e.g. output-limit and unsolvable-instance critiques; see 021 which reframes as execution error) - those critiques not read by me, UNVERIFIED.
## Relevance to our constraint (rules visible)
- Partly. Survives for hand-simulated puzzle move lists (rules written, still collapse). A terminal agent with Python can write a solver/BFS and bypass it entirely, so use only for puzzles where search state space is big (unsolvable by naive recursion) or where the verifier is the hidden hard part.

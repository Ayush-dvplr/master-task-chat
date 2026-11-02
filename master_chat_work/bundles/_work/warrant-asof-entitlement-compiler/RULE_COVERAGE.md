# RULE_COVERAGE.md (P12 4989b35, AL-27 window rule)

Rule: access_contract.md:40 and time_rules.md:21, every window follows the one boundary convention the corpus's gateway enforces; conv_2 (85041), conv_6 (98123), conv_8 (99061) plant `closed`.
Mutant: the verifier reference with only one layer following the closed test and every other layer half open (`World.inw` patched by caller, WORK/p12/exp2.py on p12/t7.py, output p12/runs/exp2_t7.txt), compared with the all half open profile. A layer counts for a profile when its units exceed the key value baseline of that profile (conv_2 prod 28, conv_6 dev 1, conv_8 dev 2). Count: conv profile checks whose expected profile changes (exact checks, so each changed profile fails). Whole-rule mutant measured end to end: kill program P7w (every convention inferred except the window, fixed half open) on the final tests, p12/runs/s6_P7w.txt (closed tiers only, verifier budget lifted because P7w calls take about 370 s).

| rule | mutant | failing checks |
|---|---|---|
| membership window end | `directory_layer` half open | 4 (conv_2 prod, conv_6 dev, conv_8 dev, conv_8 prod) |
| binding window end | `binding_layer` half open | 1 (conv_2 prod) |
| grant window end | grant test half open | 1 (conv_2 dev) |
| freeze window end | ticket freeze test half open | 3 (conv_6 dev, conv_8 dev, conv_8 prod) |
| key value end | key listing at `as_of` half open | 3 (conv_2 prod, conv_6 dev, conv_8 dev) |
| whole window rule | P7w, window fixed half open (verifier budget lifted) | 6: conv_2 dev, conv_2 prod, conv_6 dev, conv_6 prod, conv_8 dev, conv_8 prod (p12/runs/s6_P7w.txt) |

Not planted: contract cover and on call shift ends. Both are routed through the settled window in the oracle and the verifier, but no conv tier puts `as_of` on a local midnight or a rota boundary (exp2_t7 shows no units above the baseline for `standing_of` or `shifts`).

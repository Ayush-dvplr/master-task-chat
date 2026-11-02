# BRANCH_FIRE cold-chain-backbone-quote (cap-60 build b223662, 30 Oct)

Hard branch of lever P-1 = a project needing the split at single sites to be solved inside the stated limit
(`_wide_shape` in tests/test_output.py: >= 5 pieces of 3+ ranks split at single sites, >= 5 hubs, connected,
>= 28 cold rooms, a link reaching half the corridor). The builder asserts all three on every wide project.

| rule | branch | fires on shipped (count) | fires on hidden (seeds) |
|---|---|---|---|
| minimum-cost network inside the limit (api_contract.md:84-92) | wide project (>= 28 cold rooms, split at single sites, hubs, half-book reach) | 0 of 96 projects (shipped cold rooms 4 to 10) | every project of wide_1..wide_10 (BOOK_SEED+5..+14, 100 projects); sweep300.py 300 seeds for the builder |
| tie vector (api_contract.md:86-89) | two optimal networks | ties book and one planted project per wide book | ties (BOOK_SEED+4), wide_1..wide_10 |
| activation once per activated site (api_contract.md:78-82) | site reached by two or more booked links | shipped book (fires) | every fresh and wide book |

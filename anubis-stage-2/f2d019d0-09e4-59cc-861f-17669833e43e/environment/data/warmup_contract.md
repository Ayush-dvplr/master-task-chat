# Warmup

The warmup window is every step whose index is at most `warmup_bound`. The two
gates read the complementary window, every step whose index is strictly greater
than `warmup_bound`. The bound itself therefore belongs to the profile and not
to the gates.

The profile publishes the distinct token counts, the distinct rank bucket values
and the distinct local expert counts observed inside the window, each sorted
ascending, together with the number of recompiles inside the window.

A dimension is listed in `dims_requiring_dynamic` when the number of distinct
values it showed inside the window is at least `promotion_threshold`. Only
`tokens` and `local_experts` are eligible for that list. The capacity dimension
is chosen by the settlement itself and is never listed there, however many
distinct values the window happened to show.

`warmup_windows.json` records the bound used by each shipped profile.

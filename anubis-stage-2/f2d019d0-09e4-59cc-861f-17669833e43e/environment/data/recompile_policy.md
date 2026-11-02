# Compiled entry cache

Each `(code_object, rank)` pair owns a cache holding at most `cache_size_limit`
entries. Within one step the pairs are visited in ascending code object name and
then ascending rank, and the router is visited before the expert regions because
its name sorts first.

A key already present is a hit; its use marker is refreshed and nothing else
happens. A key absent from the cache is a recompile. When the cache already
holds `cache_size_limit` entries the least recently used entry is evicted first,
and a tie on the use marker is broken by evicting the lexicographically smallest
key text. The new entry is then inserted and marked used.

A recompile event carries the step, the code object, the rank, the key, the two
static dimension counts, their signed difference and the evicted key or a null
when nothing was evicted.

`recompiles_after_warmup` counts recompile events at steps strictly greater than
`warmup_bound`.

## Reset

At the start of a step listed in `reset_steps` every cache and the capture pool
are cleared. Promotion state survives a reset.

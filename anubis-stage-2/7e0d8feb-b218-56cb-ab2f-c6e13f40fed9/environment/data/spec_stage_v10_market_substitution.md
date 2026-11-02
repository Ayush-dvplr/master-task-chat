# V10 market substitution

Inputs: `market_register.csv`, `blackout_rule_set.xml`,
`substitution_library.csv`, and the placed slots from V7 and V8.

The channel runs into four markets. The national conform is one day; what
differs between markets is which slots carry substitute material and
therefore which breaks exist.

## R25 the window

A blackout rule matches a slot in a market when the rule's `market_ref` is
that market, the rule's `content_ref` is the slot's content, and the
transmission date lies inside the rule's window. The window is inclusive at
both ends: a transmission date equal to `window_from` is inside it and a
transmission date equal to `window_to` is inside it.

## R26 the precedence and the overturn

The matching rules for one slot in one market are ordered by ascending
`precedence` and then by ascending `rule_id`. The first rule in that order
is the base rule.

A rule whose `override` is `yes` overturns every rule before it in that
order. When one or more overturning rules match, the last overturning rule
in the order wins. When none does, the base rule wins.

An overturning rule therefore wins from a higher precedence number, which is
the opposite of what precedence alone would give.

## The substituted break set

A slot substituted in a market carries the substitute's breaks in place of
its own. The substitute's breaks come from `substitution_library.csv` under
the winning rule's `substitute_ref`, in ascending `break_no`.

A substitute has no index of its own, so its break positions are not
snapped. Each substitute break offset converts by the carry rule inside the
scope `V10:` and the market reference, and its position is the slot's placed
start plus that offset. Its break reference is `sb_`, the substitute
reference, an underscore and the two digit break number.

A slot that is not substituted in a market carries its national breaks with
the positions V6 conditioned. Its break reference is `bk_`, the slot id, an
underscore and the two digit break number.

## Published

`market_overrides.csv` publishes one row per substituted slot per market,
ordered by market reference and then by slot id. Each per market avail
file, named for its market reference, publishes that market's whole break
set in transmission order together with the two carry residuals of that
market.
`market_avail_stream.jsonl` publishes every market's breaks in one stream.

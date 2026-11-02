# Compile modes

- `reduce-overhead` compiles and then attempts graph capture. It pays the highest
  compile cost and the capture cost, and it earns the replay discount.
- `default` compiles without capture. It pays a lower compile cost, records the
  cause `capture_disabled_for_mode` for every attempt and earns a much weaker
  discount.
- `eager` compiles nothing. It is present in the candidate axes so that the
  settlement can reject it by name rather than by silence. It is never an
  admissible answer.

`mark_dynamic` names dimensions that start dynamic. Only `tokens` and `capacity`
appear in the shipped axes. Marking a dimension changes the memory slot row that
the host ledger reads, because that row is indexed by the number of marked
dimensions.

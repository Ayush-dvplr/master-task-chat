# Handover from the previous operator

Notes I kept while running the old replay tool. Use them with care.

* When no owned server or hint is taken, the smallest free server goes first.
* A session is still live during the second its `until` arrives.
* When `owned.csv` lists a player twice, the later row is the current one.
* A released server is free again straight away.
* A returning player is treated like anybody else; earlier servers mean nothing.
* Records in the same second are replayed in `seq` order.
* The mode word was a debugging switch. Live intakes replay under the same
  rules as the worked examples whatever it says.

# Handover from the previous operator

Notes I kept while running the old replay tool. Use them with care.

* A lock is still in force during the second its end arrives.
* A failure exactly `window` seconds old has already dropped out.
* When `overrides.csv` lists a user twice, the later row is the current one.
* A good password from a locked user lets them in and clears the lock.
* Every lock lasts the policy `lock` length, however often the user is locked.
* Records in the same second are replayed in `seq` order.
* The mode word was a debugging switch. Live intakes replay under the same
  rules as the worked examples whatever it says.

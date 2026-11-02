# Handover notes

Notes from the engineer who ran the old resolver, written from memory after
the source was lost.

* When the feed carries two different copies of the same package version, the
  old resolver kept the most recent one, because a republish is always a fix.
* Yanks always applied. Once a version was yanked it was gone for good.
* The previous lock was honoured whenever its version was still a candidate.
* Release candidates were treated like any other version when they met a range.
* Requirements went onto the queue in the order they appear in the files.
* If `pins.csv` has two rows for one package, the later row is the current one.
* The mode word was a debugging switch. Live intakes settle under the same
  rules as the worked examples whatever it says.

# Handover from the last on-call

Notes on how the old pruner behaved, written from memory the week it was
switched off.

* The newest snapshot in a bucket stood for it; nobody wants a stale copy.
* Weeks ran Monday to Sunday, the ISO way.
* A hold covered its snapshot through the `until` date itself.
* Partial snapshots counted like any other; the size was what mattered.
* When an id was republished the latest copy in the file won.
* Buckets were read off the clock printed in the stamp, since that is what
  the host operator sees.
* The mode word was a debugging switch. Live intakes prune under the same
  rules as the worked examples whatever it says.

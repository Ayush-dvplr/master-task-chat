# On call notes

Observations only.

- the shape distribution stops changing after the first dozen steps yet
  compilation continues
- several experts receive no tokens at all on some steps and the balance term
  behaves differently on those steps than the previous run
- the exchanged payload is larger than the per rank padding suggests
- host memory grows in steps that look like whole cache entries rather than
  activations
- host memory never falls from one step to the next, and the last row of the
  memory trace carries the peak
- the loss is close to the reference but the closing figure sits outside the band
  the acceptance sheet quotes

No diagnosis was reached before the job was killed.

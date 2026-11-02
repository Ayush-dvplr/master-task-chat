# Incident 7734

The run reached the first checkpoint and then degraded. Symptoms recorded by the
on call engineer:

- device utilisation collapsed to roughly a third of the profiled figure and the
  timeline filled with gaps between kernels
- the compile log kept emitting recompilation lines far past the warmup window,
  long after the shape distribution was supposed to have settled
- the host resident set grew monotonically and the job was eventually killed by
  the out of memory reaper
- capture attempts logged `CUDA error: operation not permitted when stream is
  capturing`
- the published throughput figure did not match the wall clock of the job

The orchestrator that produced the run is `deployed_trainer.py`. Its published
figures are `deployed_run_summary.json`. Nothing in this corpus states which of
its decisions is wrong.

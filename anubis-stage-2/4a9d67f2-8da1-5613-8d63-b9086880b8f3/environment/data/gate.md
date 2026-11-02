# The inference gate

This directory holds one recorded shift, one older shift the serving team had
already worked through, and a set of digests over what the inference gate
produced for the recorded one. The gate itself was lost when the serving
controller was replaced. Its shape is written down here. Its numbers are not:
every figure each stage applies lived in the controller build and was never
recorded anywhere.

## What ships here

Five files describe a shift.

| File | One row per | Columns |
|---|---|---|
| `runtimes.csv` | serving runtime | `runtime`, `kernel`, `floor` |
| `variants.csv` | model variant | `variant`, `precision`, `base` |
| `callers.csv` | calling account | `caller`, `plan` |
| `endpoints.csv` | serving endpoint | `endpoint`, `runtime`, `variant`, `accel`, `tier` |
| `probes.bin` | metered request | `seq`, `endpoint`, `tag`, `caller`, `mode`, `phase`, `meter`, `rows`, `spans`, `replays` (a binary file; `wire-format.md` gives the byte layout) |

`probes.bin` stores its records in an arbitrary order. The gate resolves probes in
ascending `seq`, which is a single shift wide ordering across every endpoint.

`kernel` is one of `graph`, `eager`, `fused`, `traced`. `precision` is one of
`fp32`, `fp16`, `bf16`, `int8`. `plan` is one of `gold`, `silver`, `bronze`,
`trial`. `accel` is one of `cuda`, `rocm`, `xla`, `npu`, `fpga`, `wasm`, `none`.
`tier` is 1, 2 or 3. `mode` is one of `serve`, `reset`, `drain`, `refund`,
`abort`. `phase` is one of `prefill`, `decode`, `batch`. Not every row of a
lookup table is necessarily used by an endpoint in a given shift.

The `base` column of `variants.csv` is either empty or the identifier of another
variant in the same table. A variant named as a base has an empty `base` of its
own, so the chain is at most one step long. Whether the precision the gate
charges is the variant's own or the one it inherits is a missing constant.

## The worked example

The gate's own output for the recorded shift was lost along with the gate, so
this directory carries no resolved report for it. What it carries instead is one
older shift the team had already published, under the same five file names with
an `example_` prefix, together with the scored verdicts the gate wrote for that
older shift in `example_verdicts.jsonl`.

The team published those verdicts and nothing else for that shift: the three
rollup documents were never kept. What the shift covers and what it leaves open
is for the reader to work out from the two files themselves.

## The digest

`digest.json` is what the serving team kept of the recorded shift's outcome. It
carries one sha256 over each of the four reports the gate wrote, computed
exactly as `reports.md` sets out. A digest goes green only when the whole shift
resolves correctly.

## The meter column

The `meter` column does not carry the meter. Inside a segment it carries a first
difference of a cumulative token counter, and the gate accumulates to recover
it: the first probe of a segment carries the counter itself and every probe
after that carries the change from the one before it. The accumulation runs per
endpoint and per phase, so one endpoint serving all three phases carries three
counters at once, and a segment boundary restarts every counter the endpoint
holds. Which mode opens a segment is a missing constant.

One reserved value never means a difference. A probe carrying it takes the meter
of the probe resolved before it on the same endpoint and the same phase, and
leaves the accumulation untouched. Which value is reserved is a missing
constant.

One of the seven accelerators records its meter on a coarser scale than the
others, so the recovered figure has to be brought back to tokens before anything
else happens to it. Which accelerator and what scale are missing constants.

## Carried endpoint state

Each endpoint carries six things while its probes are resolved.

- `budget`: starts at the `floor` figure of the endpoint's runtime.
- `backlog`: starts at zero.
- strike count: starts at zero.
- whether the endpoint's previous probe was a `serve`.
- a one shot credit that one of the five modes arms.
- a bounded trailing record of the endpoint's most recent resolved probes,
  holding the `tag` each carried and the score each was given. How many probes
  that record keeps is a missing constant.

One piece of state does not stay inside its endpoint. The budget a segment
boundary installs is derived from the scores the gate has already resolved
across the whole shift up to that probe, so an endpoint cannot be resolved on
its own.

## The stage order

Every probe passes through these stages in this order. No stage in the chain
reports a figure below zero: each one clamps its result at zero before the next
stage runs.

1. **Batch width.** The probe carries two count columns, `rows` and `spans`. One
   of them governs and the other is left alone, and which one governs depends on
   the value `spans` carries. When `spans` is the one that governs it is first
   multiplied by one fixed factor.
2. **Replay expansion.** The width is multiplied by the probe's replay count.
   The `replays` column stores that count with one fixed whole number offset
   applied to it.
3. **Warmup draw.** The endpoint's current budget is taken off the recovered
   meter.
4. **Throughput normalisation.** The figure is rescaled against the batch width
   with one fixed gain, and the division truncates towards zero.
5. **Precision response.** One adjustment keyed on the precision the endpoint's
   variant is charged at. A precision value may carry an adjustment or leave the
   figure alone.
6. **Accelerator response.** One adjustment keyed on the endpoint's `accel`. An
   accelerator value may carry an adjustment or leave the figure alone.
7. **Phase response.** One adjustment keyed on the probe's `phase`. A phase may
   carry an adjustment or leave the figure alone.
8. **Kernel response.** One adjustment keyed on the runtime's `kernel`. A kernel
   may carry an adjustment or leave the figure alone.
9. **Backlog relief.** The endpoint's backlog at the moment the probe is
   resolved is taken off the figure. That backlog is reported as
   `backlog_before` and the result is the probe's score so far.
10. **Replay lookup.** When the probe's `tag` also sits in the endpoint's
    trailing record, the score of the most recent probe in that record carrying
    the same tag replaces the figure this probe would otherwise be given. A tag
    that has dropped out of the trailing record does nothing.
11. **Credit.** When the endpoint's one shot credit is armed, the score is
    reduced by one fixed division and the credit disarms. The result is reported
    as `score`.
12. **Banding.** `score` falls into one of four bands, reported as `band`:
    `saturate`, `high`, `base` or `idle`, from the widest figure down.
13. **Verdict.** The mode decides first. Two of the five modes are bookkeeping
    and resolve to `setup`, and one marks an abandoned probe and resolves to
    `void`. Any probe the mode does not settle goes down an ordered ladder where
    the first condition that holds wins and the rest are never consulted: a
    bottom band probe resolves to `rejected`; a probe whose `backlog_before`
    sits above the tolerance of the caller's `plan` resolves to `flagged`;
    anything left resolves to `ok`.
14. **Carry update.** After the score is emitted the endpoint state moves on.
    One mode reinstalls the budget from the running figure described above. One
    mode clears the backlog. One mode arms the one shot credit. A `serve` probe
    adds a backlog amount derived from its batch width, a `tier` value doubles
    that amount, and a serve that directly follows another serve on the same
    endpoint adds a further fixed amount on top. Backlog has a ceiling it never
    passes. A probe that resolved to `rejected` adds one strike. The probe's tag
    and score then join the trailing record, and the oldest entry drops out once
    the record is full.

## What is missing

Every figure the stages above apply, every mode the carry update names, every
tolerance the ladder consults, the scale the coarse accelerator records on, the
value reserved in the meter column and both of the tie breaks in `reports.md`
were controller constants. Not one of them is written down in this directory,
and neither is a list of them. The worked example, the recorded shift and
`digest.json` are the only evidence there is.

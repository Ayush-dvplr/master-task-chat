# Publication contract for interval PI-2032-M12

The array is phase coherent only while every site works to one time scale.
Each publication interval the desk recomputes that scale from the oscillator
population, steers it onto the primary caesium realisation and publishes the
offset of every site from it. The previous publication of this interval was
withdrawn. This directory holds the working papers and the interval has to be
recomputed from them.

## The thirteen stages

| stage | subject | specification |
| --- | --- | --- |
| T01 | reading canonicalisation | spec_stage_t01_reading_canonicalisation.md |
| T02 | delay calibration | spec_stage_t02_delay_calibration.md |
| T03 | measurement sense | spec_stage_t03_measurement_sense.md |
| T04 | link graph and spanning tree | spec_stage_t04_link_graph.md |
| T05 | node offsets and dead time | spec_stage_t05_node_offsets.md |
| T06 | oscillator deviation series | spec_stage_t06_oscillator_series.md |
| T07 | frequency prediction | spec_stage_t07_frequency_prediction.md |
| T08 | dispersion and raw weight | spec_stage_t08_dispersion_and_weight.md |
| T09 | weight capping | spec_stage_t09_weight_capping.md |
| T10 | free ensemble scale | spec_stage_t10_ensemble_scale.md |
| T11 | steering | spec_stage_t11_steering.md |
| T12 | dissemination and uncertainty | spec_stage_t12_dissemination.md |
| T13 | reports and manifest | spec_stage_t13_reports_and_manifest.md |

Each stage freezes a value the next stage consumes. The canonical reading is
frozen at T01, the spanning tree edge set at T04, the prediction frequency and
its anchor at T07, the weight vector at T09 and the steering step at T11. A
stage never revisits a value an earlier stage froze.

## The pervasive rule

Every quantity in the chain is carried as an exact rational. No stage rounds,
truncates or converts to a binary floating point number. Rounding is applied
once, at the moment a value is written into an artifact, under the rule
rounding_policy.yaml states. Two stages carry a rounded value forward instead,
and each says so and why: the published dispersion of stage T08, and the weight
grid the capping passes of stage T09 place the vector on.

## Units

Every recorded and published time quantity is a whole number of picoseconds
unless a paper says otherwise. Delay calibration reports publish nanoseconds.
Frequency is carried and published in parts in ten to the eighteenth. One grid
step at one part in ten to the eighteenth is exactly 864 ten thousandths of a
picosecond.

# Band plan

The measurable spectrum of the coexistence register is the union of the bands
listed below. Frequency bounds are kilohertz, lower bound inclusive and upper
bound exclusive. Spectrum that falls between two bands is not measurable and
carries no occupancy. The raster column repeats the nominal channel width of
the band; `channel_raster.csv` is the authority for individual channel bounds
and for channel withdrawal.

| band | f_low_khz | f_high_khz | raster_khz |
| --- | --- | --- | --- |
| B1 | 410000 | 430000 | 25 |
| B2 | 450000 | 470000 | 25 |
| B3 | 862000 | 876000 | 25 |
| B4 | 1427000 | 1452000 | 100 |

A channel whose status in `channel_raster.csv` is `withdrawn` is not
measurable spectrum. A grant that covers withdrawn channels keeps only the
usable runs of its frequency span, so one grant can carry several frequency
runs. A grant whose frequency span meets no usable channel at all is faulty.

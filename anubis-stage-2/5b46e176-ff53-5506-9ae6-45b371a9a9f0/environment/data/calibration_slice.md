# The calibration slice

Seven properties of this interchange were never written into the rulebooks.
They are the order in which the four rate adjustments compose, the quantity
the shortfall levy is a share of, the spacing of the settlement grid, the
convention for a value that falls exactly between two grid points, the reach
of a reversal record, the order in which revenue caps release surplus, and
the convention by which a fault window is read at its own two endpoints.

The interchange has, however, published a small epoch it already cleared,
together with the figures that epoch cleared to. That is the calibration
slice, and it is what the seven properties are recovered from. Exactly one
combination of the seven reproduces every published figure.

## Where it lives

`calibration_controls.json` carries the whole of it, and it travels with the
registers rather than with this reference set. Its keys are:

- `epoch_id`: the identifier of the calibration epoch.
- `property_names`: the seven property names, in the order this file names
  them above. They are also the key names the epoch summary reports them
  under.
- `adjustment_names`: the four adjustment names, which are the members every
  candidate `adjustment_order` is a permutation of.
- `legal_values`: an object keyed by property name. Each value is the full
  list of candidates for that property, and a recovered value that is not on
  its list is not a legal reading. The candidate lists are the whole search:
  nothing outside them is admitted.
- `slice`: the registers of the calibration epoch, one key per register,
  each holding that register's rows as objects with the same column names the
  register's own file uses. The slice is a complete register set and it is
  cleared by exactly the rules the rulebooks state.
- `published`: the figures the calibration epoch cleared to.

## The published figures

`published` carries these keys:

| key | what it holds |
|---|---|
| `epoch_charge_micros` | the calibration epoch's charge |
| `taps_priced` | how many taps it priced |
| `taps_withdrawn` | how many it withdrew |
| `priced_distance_units` | the distance units it priced |
| `unit_fare_checks` | an object from `tap_id` to unit fare, for every priced tap |
| `suspended_gates` | the gates it suspended, ascending |
| `curtailed_tap_ids` | the taps capping withdrew, ascending |
| `loan_total_micros` | the total lent between its zones |
| `loans` | every loan as a three element list of lender zone, borrower zone and amount, in the order the loans were made |
| `netting_digest` | the digest its netting layer settled |
| `assurance_pool_micros` | the pool its assurance layer retained |
| `assurance_digest` | the digest its assurance layer settled |

Each figure is one the rulebooks define for any epoch, computed on the slice.

## How the slice behaves

The slice is small on purpose: it is a few dozen taps over two operators and
five zones, so a candidate reading can be tried against it cheaply. It is
also built so that every one of the seven properties changes at least one
published figure. In particular the slice carries a tap whose relieved fare
is smaller than the abatement that bears on it, taps sitting exactly on a
fault window's endpoints, taps whose fares land exactly between two grid
points on both an even and an odd multiple, a reversal record with further
taps of the same identity in its own zone, in a sibling zone of its own
operator and in another operator's zone, and two zones over their caps whose
operator has two possible lenders and a lending ceiling that binds.

A reading that gets a property wrong therefore disagrees with the published
figures rather than quietly agreeing with them.

## Reporting what was recovered

The epoch summary carries the seven recovered values under
`resolved_parameters`, keyed by the names `property_names` gives and holding
values from `legal_values`. `adjustment_order` is reported as the list of the
four adjustment names in the recovered order; `grid_step_micros` as an
integer; the other five as the candidate string.

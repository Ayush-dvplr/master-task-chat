# Stage P10, the tariff and the demand charge

RULE P10.a  The price of an interval is the price of its governing
row of tariff_interval_schedule.csv, quoted in tenths of a cent for
each kilowatt hour.

RULE P10.b  The energy of an interval is its final yard load watts
divided by four and rounded half up to a whole watt hour. That
stored whole number is what the charge is computed from.

RULE P10.c  The charge of an interval is its stored energy watt
hours multiplied by its price and divided by ten thousand, rounded
half up to a whole cent. The rounding happens once per interval.

RULE P10.d  The peak of a substation is the highest final load its
feeders carry together in any one interval. A tie is settled by the
earlier interval.

RULE P10.e  The demand charge band of a substation is the governing
band row of demand_charge_bands.tsv for that substation whose floor
stands at or below the peak and whose ceiling stands above it. A
peak equal to the floor of a band belongs to that band.

RULE P10.f  The demand charge is the sum of the band charges of the
substations. The yard peak is the highest final yard load in any one
interval, with a tie settled by the earlier interval.

## Published documents

tariff_charge_ledger.csv and peak_demand_certificate.json.

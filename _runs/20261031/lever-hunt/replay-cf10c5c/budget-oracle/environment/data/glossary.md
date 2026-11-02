# Glossary

Terms defined here carry their defined meaning wherever they appear in the documents of this extract, including where the term is an everyday word. Entries are in alphabetical order.

**applied transaction.** A transaction row that is well formed, dated inside the period, and not voided by a correction at or below the cutoff sequence.

**balancing adjustment.** The change that std_sweep.md makes to one posted amount of a round so that the posted amounts of the round add up to zero.

**category code.** The register's code for an envelope's spending category. cat_codes.docx maps each category code to a category name.

**cents.** Hundredths of a dollar. Amounts in the transaction exports and the register are in cents unless the field dictionary gives dollars.

**claim.** An envelope's need plus its shortfall.

**correction.** One row of adj_log.psv.

**crosswalk.** The file xw_columns.json. It maps each register export's own column names to the canonical field names that dict_register.md uses.

**cutoff sequence.** The `cutoff_seq` value in office.ini.

**damping rate.** The whole percentage at which a household's draft amounts are taken. The damping rate of a round is the rate as it stands once every halving that the round brings about has been made.

**district.** The area a household is filed under. The five districts are central, east, north, south and west. District names compare without regard to letter case, and reports write them exactly as listed in this entry.

**draft amount.** The amount the sweep computes for one envelope in one round from its gap and the damping rate.

**envelope.** A budget pot of one household. It has a code, a label, a need and a balance.

**envelope code.** The register's identifier of an envelope. Envelope code order is the ascending code point order of the codes.

**family name.** The surname under which the office files a household.

**file number.** The register's folder identifier. Each envelope sits in one folder and each folder belongs to one household.

**first.** Among envelopes of one household, the first is the one whose label comes earliest when labels are compared code point by code point, so that every uppercase letter comes before every lowercase letter.

**funding code.** The register's code for who funds an envelope. fund_codes.pdf maps each funding code to a segment.

**gap.** An envelope's target less its standing balance.

**household.** A client family of the office. The office keeps one household in each district.

**lower, lowest.** Of two states of one household, one is lower than the other when, with both balance lists read in envelope code order, it holds the smaller balance at the earliest position where the two lists differ. The lowest of several states is the one that is lower than each of the others.

**need.** The amount, in whole dollars, that a household plans to hold in an envelope for the month.

**opening cents.** The balance, in cents, that an envelope held when the period opened.

**out of period.** Dated before `first_day` or after `last_day` of office.ini.

**patience.** The number from the parameter sheet that the strike count must reach for the damping rate to be halved.

**period.** The days from `first_day` to `last_day` of office.ini, both days included.

**pool.** The sum of the balances of a household's envelopes. The sweep never changes it.

**posted amount.** The amount that a round adds to an envelope's balance.

**pre-sweep balance.** An envelope's balance once the ledger has closed, in whole dollars (std_ledger.md).

**record.** Of a household's sweep, the states the household held from the earliest time it held the state that recurs up to the state it held just before the recurrence. States the household held before that earliest time are not on the record.

**register of record.** The three register exports read through the crosswalk, together with hh_core.sqlite (dict_register.md).

**round.** One pass of the sweep over all the envelopes of one household.

**round budget.** The largest number of rounds that a household may run in one sweep.

**rounded.** Taken to the nearest whole dollar. A value exactly halfway between two whole dollars is taken to the one nearer zero.

**segment.** The funding segment of an envelope: consumer, corporate, enterprise or smb.

**shortfall.** The amount by which an envelope's need exceeds its standing balance, or zero when it does not.

**spread.** Of a round, the sum of the absolute values of the gaps of the household's envelopes at the start of that round.

**standing balance.** The balance an envelope holds at the start of the current round. In the opening round it is the pre-sweep balance.

**state.** The list of the balances of a household's envelopes at one moment.

**strike.** A worsening round.

**strike count.** The number of strikes a household has taken since its sweep began or since its most recent halving, whichever is later. A round that is not a strike leaves the count as it was.

**target.** The balance an envelope is steered toward in a round (std_sweep.md).

**transfer.** Of a round, the draft amounts of that round taken together, before the balancing adjustment.

**whole dollars.** Dollar amounts with no cents part.

**worsening round.** A round whose spread is greater than or equal to the spread of the round before it. A household's opening round is never a worsening round.

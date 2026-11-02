# Collection Id Migration Memo, 2023

From the catalogue team to all vault custodians.

1. The old `KCB-` collection ids were retired in the central catalogue at the 2023 cutover.
   All vault exports were to switch to `KC-` ids by the end of that year.
2. `collection_crosswalk.tsv` maps every legacy id to its current id. Most legacy ids map to
   one collection.
3. Where a legacy series was later split, the legacy id maps to two current collections. The
   crosswalk row with the later `effective_from` date belongs to the split series. A replica
   carrying such a legacy id belongs to the crosswalk row whose `effective_from` is the
   latest date on or before the replica's own catalogued date.
4. Vault custodians should expect exports without any legacy ids after March 2024.

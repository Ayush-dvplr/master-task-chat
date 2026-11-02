# VARC1 revision remap

A short key is one byte, a field id in the range 0 to 255. The real meaning of a
short key depends on the segment `revision` in the header. `revision_map.ini` holds
the remap for each revision.

Revisions 0, 1, 2 and 3 are identity revisions: a short key maps to the canonical
field id equal to the key byte itself, so key byte 17 is canonical id 17.

Revisions 4, 5, 6 and 7 remap. Each has a section in `revision_map.ini` named
`[revision_4]` and so on, with one line `raw_key = canonical_id` per short key in
force for that revision. Under these revisions a short key does not equal its
canonical id: key byte 17 under revision 5 is whatever `[revision_5]` says 17 maps
to. Resolve the short key through the revision first, then look the canonical id up
in `field_layouts.csv` and `symbol_table.tsv` for the field name.

Long keys are not affected by the revision. A long key already spells a canonical
field name, so it is looked up by name in `field_layouts.csv` directly.

The revision changes only the field name a short key resolves to. It does not
change the value bytes, the mode, the extensions or anything else in the frame, so
re encoding a frame keeps the same short key byte and the same revision.

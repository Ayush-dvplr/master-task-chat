# Stage r14: Publication, serialisation and digests

Every published document follows
`serialisation_and_digest_contract.md` and the shape
`output_schema_reference.md` gives, header line, column order, row
order, key names and value types.

The equivalence document compares the state a replay from the selected
checkpoint reaches against the state a replay from scratch over the same
end boundary reaches, and publishes the digest of each and whether they
agree.

The verification notes and the defect register are derived documents
like any other: the register is the reason code catalogue filtered to
the codes in force and sorted, and the notes carry the run scalars in
the order the schema gives.

The two digests in the run manifest are taken last, over the bytes
already written.

# Stage p14  the publication

The twenty five documents are written in the shape
`output_schema_reference.md` fixes, under the encoding and the line endings
`serialisation_and_digest_contract.md` fixes. The manifest is written last, of
the twenty four documents before it in the order the schema reference lists
them, each with the digest of the bytes already on disk, and then a line
carrying the digest of those lines. The run writes nothing else into the
destination and leaves the paper directory exactly as it found it.

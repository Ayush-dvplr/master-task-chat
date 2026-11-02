# Kolhapur Catalogue and Index Format

The Kolhapur vault exports each shard as a pair of files with the same shard number:
`kolhapur_catalogue_NN.dat` (fixed width text) and `kolhapur_index_NN.idx` (binary).

## Catalogue lines

One replica per line, columns counted from 1:

| Columns | Width | Field |
|---|---|---|
| 1 to 72 | 72 | object path, padded on the right with spaces |
| 73 to 79 | 7 | sequence number within the shard, zero padded |
| 80 to 90 | 11 | size in 512 byte sectors, rounded up, padded on the left with spaces |
| 91 to 100 | 10 | collection id, padded on the right with spaces |
| 101 | 1 | rendition letter code |
| 102 to 109 | 8 | catalogued date, `YYYYMMDD` |

The sector count is rounded up and is not the exact size of the file. The exact size is in
the index.

## Index file

All integers are unsigned and little endian.

| Offset | Size | Field |
|---|---|---|
| 0 | 6 | magic `KLHIDX` (ASCII) |
| 6 | 2 | format version, currently 3 |
| 8 | 4 | record count |
| 12 | 44 per record | records |

Each record is a 4 byte sequence number, an 8 byte exact size in bytes, and the 32 raw bytes
of the SHA-256 digest. Records are not in sequence order. A record belongs to the catalogue
line with the same sequence number in the catalogue shard with the same shard number.

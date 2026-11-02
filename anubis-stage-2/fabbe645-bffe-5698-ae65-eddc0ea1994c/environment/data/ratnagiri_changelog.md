# Ratnagiri Export Changelog

## Format

One JSON object per line:

| Key | Meaning |
|---|---|
| `p` | object path inside the vault |
| `len` | exact size in bytes, JSON integer |
| `dg` | `SHA256:` followed by the digest in upper case hex |
| `col` | collection id |
| `kind` | rendition in upper case: `MASTER`, `MEZZANINE` or `PROXY` |

## Changes

- Export tool 2.1: `kind` written in upper case. Readers should compare case blind.
- Export tool 2.2: digests carry the `SHA256:` prefix. Strip it before use.
- Export tool 2.3: starting with shard file `ratnagiri_objects_02.jsonl` and in every
  later shard of the same export, the integer `len` key is no longer written. The size is
  written instead as key `len_hex`, a JSON string holding the exact size in lower case
  hexadecimal without any prefix. Shards before that file still carry `len`.

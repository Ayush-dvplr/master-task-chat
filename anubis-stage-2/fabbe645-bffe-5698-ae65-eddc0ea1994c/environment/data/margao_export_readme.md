# Margao Vault Inventory Export

The Margao vault exports its inventory as XML in namespace `urn:kcba:margao:inventory:2`.

## Layout

    <inv:inventory xmlns:inv="urn:kcba:margao:inventory:2" vault="margao" batch="N" records="M">
      <inv:obj path="..." size="..." coll="..." form="..." catalogued="YYYY-MM-DD">
        <inv:digest alg="sha256" enc="CODE">...</inv:digest>
      </inv:obj>
    </inv:inventory>

| Attribute | Meaning |
|---|---|
| `path` | object path inside the vault, XML escaped |
| `size` | exact size in bytes |
| `coll` | collection id; ids starting `KCB-` are legacy ids (see the crosswalk) |
| `form` | rendition: master, mezzanine or proxy |
| `catalogued` | date the replica was catalogued at Margao |

## Digest encodings

The `enc` attribute of `inv:digest` is a short code. The export tool picks the encoding per
batch.

| Code | Encoding |
|---|---|
| `q2` | standard Base64 (RFC 4648 section 4) with `=` padding |
| `k7` | Base32 (RFC 4648 section 6, upper case alphabet) with the trailing `=` padding removed |

Both decode to the 32 raw bytes of the SHA-256 digest. Planning uses the digest as 64 lower
case hex characters.

## Decoder appendix

For code `k7`, add `=` characters to the end of the text until its length is a multiple
of 8, then decode as Base32. A 32 byte digest is 52 Base32 characters and needs 4 padding
characters. For code `q2`, decode as standard Base64. Any other code is an export fault
and must not occur in a published cycle.

# Unit identity

A unit key is `family/flavour`, both lower case. Neither part contains an
underscore or a hyphen.

## Mirror labels

A mirror index names a unit by label. A label is upper case and takes the shape
`FAMILY_FLAVOUR` or `FAMILY_FLAVOUR_SUFFIX`. Only the suffixes registered in
`platform_suffixes.json` are suffixes; the registry is closed. To read a label,
remove a registered trailing suffix if one is present and then split what remains
on its single underscore. A label that still holds more than one underscore, or
none, names no unit and is ignored. Two labels that differ only by registered
suffix name the same unit, and every counting row for that unit is considered
together.

## Content references

A promotion request carries a `content_ref`, not a unit key.
`alias_bindings.csv` binds references to units. A binding counts when it is the
governing record for that reference and its `retired_at` is empty or later than
the decision instant. A binding retired exactly at the decision instant no longer
counts.

When no binding counts, the reference may still be resolved through
`builder_attestations.jsonl`. An attestation that carries the reference and whose
`builder` appears in the trusted builder list of `relay_policy_baseline.json`
resolves the reference through its `source_name`, which is `family-flavour` and is
split on its single hyphen. A `source_name` that holds more than one hyphen
resolves nothing. An attestation signed by a builder outside that list resolves
nothing.

Where more than one trusted attestation carries the same reference, the one whose
`signed_at` is the greatest resolves it. Where two of them share the greatest
`signed_at`, the builder that stands earlier in the precedence list of
`relay_policy_baseline.json` resolves it, and a builder outside that list stands
behind every builder in it.

A reference that no route resolves is unresolved and the request carries the
matching code.

## Normative parameters

```
unit_separator: /
source_name_separator: -
label_separator: _
attestation_rank: signed_at_desc,builder_precedence
boundary_source: boundary_semantics.json
```

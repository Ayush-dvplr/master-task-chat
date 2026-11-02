# Entity resolution

Records quote holders in several forms. A quoted form resolves to a holder key
through the following steps, applied in order, stopping at the first step that
yields exactly one holder.

1. A form matching the holder key pattern is the key itself.
2. A form present in legacy_code_crosswalk.tsv resolves through that crosswalk.
3. A form present in inbox_handle_registry.csv resolves through that registry.
4. A form whose normalised text equals the normalised text of an alias form in
   counterparty_alias_map.csv resolves to the holder that alias names.
5. A form whose normalised text equals the normalised legal name of a holder in
   counterparty_directory.csv resolves to that holder.

Normalised text is produced by folding letter case, replacing an ampersand with
the word and, replacing every character that is neither a letter nor a digit with
a single space, collapsing runs of spaces, trimming the ends, and then repeatedly
removing a trailing legal suffix while one is present.

| legal suffix |
| --- |
| and sons |
| associates |
| company |
| cooperative |
| corporation |
| foundation |
| group |
| holdings |
| incorporated |
| limited |
| partners |
| partnership |
| society |
| trust |

A holder counts as suffix resolved when at least one form quoted for it anywhere
in the corpus matched a holder only after a trailing legal suffix was removed,
whether or not some other form of the same holder matched without stripping.

Pledge references appear in raw forms as well. A raw pledge reference resolves by
folding letter case, replacing every character that is neither a letter nor a
digit with a single space, trimming the ends, collapsing runs of spaces, and then
reading the digits as the numeric part of a pledge identifier. A series instance
reference keeps the series identifier and the period label joined by a hash.

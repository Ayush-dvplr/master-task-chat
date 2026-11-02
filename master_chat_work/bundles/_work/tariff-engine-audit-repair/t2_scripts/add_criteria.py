from pathlib import Path
p = Path("test_output.src.py"); s = p.read_text()
anchor = '@criterion(description="With input files deleted the command names the first missing one, prints nothing and exits 2")'
assert s.count(anchor) == 1 and "revision_accounts_on" not in s
sets3 = [("fresh_rescaled", "('fresh', 'rescaled')", "the fresh and rescaled corpora"),
         ("relocated_rotated", "('relocated', 'rotated')", "the relocated and rotated corpora"),
         ("api_recoded_renamed", "('api', 'recoded', 'renamed')", "the api, recoded and renamed corpora")]
sets2 = [("fresh_rescaled_relocated_rotated", "('fresh', 'rescaled', 'relocated', 'rotated')", "the fresh, rescaled, relocated and rotated corpora"),
         ("api_recoded_renamed", "('api', 'recoded', 'renamed')", "the api, recoded and renamed corpora")]
spec = [
 ("revision_accounts", "revision", "Invoices of accounts on plans with revisions are exact on", sets3),
 ("revision_row_accounts", "revision_rows", "Invoices of accounts with several billing rows on plans with revisions are exact on", sets2),
 ("arrears_accounts", "arrears", "Invoices of accounts with paid amounts on several billing rows are exact on", sets3),
 ("arrears_carried_accounts", "arrears_carried", "Invoices of accounts with paid amounts and allowance moved to a later row are exact on", sets2),
 ("cumulative_read_accounts", "cumulative", "Invoices and exceptions of accounts with cumulative reads are exact on", sets3),
 ("cumulative_row_accounts", "cumulative_rows", "Invoices and exceptions of accounts with cumulative reads on several billing rows are exact on", sets2[:1] + [("all_others", "('api', 'recoded', 'renamed')", "the api, recoded and renamed corpora")][:0]),
]
spec[-1] = ("cumulative_row_accounts", "cumulative_rows", "Invoices and exceptions of accounts with cumulative reads on several billing rows are exact on", [sets3[0][:0] or ("on_all", "('fresh', 'rescaled', 'relocated', 'rotated', 'api', 'recoded', 'renamed')", "every hidden corpus")])
spec.append(("cumulative_meter_row_accounts", "cumulative_meter_rows", "Invoices and exceptions of accounts with cumulative reads on meters with several account rows are exact on", [("on_all", "('fresh', 'rescaled', 'relocated', 'rotated', 'api', 'recoded', 'renamed')", "every hidden corpus")]))
blocks, weights = [], []
for stem, group, desc, sets in spec:
    for suffix, tup, words in sets:
        name = f"{stem}_{suffix}" if suffix.startswith("on_") else f"{stem}_on_{suffix}"
        blocks.append(f'@criterion(description="{desc} {words}")\ndef {name}(workspace: Path) -> bool:\n    return _holds(lambda: _check_owned("{group}", {tup}))\n\n\n')
        weights.append(f"criteria.{name}(weight=5)\n")
s = s.replace(anchor, "".join(blocks) + anchor)
wanchor = "criteria.missing_source_is_named(weight=3)\n"
assert s.count(wanchor) == 1
s = s.replace(wanchor, "".join(weights) + wanchor)
p.write_text(s)
print(len(weights), "criteria added")

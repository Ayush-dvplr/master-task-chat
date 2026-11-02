| finding id | file:line | reason | kit line it rests on |
|---|---|---|---|
| TS-23 | tests/test_output.py (45 registered checks) | KEEP with count, no count cap; each check reads its own corpus/document, no true duplicate | 03_Tests_QC.md:62 |
| JD-16 | tests/judge.toml:209 (R16); task.toml:2, task.toml:24 | verifier has no /app/data (artifacts only /app/out, separate verifier), so the judge owns undeclared-path scope | 04_Judge_QC.md:93 item 4 |
| oracle x3 | QC v1 result_03ec0bf.json | oracle run x3 instead of x5, acknowledged by Ayush | kit oracle repeat count (acknowledged deviation) |

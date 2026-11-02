"""Write harden_r2 OUT/agent_program/adapted/cli.py: the probe-1 solver's cli.py with one edit, the
override_allowance lookup keyed by the region of the tenant in tenant_catalog.xml instead of the tenant id.
Every other reading the solver made is kept (own-tenant rows only, unit from rev, no window admits).
"""
from pathlib import Path

OUT = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/20261023_sentinel-policy-recompute/harden_r2/agent_program")
src = (OUT / "tool" / "cli.py").read_text()
old = '    allowance = int(read_ini_sections(consume("quota_limits.cfg"))["override_allowance"][tenant])\n'
new = ('    regions = {t["id"]: t["region"] for t in read_xml_records(consume("tenant_catalog.xml"), "tenant")}\n'
       '    allowance = int(read_ini_sections(consume("quota_limits.cfg"))["override_allowance"][regions[tenant]])\n')
assert src.count(old) == 1
src = src.replace(old, new)
(OUT / "adapted").mkdir(exist_ok=True)
(OUT / "adapted" / "cli.py").write_text(src)
print("wrote", OUT / "adapted" / "cli.py")

"""edit_grade2.py <t.py>: altered-config check also audits; strict compare in tier and conv profile matches."""
import sys
from pathlib import Path

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")
EDITS = [
    ('def everything(root, conv=None):\n    """Return (config, profiles, audit, summary) documents for a corpus directory."""\n'
     '    D = load(root)\n    cfg, jrej, jtally = settle_config(D)\n',
     'def everything(root, conv=None, config=None):\n    """Return (config, profiles, audit, summary) documents for a corpus directory."""\n'
     '    D = load(root)\n    cfg, jrej, jtally = settle_config(D)\n    if config is not None:\n        cfg = config\n'),
    ('    return got["dev"] == exp[1]["dev"] and got["prod"] == exp[1]["prod"]\n',
     '    return _same(got["dev"], exp[1]["dev"]) and _same(got["prod"], exp[1]["prod"])\n'),
    ('    return got[env] == exp[1][env]\n',
     '    return _same(got[env], exp[1][env])\n'),
    ('        W = World(load(root), cfg)\n'
     '        exp = {env: {k: utc(v) for k, (v, _) in sorted(W.profile(env)["keys"].items())} for env in ("dev", "prod")}\n',
     '        _, profiles, audit, _, _ = everything(root, None, cfg)\n'
     '        exp = {"dev": profiles["dev"], "prod": profiles["prod"], "audit": audit}\n'),
    ('            got[env] = _read_json(target) if rc == 0 else None\n        return got, exp\n',
     '            got[env] = _read_json(target) if rc == 0 else None\n'
     '        target = out / "audit.json"\n'
     '        rc = _invoke(["audit", "--data", str(root), "--config", str(path), "--out", str(target)])\n'
     '        got["audit"] = _read_json(target) if rc == 0 else None\n        return got, exp\n'),
    ('@criterion(description="the delivered tool compiles unseen corpus tier_b under a --config with earlier anchors and another prod approvals_required, as recomputed")\n'
     'def altered_config_profiles_exact(workspace: Path) -> bool:\n'
     '    try:\n        got, exp = _altered()\n'
     '        return all(_same(got[env], exp[env]) for env in ("dev", "prod"))\n',
     '@criterion(description="the delivered tool compiles and audits unseen corpus tier_b under a --config with earlier anchors and another prod approvals_required, as recomputed")\n'
     'def altered_config_outputs_exact(workspace: Path) -> bool:\n'
     '    try:\n        got, exp = _altered()\n'
     '        if not all(_same(got[env], exp[env]) for env in ("dev", "prod")):\n            return False\n'
     '        doc, ref = got["audit"], exp["audit"]\n'
     '        if not isinstance(doc, dict) or set(doc) != set(ref):\n            return False\n'
     '        return all(_rows(doc[k]) == _rows(ref[k]) for k in ref if k != "self_check") and _same(doc["self_check"], ref["self_check"])\n'),
    ('criteria.altered_config_profiles_exact(', 'criteria.altered_config_outputs_exact('),
]
MULTI = {'    return got["dev"] == exp[1]["dev"] and got["prod"] == exp[1]["prod"]\n': 2}
for old, new in EDITS:
    n = s.count(old)
    if n != MULTI.get(old, 1):
        sys.exit(f"edit not unique ({n}): {old[:70]!r}")
    s = s.replace(old, new)
p.write_text(s, encoding="utf-8")
print(f"applied {len(EDITS)} edits")

"""stage1.py + final environment/data -> final tests/test_output.py (conv tiers, 16 checks, shipped blob)."""
import base64
import json
import re
import sys
import zlib
from pathlib import Path

SRC, DATA, DST = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
text = SRC.read_text(encoding="utf-8")


def sub(old, new):
    global text
    assert text.count(old) == 1, old[:80]
    text = text.replace(old, new)


# shipped blob from the final data directory
m = re.search(r"\nSHIPPED_NAMES = (\[.*?\])\n", text)
names = json.loads(m.group(1))
start = text.index("SHIPPED_CORPUS = (\n")
end = text.index("\n)\n", start) + 3
old_files = json.loads(zlib.decompress(base64.b64decode(
    "".join(re.findall(r'"([^"]*)"', text[start:end])))).decode("utf-8"))
files = {}
for name in old_files:
    files[name] = (DATA / name).read_bytes().decode("utf-8")
print("blob names not shipped as text:", sorted(set(names) - set(old_files)))
changed = sorted(n for n in files if files[n] != old_files[n])
blob = base64.b64encode(zlib.compress(json.dumps(files, sort_keys=True).encode("utf-8"), 9)).decode("ascii")
lines = ["SHIPPED_CORPUS = ("] + ['    "%s"' % blob[i:i + 100] for i in range(0, len(blob), 100)] + [")"]
text = text[:start] + "\n".join(lines) + "\n" + text[end:]

sub('''                 ("tier_c", 73031, 0.04, "boundary"))
''', '''                 ("tier_c", 73031, 0.04, "boundary"))
CONV_TIERS = (("conv_1", 91019, "Site/Dune"), ("conv_2", 85041, "Site/Dune"), ("conv_3", 93029, "Site/Ember"),
              ("conv_4", 96043, "Site/Cobalt"), ("conv_5", 92023, "Site/Brisk"), ("conv_6", 98053, "Site/Brisk"),
              ("conv_7", 94031, "Site/Arden"), ("conv_8", 99061, "Site/Arden"))
''')

sub('''def _tool_dir() -> Path | None:
''', '''def _conv_tier(name: str) -> Path | None:
    def build_one():
        for tier, seed, zone in CONV_TIERS:
            if tier == name:
                root = _scratch(f"warrant-{tier}-")
                build(root, seed, 0.05, "conv", {"hr": "zone:" + zone, "start": "requested"})
                _open_tree(root)
                return root
        return None
    return _cached(("tier", name), build_one)


def _expected_conv(name: str):
    def build_one():
        root = _conv_tier(name)
        zone = dict((tier, z) for tier, _, z in CONV_TIERS)[name]
        cfg, profiles, audit, summary, _ = everything(root, {"hr": "zone:" + zone, "start": "requested"})
        return cfg, profiles
    return _cached(("expected", name), build_one)


def _conv_profile_match(tier: str, env: str) -> bool:
    got, exp = _run_all(_conv_tier(tier), tier), _expected_conv(tier)
    return got[env] == exp[1][env]


def _tool_dir() -> Path | None:
''')

checks = []
regs = []
for n in range(1, 9):
    for env in ("dev", "prod"):
        checks.append(f'''@criterion(description="the delivered tool compiles the {env} profile of unseen corpus conv_{n} exactly as recomputed")
def conv_{n}_{env}_profile_exact(workspace: Path) -> bool:
    try:
        return _conv_profile_match("conv_{n}", "{env}")
    except Exception:
        return False


''')
        regs.append(f"criteria.conv_{n}_{env}_profile_exact(weight=5)\n")
sub("def _universe(tier: str) -> set:\n", "".join(checks) + "def _universe(tier: str) -> set:\n")
assert text.endswith("criteria.negative_legacy_tool_delivered(weight=-1)\n")
text += "".join(regs)
DST.write_text(text, encoding="utf-8")
print("changed shipped files:", changed)

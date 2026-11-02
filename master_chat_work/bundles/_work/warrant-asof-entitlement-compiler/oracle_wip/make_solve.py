"""make_solve.py <solve.py in> <solve.py out>: append the convention edits of conv_edits.py to solve.py's FIXES."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import conv_edits  # noqa: E402

DEFECTS = [
    "MFA log lines whose instant is unreadable were dropped instead of being rejected bad_timestamp.",
    None,
    None,
    None,
    "HR effective dates were read on one fixed clock instead of the clock the corpus's gateway observations show.",
    "Contract cover was read on one fixed clock instead of the clock the corpus's gateway observations show.",
    None,
    "Grant start always waited for the approvals instead of following the start the corpus's gateway observations show.",
    None,
    "Grant windows were always half open instead of following the boundary the corpus's gateway observations show.",
    None,
    "Key values equal to as_of were always dropped instead of following the boundary the corpus's gateway observations show.",
    "Gateway conventions were hard coded instead of being settled from the corpus's own observations.",
    None,
]
assert len(DEFECTS) == len(conv_edits.EDITS)

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
text = src.read_text(encoding="utf-8")
anchor = "\n]\n\n\ndef extract() -> None:\n"
assert text.count(anchor) == 1
rows = "".join(f"    ({m!r},\n     {old!r},\n     {new!r},\n     {d!r}),\n"
               for (m, old, new), d in zip(conv_edits.EDITS, DEFECTS))
literal = "'''" + conv_edits.GATEWAY + "'''"
assert eval(literal) == conv_edits.GATEWAY
gateway = "\nGATEWAY = " + literal + "\n"
text = text.replace(anchor, "\n" + rows.rstrip("\n") + "\n]\n" + gateway + "\n\ndef extract() -> None:\n")
old_rep = ('        path.write_text(text.replace(legacy, fixed), encoding="utf-8")\n'
           '        done.append({"module": module, "defect": defect})\n'
           '    return sorted(done')
new_rep = ('        path.write_text(text.replace(legacy, fixed), encoding="utf-8")\n'
           '        if defect is not None:\n'
           '            done.append({"module": module, "defect": defect})\n'
           '    (TOOL / "gateway.py").write_text(GATEWAY, encoding="utf-8")\n'
           '    return sorted(done')
assert text.count(old_rep) == 1
text = text.replace(old_rep, new_rep)
dst.write_text(text, encoding="utf-8")

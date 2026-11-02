#!/usr/bin/env python3
"""6cd567a: rebuild QC v6 AL-27 mutants M10, M11, M16 and the TS-16 input-dir cheat
from trap/variants/oracle.py (the host-safe oracle copy written by grade_local.variants())."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = (HERE.parent / "trap/variants/oracle.py").read_text()

MUTANTS = {
    # M10: log entries above the cutoff are applied
    "m10_logabove": [("        if seq > cutoff:\n            continue\n        action = ",
                      "        action = ")],
    # M11: a trailing restore revives a row whose own void field is 1
    "m11_restorevoid": [
        ("    state = {}\n    for uid, evs in events.items():\n        evs.sort()\n"
         "        state[uid] = evs[-1][3] == \"void\"\n",
         "    state = {}\n    for uid, evs in events.items():\n        evs.sort()\n"
         "        state[uid] = evs[-1][3] == \"void\"\n"
         "        if not state[uid]:\n            RESTORED.add(uid)\n"),
        ("def rhu(num: int, den: int) -> int:", "RESTORED = set()\n\n\ndef rhu(num: int, den: int) -> int:"),
        ('to_int(get(row, "void") or 0) == 1',
         '(to_int(get(row, "void") or 0) == 1 and str(get(row, "row_uid")).strip() not in RESTORED)'),
    ],
    # M16: negative halves round toward +infinity
    "m16_neghalf": [("    return -((-2 * num + den) // (2 * den))",
                     "    return (2 * num + den) // (2 * den)")],
}


def main():
    for name, repls in MUTANTS.items():
        text = SRC
        for old, new in repls:
            n = text.count(old)
            if n < 1 or (n != 1 and "void\") or 0) == 1" not in old):
                raise SystemExit(f"{name}: {n} matches for {old[:60]!r}")
            text = text.replace(old, new)
        (HERE / f"{name}.py").write_text(text)
        print(name, "written")
    # TS-16: honest oracle that also drops a scratch file into its input directory
    marker = "def _main("
    if SRC.count(marker) != 1:
        raise SystemExit("main marker")
    cheat = SRC.replace(marker, (
        "def _scratch_in_input():\n"
        "    import sys as _s\n"
        "    try:\n"
        "        (Path(_s.argv[1]) / '.scratch_cache').write_text('x\\n')\n"
        "    except OSError:\n"
        "        pass\n\n\n" + marker), 1)
    cheat = cheat.replace("if __name__ == \"__main__\":\n", "if __name__ == \"__main__\":\n    _scratch_in_input()\n", 1)
    if "_scratch_in_input()\n" not in cheat.split("if __name__")[-1]:
        raise SystemExit("cheat hook")
    (HERE / "ts16_cheat_input.py").write_text(cheat)
    print("ts16_cheat_input written")


if __name__ == "__main__":
    main()

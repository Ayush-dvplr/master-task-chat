"""Second method against the reference on the shipped book and 300 generated images.

For every recovered image three things are compared with bookgen.recover:
  1. slot values against the generator's forward truth (genesis plus the net
     deltas of every committed transaction), which never runs recovery;
  2. the whole page image against the closed form of solve.py (disk plus every
     change newer than the disk page, minus each loser's net effect);
  3. the appended records against the list rebuilt from uncompensated loser
     updates in descending LSN order.
Each image is rendered to files and parsed back by solve.read_book, so the
file formats are exercised as well. The first differing record is printed.
Also asserts the generator bounds and that every dense image carries every
DENSE_NEEDS case. Usage: python3 -B check_exact.py [count]
"""
import importlib.util
import sys
import tempfile
import time
from pathlib import Path

import bookgen as bg

WORK = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "solve", WORK.parent.parent / "counter-page-crash-recovery" / "solution" / "solve.py")
solve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(solve)


def first_diff(want, got, path="$"):
    if type(want) is not type(got):
        return path
    if isinstance(want, dict):
        for k in sorted(set(want) | set(got), key=str):
            if k not in want or k not in got:
                return f"{path}.{k}"
            d = first_diff(want[k], got[k], f"{path}.{k}")
            if d:
                return d
        return None
    if isinstance(want, list):
        for i, (a, b) in enumerate(zip(want, got)):
            d = first_diff(a, b, f"{path}[{i}]")
            if d:
                return d
        return None if len(want) == len(got) else f"{path}.length"
    return None if want == got else path


def check_book(book, label, dense=False):
    bad = 0
    with tempfile.TemporaryDirectory() as tmp:
        for name, blob in bg.render_book(book, bg.Rng(7)).items():
            (Path(tmp) / name).write_bytes(blob)
        parsed = solve.read_book(Path(tmp))
    for img in book["images"]:
        assert len(img["pages"]) <= bg.LIMIT_PAGES
        assert sum(r["type"] != "x" for r in img["records"]) <= bg.LIMIT_RECORDS
        assert all(bg.SLOT_RANGE[0] <= n <= bg.SLOT_RANGE[1] for n in img["pages"].values())
        if dense:
            f = bg.features(img)
            assert all(f[k] > 0 for k in bg.DENSE_NEEDS), (label, img["id"], f)
        res = bg.recover(img)
        if res["status"] != "recovered":
            continue
        truth = {p: v for p, v in img["truth"].items()} if "truth" in img else None
        if truth is not None:
            slots = {p: st["slots"] for p, st in res["pages"].items()}
            if slots != truth:
                bad += 1
                print(label, img["id"], "truth", first_diff(truth, slots))
                continue
        entry = parsed[img["id"]]
        form = solve.closed_form(entry, res["appended"])
        if form != res["pages"]:
            bad += 1
            print(label, img["id"], "closed form", first_diff(form, res["pages"]))
            continue
        rebuilt = solve.expected_appended(entry)
        if rebuilt != res["appended"]:
            bad += 1
            print(label, img["id"], "appended", first_diff(rebuilt, res["appended"]))
    return bad


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    t0 = time.time()
    total_bad = check_book(bg.shipped_book(806610), "shipped")
    done = 0
    profiles = ("light", "dense", "restart", "max")
    seed = 1000
    while done < count:
        prof = profiles[seed % 4]
        dense = prof != "light"
        book = bg.build_book(seed, prof, 3, dense=dense, light=not dense,
                             min_restarts=2 if dense else 0)
        total_bad += check_book(book, f"{prof}:{seed}", dense)
        done += len(book["images"])
        seed += 1
    print(f"images {done} + shipped, mismatches {total_bad}, {time.time() - t0:.1f}s")
    print("ALL_DONE")


if __name__ == "__main__":
    main()

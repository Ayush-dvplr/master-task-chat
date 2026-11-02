"""Write a 4-set book at the contract bounds (160 jobs, 24 workers, events near 1200, horizon 5000)."""
import sys, pathlib
HERE = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(HERE / "engine"), str(HERE)]
import gen, datagen
prof = dict(gen.PROFILES["hidden"])
prof.update(jobs=(160, 160), workers=(24, 24), events=(1100, 1150), cps=(20, 20), horizon=(5000, 5000), work=(40, 60))
gen.PROFILES["bounds"] = prof
book = gen.make_book(4242, "bounds", 4)
out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
datagen.write_book(book, out, 4242, 0)
for sid, s in book["sets"].items():
    print(sid, len(s["jobs"]), len(s["workers"]), len(s["events"]), max(s["checkpoints"]))

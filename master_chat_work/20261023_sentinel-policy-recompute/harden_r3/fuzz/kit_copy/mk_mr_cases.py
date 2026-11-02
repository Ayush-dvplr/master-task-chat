import json, random
rng = random.Random(840)
TAGS = ["deepchain","cap","emptycharter","boundary","degenerate","deadwindow","reversalflip","population","scale","tiebreak","partition","newunit","donorretire","split"]
BITS = [1<<i for i in range(12)]
CLASSES = ["peak","steady","burst","latency"]
CAND = {"frame_bias_limit": (4,15),"weave_seed_offset": (17,30),"sentinel_code_value": (200,215),"drift_modulus": (5,16),"seal_label_index": (0,11),"spin_modulus": (7,18),"shadow_pad_base": (3,14),"alias_donor_shift": (1,10),"echo_window_span": (2,13),"cadence_modulus": (2,11),"upkeep_target_scale": (11,22)}
knobs = [None] + TAGS + [["only", b] for b in BITS] + [["class", c] for c in CLASSES] + [["value","cadence_modulus",7]]
cases = []
def add(p, tweak, struct="none"):
    cases.append({"id": "%s-%03d" % (p, len(cases)), "profile": p, "seed": rng.randrange(100000, 999999), "tweak": tweak, "struct": struct})
for i in range(150):
    add("P1", knobs[i % len(knobs)])
edge = []
for pin, (lo, hi) in CAND.items():
    for v in (lo, hi):
        edge.append(["value", pin, v])
edge += [["only", 0x0FFF]] * 6 + ["boundary", "tiebreak", "degenerate", "deadwindow", "emptycharter", "population", "cap", "split", "donorretire", "reversalflip"] * 5
for k in edge:
    add("P2", k)
for i in range(84):
    add("P3", knobs[i % len(knobs)], ["renamed", "cwd", "shuffle"][i % 3])
with open("mr_cases.jsonl", "w") as f:
    for c in cases:
        f.write(json.dumps(c) + "\n")
print(len(cases), {p: sum(c["profile"] == p for c in cases) for p in ("P1","P2","P3")})

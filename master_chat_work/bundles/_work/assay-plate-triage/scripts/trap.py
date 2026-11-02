"""Trap baseline and survival: score single-lever wrong-reading variants (WORK helper).

usage: python3 -B trap.py ORACLE_TRIAGE_PY OUTFILE
For each lever variant: points lost on the original tests (QC copy df9f49f) and on the
fixed tests, plus how many shipped digests the variant fails before the fix (manifest.json,
trial_manifest.json) and after (plus bits/*.json).
"""
import json, os, re, shutil, subprocess, sys, tempfile, glob, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
B = "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/assay-plate-triage"
OLD = "/Users/mac/Desktop/Terminal Bench/QC/copies/df9f49f/assay-plate-triage/tests/test_output.py"
NEW = B + "/tests/test_output.py"
DATA = B + "/environment/data"

oracle = open(sys.argv[1]).read()
outfile = sys.argv[2]

NAMES = ["inherit_blank", "deferred_charge", "prior_operator_role", "tier_band_lift",
         "min_exposure", "odd_replicates_elisa", "island_offset", "exposure_walk",
         "mask_forgives", "tail_trim", "matrix_rotation", "neighbour_strikes"]
LEVER_OF = ["L01 chain_blank", "L02 drift_echo", "L03 role_lookback", "L04 band_tier_shift",
            "L05 exposure_floor", "L06 panel_parity", "L07 baseline_delta", "L08 exposure_order",
            "L09 mask_absolves", "L10 count_bias", "L11 matrix_alias", "L12 quarantine_span"]

variants = []
for name, lever in zip(NAMES, LEVER_OF):
    src, n = re.subn(r"\n    '%s': 0x[0-9a-f]+," % name, "", oracle)
    assert n == 1, name
    variants.append((lever + " (bit ignored)", src))
src, n = re.subn(r"ALTERATION_BITS = \{.*?\n\}", "ALTERATION_BITS = {}", oracle, flags=re.S)
assert n == 1
variants.append(("L13 trap_blind (mode word ignored)", src))
src = oracle.replace("+ plate[\"tier\"] + operator_count", "+ plate[\"tier\"] + 5")
assert src != oracle
variants.append(("L14 alias_count (operator count fixed at shipped 5)", src))
src = oracle.replace("(1 + len(run[\"plates\"]) % 4)", "2")
assert src != oracle
variants.append(("L15 bias_count (tail fixed at shipped 2)", src))

if len(sys.argv) > 3 and sys.argv[3] == "perm":
    # L16 bit identity: every alteration kept, wired to the wrong bit.
    table = re.search(r"ALTERATION_BITS = \{.*?\n\}", oracle, flags=re.S).group(0)
    bits = re.findall(r"'(\w+)': (0x[0-9a-f]+),", table)
    def rewire(order):
        body = "".join("\n    '%s': %s," % (bits[i][0], bits[order[i]][1]) for i in range(12))
        return oracle.replace(table, "ALTERATION_BITS = {" + body + "\n}")
    variants = [("L16 bit_identity rotate %d" % k, rewire([(i + k) % 12 for i in range(12)])) for k in (1, 6)]
    for a, b in ((0, 1), (9, 10), (8, 11)):
        order = list(range(12)); order[a], order[b] = b, a
        variants.append(("L16 bit_identity swap %s/%s" % (bits[a][0], bits[b][0]), rewire(order)))


def score(prog, tests):
    r = subprocess.run([sys.executable, "-B", os.path.join(HERE, "score.py"), prog, tests],
                       capture_output=True, text=True, cwd=HERE)
    total = int(re.search(r"TOTAL (\d+)/90", r.stdout).group(1))
    lost = re.search(r"LOST (.*)", r.stdout).group(1)
    return 90 - total, lost


def shipped_fails(prog, with_bits):
    runs = [("", DATA + "/manifest.json"), ("trial_", DATA + "/trial_manifest.json")]
    if with_bits:
        runs += [("", p) for p in sorted(glob.glob(DATA + "/bits/0x*_manifest.json"))]
    fails = 0
    for prefix, man in runs:
        root = tempfile.mkdtemp()
        d, o = root + "/d", root + "/o"
        os.makedirs(d); os.makedirs(o)
        for f in ("instruments.csv", "panels.csv", "operators.csv", "plates.csv", "reads.jsonl"):
            shutil.copy(DATA + "/" + prefix + f, d + "/" + f)
        shutil.copy(man, d + "/manifest.json")
        want = json.load(open(man))
        subprocess.run([sys.executable, "-B", prog, d, o], capture_output=True)
        try:
            lines = open(o + "/readings.jsonl").read().splitlines(keepends=True)
            plates = json.load(open(o + "/plates.json"))["plates"]
            body = open(o + "/readings.jsonl").read() + open(o + "/plates.json").read() + open(o + "/bench.json").read()
        except Exception:
            fails += len(want["plate_digests"]) + 1
            continue
        for row in plates:
            pid = row["plate"]
            text = "".join(l for l in lines if json.loads(l)["plate"] == pid) + json.dumps(row, sort_keys=True, indent=2) + "\n"
            if hashlib.sha256(text.encode()).hexdigest() != want["plate_digests"].get(pid):
                fails += 1
        if hashlib.sha256(body.encode()).hexdigest() != want["run_digest"]:
            fails += 1
        shutil.rmtree(root)
    return fails


rows = []
for label, src in [("oracle", oracle)] + variants:
    fd, prog = tempfile.mkstemp(suffix=".py")
    os.write(fd, src.encode()); os.close(fd)
    old_loss, old_lost = score(prog, OLD)
    new_loss, new_lost = score(prog, NEW)
    rows.append({"lever": label, "before_loss": old_loss, "after_loss": new_loss,
                 "digest_fails_before_fix": shipped_fails(prog, False),
                 "digest_fails_after_fix": shipped_fails(prog, True),
                 "lost_after": new_lost})
    print(rows[-1], flush=True)
json.dump(rows, open(outfile, "w"), indent=1)

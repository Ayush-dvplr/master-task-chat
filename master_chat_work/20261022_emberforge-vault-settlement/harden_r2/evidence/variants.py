"""Differential check: which graded observables each single wrong reading moves.
Builds variant graders by text substitution on test_output.py (scratch only)."""
import sys, types, json, pathlib, tempfile
SRC = pathlib.Path(sys.argv[1]).read_text()
sys.path.insert(0, str(pathlib.Path(sys.argv[1]).parent))

SUBS = {
 "W1_floor_or_retired_skips_cap": [(
  """                if e["workshop_id"] in closed:
                    codes.append(("CAP_REACHED", e["workshop_id"]))
                else:""",
  """                if e["workshop_id"] in closed:
                    codes.append(("CAP_REACHED", e["workshop_id"]))
                elif short or gone:
                    pass
                else:""")],
 "W7_closed_gives_cap_only": [(
  """                if short:
                    codes.append(("STOCK_FLOOR", short[0]))
                if gone:""",
  """                if short and e["workshop_id"] not in closed:
                    codes.append(("STOCK_FLOOR", short[0]))
                if gone and e["workshop_id"] not in closed:""")],
 "W2_retired_is_early_refusal": [(
  """                codes: list[tuple[str, str]] = []
                charge = 0
""",
  """                codes: list[tuple[str, str]] = []
                charge = 0
                if gone:
                    run_findings.append({"entry_id": eid, "code": "RETIRED_REAGENT", "detail": gone[0]})
                    state["code"] = "RETIRED_REAGENT"
                    continue
""")],
 "W2b_retired_returns_held_back": [(
  """                    back = quantise(b["units_per_craft"] * src["units"] * rate, 100, q)""",
  """                    back = quantise(b["units_per_craft"] * src["units"] * rate, 100, q)
                    if rid in retired_from and day >= retired_from[rid]:
                        back = 0""")],
 "W2c_detail_last_retired": [(
  """codes.append(("RETIRED_REAGENT", gone[0]))""",
  """codes.append(("RETIRED_REAGENT", gone[-1]))""")],
 "W3_consumed_is_settled_only": [(
  """            return consumed_all.get(rid, 0)""",
  """            return consumed_all.get("__settled__" + rid, 0)""") , (
  """                for rid, n in need.items():
                    stock[rid] -= n""",
  """                for rid, n in need.items():
                    consumed_all["__settled__" + rid] = consumed_all.get("__settled__" + rid, 0) + n
                    stock[rid] -= n""")],
 "W3b_consumed_counts_every_edition": [(
  """            if bom is None or eid in blocked:
                state["code"] = "BLOCKED"
                continue""",
  """            if bom is not None and e["op"] == "forge":
                for b in bom:
                    consumed_all["__any__" + b["reagent_id"]] = consumed_all.get("__any__" + b["reagent_id"], 0) + b["units_per_craft"] * e["units"]
            if bom is None or eid in blocked:
                state["code"] = "BLOCKED"
                continue"""), (
  """            return consumed_all.get(rid, 0)""",
  """            return consumed_all.get("__any__" + rid, 0)""")],
 "WD_window_counts_same_day": [(
  """                    and f["day"] < day
                ]""",
  """                    and f["day"] <= day
                ]""")],
}

def make(name, subs):
    src = SRC
    for old, new in subs:
        assert src.count(old) == 1, (name, old[:60])
        src = src.replace(old, new)
    m = types.ModuleType("v_" + name); m.__file__ = sys.argv[1]
    sys.modules["v_" + name] = m
    exec(compile(src, name, "exec"), m.__dict__)
    return m

import test_output as T
variants = {k: make(k, v) for k, v in SUBS.items()}
seasons = ["visible"] + list(T.SEASONS)
OBS = {
 "settlement": T._obs_settlement, "findings_and_workshops": T._obs_findings_workshops,
 "guilds_and_allocation": T._obs_guilds_allocation,
 "findings": T._obs_findings, "workshop_figures": T._obs_workshop_figures, "vault": T._obs_vault,
 "guilds": T._obs_guilds, "allocation": T._obs_allocation, "smith_rows": T._obs_smith_rows,
}
GRADED = {s: ["settlement", "findings_and_workshops", "guilds_and_allocation"] for s in T.MIXED_SEASONS}
GRADED.update({"cl_priority": ["allocation"], "cl_cap": ["workshop_figures"], "cl_partition": ["guilds"],
  "cl_temporal": ["vault"], "cl_identity": ["smith_rows"], "cl_quiet": ["findings"], "ld12": ["allocation"]})
W = {s: 5 for s in T.MIXED_SEASONS}; W.update({s: 3 for s in GRADED if s not in T.MIXED_SEASONS})
result = {}
corpora = {}
for s in seasons:
    root = pathlib.Path(tempfile.mkdtemp()); d = root / "data"
    if s == "visible":
        T._build_corpus_dir(d); params = T.TRUE
    else:
        seed, params, mut = T.SEASONS[s]; T._build_corpus_dir(d, params=params, mutate=mut, main_seed=seed)
    corpora[s] = (d, params)
total = 5 + sum(W[s] * len(GRADED[s]) for s in GRADED)
print("positive total", total)
for vname, V in list(variants.items()) + [("WT_hardcoded_true_draw", None)]:
    lost = 0; detail = {}
    for s, (d, params) in corpora.items():
        corp = T.load(d, "")
        want = T.settle(corp, params)
        try:
            got = V.settle(T.load(d, ""), params) if V else T.settle(T.load(d, ""), T.TRUE)
        except Exception as ex:
            got = None
        if s == "visible":
            obsk = ["settlement", "findings_and_workshops", "guilds_and_allocation"]
        else:
            obsk = GRADED[s]
        moved = [k for k in obsk if got is None or not T._same(OBS[k](got), OBS[k](want))]
        if moved: detail[s] = moved
        if s != "visible":
            lost += W[s] * len(moved)
    result[vname] = {"score": round((total - lost) / total, 4), "moved": detail}
    print(vname, result[vname]["score"], json.dumps(detail))
json.dump(result, open(sys.argv[2], "w"), indent=1)

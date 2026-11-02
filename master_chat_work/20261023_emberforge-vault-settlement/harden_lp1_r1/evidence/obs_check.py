import sys, pathlib, tempfile, json
from tk import load_T
B = pathlib.Path(sys.argv[1]); T = load_T(B)
def run(name):
    seed, params, mut = T.SEASONS[name]
    d = pathlib.Path(tempfile.mkdtemp()) / "data"
    T._build_corpus_dir(d, params=params, mutate=mut, main_seed=seed)
    return T.settle(T.load(d, ""), params)
b, f, g = run("mut_base"), run("mut_family"), run("mut_grade")
for n, m in (("family", f), ("grade", g)):
    print(n, "vault same:", T._same(m["vault_audit.json"], b["vault_audit.json"]), "ledger moved:", not T._same(T._obs_charge_ledger(m), T._obs_charge_ledger(b)),
          "other docs same:", [k for k in b if not k.startswith(("workshop_","guild_")) and k not in ("summary.json","reconciliation.json") and not T._same(m[k], b[k])])
for n, code in (("iso_cap_release","CAP_REACHED"),("iso_live_window","UNCREDITED_SALVAGE")):
    r = run(n); print(n, code, T._coded(code)(r))
print("iso_unit_charge", run("iso_unit_charge")["summary.json"]["season_charge_ember"])

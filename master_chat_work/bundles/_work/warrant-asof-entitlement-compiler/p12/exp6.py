"""Vacuity of altered_config_profiles_exact: altered expected vs standard tier_b expected."""
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("t", sys.argv[1])
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
std = t._expected_tier("tier_b")
cfg = dict(std[0])
for key in ("as_of", "recorded_cutoff"):
    cfg[key] = t.iso_z(t.stamp(cfg[key]) - 2 * t.DAY)
cfg["prod.approvals_required"] = 1 if cfg["prod.approvals_required"] != 1 else 2
print("std anchors", std[0]["as_of"], std[0]["recorded_cutoff"], "prod.approvals", std[0]["prod.approvals_required"])
print("alt anchors", cfg["as_of"], cfg["recorded_cutoff"], "prod.approvals", cfg["prod.approvals_required"])
W = t.World(t.load(t._tier("tier_b")), cfg)
alt = {env: {k: t.utc(v) for k, (v, _) in sorted(W.profile(env)["keys"].items())} for env in ("dev", "prod")}
for env in ("dev", "prod"):
    a, s = alt[env], std[1][env]
    print(env, "keys std", len(s), "alt", len(a), "only_alt", len(set(a) - set(s)), "only_std", len(set(s) - set(a)),
          "valdiff", sum(1 for k in set(a) & set(s) if a[k] != s[k]))
# approvals alone (anchors unchanged)
cfg2 = dict(std[0], **{"prod.approvals_required": cfg["prod.approvals_required"]})
W2 = t.World(t.load(t._tier("tier_b")), cfg2)
p2 = {k: t.utc(v) for k, (v, _) in sorted(W2.profile("prod")["keys"].items())}
print("approvals only prod diff keys", len(set(p2) ^ set(std[1]["prod"])), "valdiff",
      sum(1 for k in set(p2) & set(std[1]["prod"]) if p2[k] != std[1]["prod"][k]))

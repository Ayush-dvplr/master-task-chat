"""edit_grade3.py <t.py>: kit W2 allows weights in {-5,-3,-1,1,3,5} only: config_shipped_exact 1, config_heldout_resolution_exact 3, altered_config_outputs_exact 3."""
import sys
p = sys.argv[1]; s = open(p).read()
for a, b in [("criteria.config_shipped_exact(weight=2)", "criteria.config_shipped_exact(weight=1)"),
             ("criteria.config_heldout_resolution_exact(weight=2)", "criteria.config_heldout_resolution_exact(weight=3)"),
             ("criteria.altered_config_outputs_exact(weight=2)", "criteria.altered_config_outputs_exact(weight=3)")]:
    assert s.count(a) == 1, a
    s = s.replace(a, b)
open(p, "w").write(s); print("edit_grade3 ok")

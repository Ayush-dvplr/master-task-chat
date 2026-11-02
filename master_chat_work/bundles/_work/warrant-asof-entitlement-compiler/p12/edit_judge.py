import re
import sys

p = sys.argv[1]
s = open(p).read()
blocks = s.split("[[criterion]]\n")
head, crit = blocks[0], blocks[1:]
assert len(crit) == 17


def sub(b, old, new):
    assert b.count(old) == 1, old
    return b.replace(old, new)


# JD-15: R6, R8 weight 3 -> 1
crit[5] = sub(crit[5], "weight = 3\n", "weight = 1\n")
crit[7] = sub(crit[7], "weight = 3\n", "weight = 1\n")
# JD-7/AL-4/AL-6/JD-5: R9 drops the malformed-input clause; skip under a named contract rule counts
crit[8] = sub(crit[8],
              'description = "The agent leaves /app/out/tool.zip in which every exception handler acts on the error it catches (raises, logs and exits non-zero, or records it in an output), and a missing or malformed declared input stops the run with a message naming the file."',
              'description = "The agent leaves /app/out/tool.zip in which every exception handler acts on the error it catches: it raises, exits non-zero with a message, records the error in an output, or rejects or skips the record under a rule an /app/data contract names for that case."')
# JD-16: split R13
r13 = crit[12]
old_d = 'description = "The agent runs a package install or an online lookup during its run."'
r13a = sub(sub(r13, 'name = "r13_installs_or_goes_online"', 'name = "r13_runs_package_install"'),
           old_d, 'description = "The agent runs a package install command during its run."')
r14n = sub(sub(r13, 'name = "r13_installs_or_goes_online"', 'name = "r14_runs_online_lookup"'),
           old_d, 'description = "The agent runs an online lookup during its run."')
# JD-13: R16 -1 important -> -3 critically_important
crit[15] = sub(sub(crit[15], "weight = -1\n", "weight = -3\n"),
               'importance = "important"', 'importance = "critically_important"')
# JD-14: drop R17; renumber sequentially
new = crit[:12] + [r13a, r14n] + crit[13:16]
out = []
for i, b in enumerate(new, 1):
    b = re.sub(r'id = "R\d+"', f'id = "R{i}"', b, count=1)
    b = re.sub(r'name = "r\d+_', f'name = "r{i}_', b, count=1)
    out.append(b)
s2 = head + "".join("[[criterion]]\n" + b for b in out)
open(p, "w").write(s2.rstrip("\n") + "\n")

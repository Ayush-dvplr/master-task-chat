from pathlib import Path
p = Path("test_output.src.py"); s = p.read_text()
block = Path("t2_scripts/levers_block.py").read_text()
block = block.replace("    small = (high - (cap_t - low)) * cents(fit) if False else (low + high - cap_t) * fit[1][1] // 100\n",
                      "    small = (low + high - cap_t) * fit[1][1] // 100\n")
block = block.replace('    assert final.chosen.get(plan_a) == [{"up_to": c, "rate": Fraction(r, 10000)} for c, r in fit]\n',
                      '    assert final.chosen.get(plan_a) == final.plans[plan_a]["revisions"][revisions_a.index(fit)]["tiers"]\n')
anchor = "def _quiet_corpus(corpus: str)"
assert s.count(anchor) == 1
s = s.replace(anchor, block + anchor)
old = '    return _memo(f"quiet:{corpus}", lambda: _quiet(_base_texts(corpus), _QUIET_SEEDS[corpus]))\n'
assert s.count(old) == 1
s = s.replace(old, '    seed = _QUIET_SEEDS[corpus]\n    return _memo(f"quiet:{corpus}", lambda: _levers(*_quiet(_base_texts(corpus), seed), seed))\n')
old = """            + "".join(f', "estimated": {json.dumps(read["estimated"])}' for _ in [0] if "estimated" in read) + "}")"""
assert s.count(old) == 1
s = s.replace(old, """            + "".join(f', "estimated": {json.dumps(read["estimated"])}' for _ in [0] if "estimated" in read)
            + "".join(', "cumulative": true' for _ in [0] if read.get("cumulative")) + "}")""")
old = """            if len(fits) == 1 or (fits and "U1first" in self.off):
                self.chosen[key] = self.plans[key]["revisions"][fits[0]]["tiers"]
"""
assert s.count(old) == 1
s = s.replace(old, old + """            elif not fits and "U1nofit" in self.off:
                self.chosen[key] = self.plans[key]["revisions"][0]["tiers"]
""")
p.write_text(s)
print("ok")

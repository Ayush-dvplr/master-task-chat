"""Minimal stand-in so test_output imports outside rewardkit."""
REG = {}
def criterion(description=""):
    def deco(fn):
        REG[fn.__name__] = {"fn": fn, "description": description}
        return fn
    return deco
class _Criteria:
    def __getattr__(self, name):
        def reg(weight=1):
            REG[name]["weight"] = weight
        return reg
criteria = _Criteria()

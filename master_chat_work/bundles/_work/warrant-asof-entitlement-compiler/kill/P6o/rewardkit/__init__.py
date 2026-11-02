REG = []
def criterion(description=""):
    def deco(fn):
        fn._desc = description
        return fn
    return deco
class _C:
    def __getattr__(self, name):
        def f(*a, **k):
            REG.append((name, a, k))
            return None
        return f
criteria = _C()

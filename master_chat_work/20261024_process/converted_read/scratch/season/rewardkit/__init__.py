def criterion(description=None, **kw):
    def deco(f):
        return f
    return deco
class _C:
    def __getattr__(self, n):
        return lambda *a, **k: None
criteria = _C()

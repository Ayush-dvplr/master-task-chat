class _C:
    def __getattr__(self, n):
        return lambda *a, **k: None
criteria = _C()
def criterion(*a, **k):
    if a and callable(a[0]) and not k:
        return a[0]
    return lambda f: f

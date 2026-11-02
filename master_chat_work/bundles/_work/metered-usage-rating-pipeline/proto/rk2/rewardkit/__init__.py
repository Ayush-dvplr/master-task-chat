def criterion(*a, **k):
    def deco(f):
        return f
    if a and callable(a[0]) and not k:
        return a[0]
    return deco


class _C:
    def __init__(self):
        self.items = []

    def __getattr__(self, n):
        def reg(weight=1, **k):
            self.items.append((n, weight))
        return reg


criteria = _C()

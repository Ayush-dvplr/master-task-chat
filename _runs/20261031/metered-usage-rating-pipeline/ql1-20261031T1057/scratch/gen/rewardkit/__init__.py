class _Any:
    def __call__(self, *a, **k):
        if len(a) == 1 and callable(a[0]) and not k:
            return a[0]
        return self
    def __getattr__(self, n):
        return self
criteria = _Any()
criterion = _Any()

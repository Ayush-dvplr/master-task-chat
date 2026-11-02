"""Local stub: criterion decorator passes through; criteria.<name>(weight=N) is recorded in order."""


def criterion(*args, **kwargs):
    if args and callable(args[0]) and not kwargs:
        return args[0]
    return lambda fn: fn


class _Criteria:
    def __init__(self):
        self.items = []

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda weight=1, **_: self.items.append((name, weight))


criteria = _Criteria()

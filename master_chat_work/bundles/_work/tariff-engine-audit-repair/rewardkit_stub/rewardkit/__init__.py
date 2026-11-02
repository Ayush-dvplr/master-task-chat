"""Local stand-in for rewardkit: lets the check functions be called directly during authoring."""
REGISTERED = {}


def criterion(description=""):
    def wrap(fn):
        fn.description = description
        return fn
    return wrap


class _Criteria:
    def __getattr__(self, name):
        def register(weight):
            REGISTERED[name] = weight
        return register


criteria = _Criteria()

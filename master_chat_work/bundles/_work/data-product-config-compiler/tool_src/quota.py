"""Splitting a cluster quota over the active products by weight."""


def split_quota(quota, weights):
    """Return {pid: units} for the given {pid: weight} of the active products."""
    total = sum(weights.values())
    if total == 0:
        return {pid: 0 for pid in weights}
    return {pid: round(quota * weight / total) for pid, weight in weights.items()}

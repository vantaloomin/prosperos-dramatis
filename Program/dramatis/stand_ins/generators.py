"""Stands in for companion/world/generators.py: `unit` and `pick`, copied as they are, so a seed rolls the same sliders
and looks in Dramatis as in Companion."""
import hashlib


def unit(seed: str, *parts) -> float:
    """A stable number in [0, 1) for this seed and label."""
    digest = hashlib.sha256('\x1f'.join(map(str, (seed, *parts))).encode()).digest()
    return int.from_bytes(digest[:8], 'big') / 2 ** 64


def pick(seed: str, label: str, items: list, weights: list[float] | None = None):
    """Weighted choice that depends only on the seed, the label and the order of `items`."""
    if not items:
        return None
    weights = weights or [1.0] * len(items)
    total = sum(weights)
    target, running = unit(seed, label) * total, 0.0
    for item, weight in zip(items, weights, strict=True):
        running += weight
        if target < running:
            return item
    return items[-1]

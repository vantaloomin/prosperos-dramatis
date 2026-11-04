"""Stands in for companion/world/generators.py: `unit`, copied as it is, so a seed rolls the same sliders in Dramatis
as in Companion."""
import hashlib


def unit(seed: str, *parts) -> float:
    """A stable number in [0, 1) for this seed and label."""
    digest = hashlib.sha256('\x1f'.join(map(str, (seed, *parts))).encode()).digest()
    return int.from_bytes(digest[:8], 'big') / 2 ** 64

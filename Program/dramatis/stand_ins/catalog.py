"""Stands in for companion/world/catalog.py: where the vendored personality words are (formats/companion/data)."""
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / 'formats' / 'companion' / 'data'

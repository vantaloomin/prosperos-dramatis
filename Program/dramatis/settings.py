"""Dramatis' own folder: settings.json and the character library (DRAMATIS_HOME overrides where).

- `model`: which model drafts (dramatis/ai.py); its API key is in the system keyring, not here.
"""
import json
import os
from pathlib import Path


def home() -> Path:
    if os.environ.get('DRAMATIS_HOME'):
        return Path(os.environ['DRAMATIS_HOME'])
    if os.name == 'nt' and os.environ.get('APPDATA'):
        return Path(os.environ['APPDATA']) / 'ProsperoDramatis'
    return Path.home() / '.prosperos-dramatis'


def path() -> Path:
    return home() / 'settings.json'


def load() -> dict:
    try:
        saved = json.loads(path().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        saved = {}
    saved = saved if isinstance(saved, dict) else {}
    return {'model': saved.get('model') if isinstance(saved.get('model'), dict) else {}}


def save(settings: dict) -> dict:
    kept = load() | {key: settings[key] for key in ('model',) if key in settings}
    path().parent.mkdir(parents=True, exist_ok=True)
    path().write_text(json.dumps(kept, indent=2) + '\n', encoding='utf-8')
    return load()

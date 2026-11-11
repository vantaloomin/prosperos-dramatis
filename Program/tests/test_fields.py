"""dramatis/fields.py, the field registry, and the screen's copy of it (scripts/screen_types.py)."""
import json
import subprocess
import sys
from pathlib import Path

from dramatis import assistant, drafting, fields, slop
from dramatis.asking import template
from dramatis.character import Character

PROGRAM = Path(__file__).resolve().parents[1]


def test_every_field_sits_in_the_character():
    blank = Character().model_dump()
    for spec in fields.SPECS:
        place = blank
        for part in spec.at():
            if place is None and spec.key.startswith('psyche.'):
                break  # an empty psyche is saved as None
            assert isinstance(place, dict) and part in place, spec.key
            place = place[part]


def test_limits_come_from_the_model():
    assert fields.limits('about') == {'limit': 2000}
    assert fields.limits('skills') == {'count': 20, 'limit': 300}
    assert fields.limits('psyche.was') == {'limit': 300}
    assert fields.limits('looks.hair') == {'limit': 200}
    assert fields.limits('emotional_traits') == {'count': 12}
    assert fields.limits('age') == {}


def test_every_text_a_model_writes_has_a_limit_and_a_label():
    for key in (*slop.FIELDS, *slop.LIFE_FIELDS, *slop.DEPTH):
        assert fields.LABELS[key]
        assert 'limit' in fields.limits(key) or key == 'emotional_traits', key
    for key in drafting.WRITTEN_KEYS:
        assert key in fields.BY_KEY, key


def test_help_me_write_and_the_assistant_only_name_fields_it_knows():
    assert set(json.loads(template('fields.json'))) <= set(fields.BY_KEY)
    for key, guide in assistant.guides().items():
        assert key in fields.BY_KEY
        assert 'limit' not in guide or guide['limit'] == fields.limit(key)


def test_the_screen_has_the_registry_and_types_as_they_are_now():
    found = subprocess.run([sys.executable, 'scripts/screen_types.py', '--check'], cwd=PROGRAM, capture_output=True,
                           text=True)
    assert found.returncode == 0, found.stderr

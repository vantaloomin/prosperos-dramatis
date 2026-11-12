"""A model's reading of whether the fields other characters read give their secret away, for what the word checks in
dramatis/echo.py cannot see: the secret told in other words ("dropped out before graduating" for a forged diploma),
in another language, or guessed by a model that was never shown it (Wren's sixth pass). Vanta chose the extra call
(2026-11-12). It runs on a split and on the assistant's edits, for a character with a secret, and costs one call; when
that call fails, what the word checks let through stands."""
import re

from dramatis import ai, calls, echo, fields, slop
from dramatis.asking import Unusable, ask, fill, template
from dramatis.formats.companion.errors import DomainError

# Fields that say who they are rather than describe them: no secret goes there in words.
PLAIN = ('name', 'gender', 'age', 'kind', 'setting', 'lifespan', 'birthday')


def public_values(character: dict) -> dict[str, str]:
    """The text of each field anyone reads that has some, by the form's keys."""
    found = {}
    for spec in fields.SPECS:
        if echo.public(spec.key) and spec.key not in PLAIN and not spec.key.startswith('looks.'):
            text = echo.texts(slop.at(character, spec.at())).strip()
            if text:
                found[spec.key] = text
    return found


def leaked(secret: dict, values: dict[str, str]) -> dict[str, str]:
    """Which of these field texts (by key) give the secret away, each with the words that do; {} when none do, when
    there is no secret, or when the check could not be made."""
    truth = ((secret or {}).get('truth') or '').strip() if isinstance(secret, dict) else ''
    values = {key: text for key, text in values.items() if text.strip()}
    if not truth or not values:
        return {}
    shown = '\n\n'.join(f'[[field {key}]]\n{fence(text)}\n[[end {key}]]' for key, text in values.items())
    system = fill(template('leak-check.md'), truth=fence(truth),
                  cover=fence((secret.get('cover_story') or '').strip() or 'nothing in particular'), fields=shown)

    def shape(raw: dict, final: bool) -> dict[str, str]:
        items = raw.get('leaks')
        if not isinstance(items, list):
            raise Unusable('"leaks" must be a list, empty when no field gives the secret away.')
        found = {}
        for item in items:
            key = item.get('field') if isinstance(item, dict) else None
            if key in values:
                found[key] = re.sub(r'\s+', ' ', str(item.get('words') or '')).strip()[:200]
            elif not final:
                raise Unusable(f'"{key}" is not one of the fields. Name only: {", ".join(values)}.')
        return found

    calls.step('Checking their secret stays theirs')
    try:
        return ask(system, shape, 'Name the fields that give the secret away, as JSON.')
    except ai.Stopped:
        raise
    except DomainError:
        return {}


def fence(text: str) -> str:
    """Text inside markers it cannot close."""
    return re.sub(r'\[\s*\[', '[ [', re.sub(r'\]\s*\]', '] ]', text))

"""The Sidebar Assistant: a chat beside the character form, after Prospero's Adventure's (adventure/assistant.py),
which came from the sidecar in Prospero's Companion (companion/sidecar.py). Those two are built on their apps' stories,
memories and chats, so this one is Dramatis's own, on the same contract: it sees the context, answers in one JSON
object, and every change it makes is checked here first.

- It sees the form live: the screen sends the character as it stands with every message, unsaved typing included,
  along with the form as the assistant last left it (`seen`), so it is told which fields the user changed since, and
  which field the user is in (`focus`).
- It edits through `edits`, each one field by its key (dotted for their depth, as Help me write uses them). Each value
  is shaped to that field's limits like any draft, and an edit to a field it may not touch, a value that cannot be
  used or an age under 18 is sent back once with the reason, then dropped. The screen puts what is left into its
  fields as proposals (src/proposals.ts), each marked there for the user to keep or put back, and only Save writes to
  the library.
- Every edit goes through the AI-slop audit (dramatis/slop.py): a hard hit the user didn't write sends the reply
  back once, and what is left comes back for the form to show.

Nothing is stored here, and the conversation is the screen's to keep.
"""
import json
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from dramatis import adults, ai, asking, drafting, fields, slop
from dramatis.character import APPS
from dramatis.drafting import Unusable, fill, template, text_value

HISTORY_TURNS = 10
SHOWN_CHARS = 400
REPLY_CHARS = 3000
# Companion's part of the character, under `companion`.
LIFE = ('routine', 'life_themes', 'schedule', 'history_together', 'emotional_traits')
COMPANION_ONLY = LIFE
# Fields the form has that Help me write does not.
EXTRA = {
    'name': {'guide': 'their first and last name, or the one name they go by', 'shape': 'a string'},
    'gender': {'guide': 'their gender', 'shape': '"woman", "man", "nonbinary", or "" for not said'},
    'age': {'guide': 'their age in whole years: always 18 or more', 'shape': 'a whole number, or null to leave it open'},
    'setting': {'guide': 'where and when they come from, in a few words such as "Baltimore, today"', 'shape': 'a string'},
    'history_together': {'guide': 'how they and the user know each other, in Companion', 'shape': 'a string'},
    'emotional_traits': {'guide': "Companion's emotional edges, such as jealousy or guilt over absence: each one's "
                                  'name, how strong it is and how it shows', 'shape': 'a list of objects {"name": a short '
                                  'name, "intensity": "mild" | "moderate" | "strong", "note": how it shows, in a sentence '
                                  'or two}'},
}
LABELS = fields.LABELS


def guides() -> dict[str, dict]:
    """Every field the assistant may change, in the form's order, with its guide and shape."""
    found = drafting.field_guides()
    extra = {key: guide | fields.limits(key) for key, guide in EXTRA.items()}
    return {key: extra[key] for key in ('name', 'gender', 'age', 'setting')} | found | \
        {key: extra[key] for key in ('history_together', 'emotional_traits')}


def editable(character: dict) -> dict[str, dict]:
    """The fields it may change on this character: Companion's part only when they are made for Companion as a
    companion, since a user persona has no life there."""
    apps = character.get('apps') or list(APPS)
    life = 'companion' in apps and not drafting.is_persona(character.get('companion') or {})
    return {key: guide for key, guide in guides().items() if life or key not in COMPANION_ONLY}


path = fields.path


def plain(value):
    """A value as the form means it, for comparing: lists without blank items, text without the edges."""
    if isinstance(value, list):
        return [item.strip() if isinstance(item, str) else item for item in value
                if not (isinstance(item, str) and not item.strip())]
    return value.strip() if isinstance(value, str) else value


def same(before, after) -> bool:
    empty = (None, '', [])
    return plain(before) == plain(after) or (plain(before) in empty and plain(after) in empty)


def shown(value) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = text.strip() or '(empty)'
    return text if len(text) <= SHOWN_CHARS else text[:SHOWN_CHARS] + '…'


# What it is shown --------------------------------------------------------------------------------------------------

def changed_text(seen: dict | None, now: dict) -> str:
    """The fields the user changed since the assistant last answered, each with what it was and is now."""
    if seen is None:
        return ''
    lines = [f'- {LABELS.get(key, key)} ("{key}"): was {shown(slop.at(seen, path(key)))}; now '
             f'{shown(slop.at(now, path(key)))}'
             for key in guides() if not same(slop.at(seen, path(key)), slop.at(now, path(key)))]
    if not lines:
        return 'They have not changed the form since your last answer.'
    return 'Since your last answer they changed these fields themselves:\n' + '\n'.join(lines)


def where_text(focus: str | None, character: dict) -> str:
    if focus not in editable(character):
        return ''
    return (f'They are in the {LABELS.get(focus, focus)} field ("{focus}") right now, so "this", "here" or "it" most '
            'likely means that field.')


def fields_text(character: dict) -> str:
    return '\n'.join(f"- {key} ({guide['shape']}): {guide['guide']}" for key, guide in editable(character).items())


def character_text(character: dict) -> str:
    """The form as the model sees it: the interview included, the sliders said nowhere."""
    return json.dumps(drafting.for_model(character, interview=True, secret=True), ensure_ascii=False, indent=1)


def conversation(history: list[dict], message: str) -> str:
    lines = [f"{'Them' if turn['role'] == 'user' else 'You'}: {turn['content']}" for turn in history[-HISTORY_TURNS:]]
    earlier = 'The conversation so far:\n' + '\n\n'.join(lines) + '\n\n' if lines else ''
    return f'{earlier}Their new message:\n{message}\n\nWrite the JSON now.'


# What it may change ------------------------------------------------------------------------------------------------

def value_for(field: str, guide: dict, raw, final: bool):
    """One edit's value, shaped like a draft of that field; an empty one clears it."""
    if field == 'age':
        if raw in (None, ''):
            return None
        age = adults.age_value(raw)
        if age is None or not 18 <= age <= 5000:
            raise Unusable(f'"age" must be a whole number of years, 18 or more. {adults.ADULTS_ONLY}')
        return age
    if field == 'gender':
        if raw not in (*drafting.GENDERS, ''):
            raise Unusable('"gender" must be "woman", "man", "nonbinary" or "".')
        return raw
    if field == 'emotional_traits':
        return drafting.traits_value(raw, guide['count'])
    listed = 'count' in guide or field == 'schedule'
    if raw in (None, '', []):
        return [] if listed else ''
    value = drafting.field_value(field, guide, {'value': raw}, final)
    if field == 'about' and adults.YOUNG.search(value):
        raise Unusable(adults.ADULTS_ONLY)
    return value


class Edits:
    """The reply and its edits, each checked against the form it was shown."""

    def __init__(self, character: dict, allowed: str):
        self.character, self.allowed, self.fields = character, allowed, editable(character)

    def __call__(self, raw: dict, final: bool) -> dict:
        reply = text_value(raw.get('reply'), REPLY_CHARS)
        edits, hits, problems = {}, [], []
        for item in raw.get('edits') if isinstance(raw.get('edits'), list) else []:
            try:
                found = self.edit(item, final)
            except Unusable as problem:
                problems.append(str(problem))
                continue
            if found and found['field'] not in edits:
                edits[found['field']] = found
                hits += slop.audit(drafting.placed(found['field'], found['value']), self.allowed)
        if not final:
            if problems:
                raise Unusable(' '.join(problems))
            if slop.hard(hits):
                raise Unusable(slop.problem(slop.hard(hits)))
            if not reply:
                raise Unusable('"reply" was empty.')
        if not reply:
            reply = 'I changed the fields below.' if edits else 'I have nothing to change.'
        return {'reply': reply, 'edits': list(edits.values()), 'audit': hits}

    def edit(self, item, final: bool) -> dict | None:
        """One field's new value, or None when it would change nothing."""
        field = item.get('field') if isinstance(item, dict) else None
        if field not in self.fields:
            raise Unusable(f'"{field}" is not a field you may change. Change only: {", ".join(self.fields)}.')
        value = value_for(field, self.fields[field], item.get('value'), final)
        if same(slop.at(self.character, path(field)), value):
            return None
        return {'field': field, 'label': LABELS.get(field, field), 'path': list(path(field)), 'value': value}


def answer(body: 'AssistantBody') -> dict:
    """One message to the assistant: its reply and the edits for the form; nothing is saved."""
    character = body.character
    history = [turn.model_dump() for turn in body.history]
    system = fill(template('assistant.md'), rules=template('rules.md'), emotional=drafting.FIELD_EDGES,
                  where=where_text(body.focus, character), fields=fields_text(character),
                  # Last, so braces in the user's own words are never read as placeholders.
                  changed=changed_text(body.seen, character), character=character_text(character))
    # What the user typed or pasted, here or on the form, is theirs: the audit never holds it against the model.
    allowed = ' '.join([json.dumps(drafting.own_words(character), ensure_ascii=False), body.message,
                        *(turn['content'] for turn in history if turn['role'] == 'user')])
    with ai.doing('assistant'):
        return asking.ask(system, Edits(character, allowed), conversation(history, body.message))


# Routes -----------------------------------------------------------------------------------------------------------

class Turn(BaseModel):
    model_config = {'extra': 'forbid'}
    role: Literal['user', 'assistant']
    content: str = Field(max_length=8000)


class AssistantBody(BaseModel):
    """`character` is the form as it stands; `seen` is the form as the assistant's last answer left it."""
    model_config = {'extra': 'forbid', 'str_strip_whitespace': True}
    message: str = Field(min_length=1, max_length=8000)
    character: dict
    seen: dict | None = None
    focus: str | None = Field(default=None, max_length=40)
    history: list[Turn] = Field(default_factory=list, max_length=HISTORY_TURNS * 2)


router = APIRouter(prefix='/api')


@router.post('/assistant')
def assistant_route(body: AssistantBody):
    return answer(body)

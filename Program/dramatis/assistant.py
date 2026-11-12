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
- Their secret is shown only when the user is in the secret or their inner fields (arc, psyche, how they see
  themselves) or their message is about them; otherwise the model sees only what people believe, and cannot edit the
  secret. A field anyone can read whose edit uses the secret's own words is sent back once, then dropped
  (dramatis/echo.py).
- With the secret shown, each edit to a field anyone reads is written again by Help me write's call, which sees only
  what people believe (`covered`).
- A message asking to make them a minor is refused before the model runs (`adults.adult_request`). Every text it
  writes, the reply included, is read for an age under 18 or a school they are still at (`adults.young_text`): an
  edit that has one is sent back once, then dropped, and a reply that still has one after the retry is replaced, with
  no edits.
- Lines on the form that talk to the model are left out of what it reads (`drafting.unspoken`).

Nothing is stored here, and the conversation is the screen's to keep.
"""
import json
import re
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from dramatis import adults, ai, asking, drafting, echo, fields, leaks, slop
from dramatis.character import APPS
from dramatis.drafting import Unusable, fill, template, text_value
from dramatis.formats.companion.errors import DomainError

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
# A message about their secret or how they are inside, which is when the assistant is shown the secret.
INNER_TALK = re.compile(r"\b(?:secrets?|hid(?:e|es|den|ing)|cover(?:[- ]up| story)|lie|lies|lying|truth|(?:story )?arc"
                        r"|catalyst|psyche|inner|deep down|inside|sees? (?:them|her|him)sel(?:f|ves)|how (?:they|she|he) "
                        r"sees?|nobody knows|no one knows|who knows)\b", re.IGNORECASE)
# A message that asks for the secret in a field anyone can read, so its words there are the user's wish.
SECRET_OUT = re.compile(r"\b(?:put|move|add|include|mention|reveal|weave|work|bring|use)\b[^.?!]{0,60}\bsecret\b",
                        re.IGNORECASE)


def guides() -> dict[str, dict]:
    """Every field the assistant may change, in the form's order, with its guide and shape."""
    found = drafting.field_guides()
    extra = {key: guide | fields.limits(key) for key, guide in EXTRA.items()}
    return {key: extra[key] for key in ('name', 'gender', 'age', 'setting')} | found | \
        {key: extra[key] for key in ('history_together', 'emotional_traits')}


def editable(character: dict, inner: bool = True) -> dict[str, dict]:
    """The fields it may change on this character: Companion's part only when they are made for Companion as a
    companion, since a user persona has no life there, and the secret only when it is shown it (`inner`)."""
    apps = character.get('apps') or list(APPS)
    life = 'companion' in apps and not drafting.is_persona(character.get('companion') or {})
    return {key: guide for key, guide in guides().items()
            if (life or key not in COMPANION_ONLY) and (inner or not key.startswith('secret.'))}


def inner(focus: str | None, message: str) -> bool:
    """Whether this message is about their secret or how they are inside: the user is in one of those fields, or
    their message speaks of it."""
    return (bool(focus) and drafting.sees_secret(focus)) or bool(INNER_TALK.search(message))


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


def where_text(focus: str | None, character: dict, shown: bool = True) -> str:
    if focus not in editable(character, shown):
        return ''
    return (f'They are in the {LABELS.get(focus, focus)} field ("{focus}") right now, so "this", "here" or "it" most '
            'likely means that field.')


def fields_text(character: dict, shown: bool = True) -> str:
    return '\n'.join(f"- {key} ({guide['shape']}): {guide['guide']}"
                     for key, guide in editable(character, shown).items())


def character_text(character: dict, secret: bool = True) -> str:
    """The form as the model sees it: the interview included, the sliders said nowhere, and their secret only when
    the message is about it (`inner`); otherwise what people believe instead."""
    return json.dumps(drafting.for_model(character, interview=True, secret=secret), ensure_ascii=False, indent=1)


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
    if found := adults.young_text(echo.texts(value)):
        raise Unusable(f'"{field}" makes them younger than 18 ("{found}"). {adults.ADULTS_ONLY}')
    return value


class Edits:
    """The reply and its edits, each checked against the form it was shown."""

    def __init__(self, character: dict, allowed: str, shown: bool = True, secret: set[str] = frozenset(),
                 cover: bool = False, known: str = ''):
        self.character, self.allowed, self.fields = character, allowed, editable(character, shown)
        # `cover`: they have a secret the user didn't ask to put anywhere, so no field anyone reads may say what
        # people believe isn't so, whether or not the assistant was shown it (Wren's fifth pass: it guessed). `known`
        # is what anyone could read before, and the user's message: words from it never count as the secret.
        self.secret, self.cover, self.known = secret, cover, known

    def __call__(self, raw: dict, final: bool) -> dict:
        reply = text_value(raw.get('reply'), REPLY_CHARS)
        if (young := adults.says_young(reply)) and final:
            return {'reply': adults.ADULTS_ONLY, 'edits': [], 'audit': []}
        edits, hits, problems = {}, [], [f'"reply" makes them younger than 18 ("{young}"). {adults.ADULTS_ONLY}'] if young else []
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
            self.send_back(problems, hits, reply, edits)
        if not reply:
            reply = 'I changed the fields below.' if edits else 'I have nothing to change.'
        return {'reply': reply, 'edits': list(edits.values()), 'audit': hits}

    def send_back(self, problems: list[str], hits: list[dict], reply: str, edits: dict[str, dict]) -> None:
        """The first reply goes back once for what is wrong with it, a secret given away last: that check costs a
        model call."""
        if problems:
            raise Unusable(' '.join(problems))
        if slop.hard(hits):
            raise Unusable(slop.problem(slop.hard(hits)))
        if not reply:
            raise Unusable('"reply" was empty.')
        if self.cover and (leaked := self.leaked(edits)):
            raise Unusable(' '.join(leaked))

    def leaked(self, edits: dict[str, dict]) -> list[str]:
        """The first reply's edits to fields anyone reads that a model's reading finds give the secret away
        (dramatis/leaks.py), as a problem to send back. Those `covered` writes again are left to it."""
        guides = drafting.field_guides() if self.secret else {}
        values = {key: echo.texts(edit['value']) for key, edit in edits.items()
                  if echo.public(key) and key not in guides and edit['value'] not in ('', [])}
        found = leaks.leaked(self.character.get('secret'), values, self.known) if values else {}
        return [leaks.problem(found)] if found else []

    def edit(self, item, final: bool) -> dict | None:
        """One field's new value, or None when it would change nothing."""
        field = item.get('field') if isinstance(item, dict) else None
        if field not in self.fields:
            raise Unusable(f'"{field}" is not a field you may change. Change only: {", ".join(self.fields)}.')
        value = value_for(field, self.fields[field], item.get('value'), final)
        if same(slop.at(self.character, path(field)), value):
            return None
        if self.cover and echo.public(field) and (found := echo.breaks_cover(echo.texts(value))):
            if final:
                return None
            raise Unusable(echo.problem([LABELS.get(field, field)], found))
        # A field Help me write writes is written again without the secret (`covered`); the rest are checked here.
        if echo.public(field) and field not in drafting.field_guides() and self.secret:
            if echo.echoed(value, self.secret):
                raise Unusable(echo.problem([LABELS.get(field, field)]))
            if found := echo.breaks_cover(echo.texts(value)):
                raise Unusable(echo.problem([LABELS.get(field, field)], found))
        return {'field': field, 'label': LABELS.get(field, field), 'path': list(path(field)), 'value': value}


def answer(body: 'AssistantBody') -> dict:
    """One message to the assistant: its reply and the edits for the form; nothing is saved."""
    adults.adult_request(body.message)
    character = body.character
    history = [turn.model_dump() for turn in body.history]
    shown = inner(body.focus, body.message)
    system = fill(template('assistant.md'), rules=template('rules.md'), emotional=drafting.FIELD_EDGES,
                  where=where_text(body.focus, character, shown), fields=fields_text(character, shown),
                  # Last, so braces in the user's own words are never read as placeholders.
                  changed=changed_text(body.seen, character), character=character_text(character, shown))
    # What the user typed or pasted, here or on the form, is theirs: the audit never holds it against the model.
    allowed = ' '.join([json.dumps(drafting.own_words(character), ensure_ascii=False), body.message,
                        *(turn['content'] for turn in history if turn['role'] == 'user')])
    # The secret's own words, held against an edit to a field anyone reads, unless the user asked for it there.
    secret = set() if not shown or SECRET_OUT.search(body.message) else \
        echo.secret_words(character.get('secret'), echo.public_text(character), body.message)
    cover = echo.has_secret(character) and not SECRET_OUT.search(body.message)
    with ai.doing('assistant'):
        known = f'{echo.public_text(character)} {body.message}'
        found = asking.ask(system, Edits(character, allowed, shown, secret, cover, known),
                           conversation(history, body.message))
        # Unless the user asked for the secret there: then its words in that field are their wish.
        if shown and not SECRET_OUT.search(body.message):
            found = covered(found, character, body.message)
        return unleaked(found, character, known) if cover else found


def unleaked(found: dict, character: dict, known: str = '') -> dict:
    """The answer without the edits to fields anyone reads that a model call judged to give the secret away
    (dramatis/leaks.py), shown or not: the word checks miss it said in other words, or guessed."""
    values = {edit['field']: echo.texts(edit['value']) for edit in found['edits'] if echo.public(edit['field'])}
    found_leaks = leaks.leaked(character.get('secret'), values, known) if values else {}
    if not found_leaks:
        return found
    dropped = ', '.join(LABELS.get(key, key) for key in found_leaks)
    return found | {'reply': f"{found['reply']} I left out my change to {dropped}: other characters read it, and it "
                             'gave their secret away.',
                    'edits': [edit for edit in found['edits'] if edit['field'] not in found_leaks],
                    'audit': [hit for hit in found['audit'] if hit.get('field') not in found_leaks]}


def covered(found: dict, character: dict, message: str) -> dict:
    """An answer written with the secret in view, with each field anyone reads that Help me write can write written
    again by a call that sees only what people believe, as Fix does: told the secret, a model writes it into the
    Background however it is told not to (Wren's runs: 6 in 19, and the job behind it in 13), and its own words for it
    share none with the secret. What the user asked for goes to that call as their request."""
    guides = drafting.field_guides()
    again = {edit['field'] for edit in found['edits']
             if echo.public(edit['field']) and edit['field'] in guides and edit['value'] not in ('', [])}
    if not again:
        return found
    edits, audit = [], [hit for hit in found['audit'] if hit['field'] not in again]
    request = unasked(message)
    for edit in found['edits']:
        if edit['field'] in again:
            try:
                written = drafting.rewrite(character, edit['field'], request)
            except DomainError:
                continue
            text = echo.texts(written['value'])
            if adults.says_young(text) or echo.breaks_cover(text) or same(slop.at(character, path(edit['field'])),
                                                                         written['value']):
                continue
            edit, audit = edit | {'value': written['value']}, audit + written['audit']
        edits.append(edit)
    return found | {'edits': edits, 'audit': audit}


# "with her secret in mind", "keeping what she hides in view": a clause that brings the secret into a request.
SECRET_CLAUSE = re.compile(r",?\s*\b(?:with|keeping|bearing|given|considering|knowing|remembering|minding)\b[^.,;!?]{0,60}?"
                           r"\b(?:secrets?|hid(?:e|es|den|ing)|truth|cover(?:[- ]up| story))\b[^.,;!?]{0,30}", re.IGNORECASE)


def unasked(message: str) -> str:
    """The user's message as a request to a call that writes a field anyone reads: without the clauses and sentences
    that talk about their secret or how they are inside, so the call can't write it there (Wren's fourth pass: told
    "keeping her secret in mind", it did)."""
    kept = [sentence for sentence in re.split(r'(?<=[.!?])\s+|\n+', SECRET_CLAUSE.sub('', message or ''))
            if sentence.strip() and not INNER_TALK.search(sentence)]
    return ' '.join(kept).strip()


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

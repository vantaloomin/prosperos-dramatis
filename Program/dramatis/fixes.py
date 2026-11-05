"""Fix under the AI-slop audit: the model rewrites only the words the audit marked, and the rest of each field stays
as it was, letter for letter.

- The form sends the hits the user picked (or all of them) as the audit showed them; `fix` finds each one again in
  the character (slop.located), joins hits that overlap ("A beat" and "beat."), and shows the model each field with
  those words marked [[1]]...[[/1]] and why each was marked (prompts/fix.md). The model answers only the replacements,
  and they are put into the text here, so nothing else in the field can change.
- What touches their secret is asked apart from the rest, the way Help me write does it (drafting.sees_secret): the
  secret is only in front of the model while it rewrites what may say it.
- A replacement that is missing, unchanged, far longer than what it replaces, or brings in a hard hit the field didn't
  have is sent back once (drafting.ask). Each changed field comes back whole, for the form to show as a proposal with
  Keep / Put back. Nothing is saved.
"""
import json

from fastapi import APIRouter
from pydantic import BaseModel, Field, ValidationError

from dramatis import drafting, slop
from dramatis.character import Character
from dramatis.drafting import Unusable, ask, fenced, fill, template
from dramatis.formats.companion.errors import DomainError

PUNCTUATION = ',.;:!?)'


def path(field: str) -> tuple[str, ...]:
    """Where a field the audit reads sits in the character."""
    if field in slop.DEPTH:
        return slop.DEPTH[field][1]
    return ('companion', field) if field in slop.LIFE_FIELDS else (field,)


def chosen(character: dict, picked: list[dict]) -> list[dict]:
    """The picked hits, found again in the character with where they are; a hit no longer there is left out."""
    wanted = {(hit['field'], hit['rule'], hit['match'], hit['context']) for hit in picked}
    return [hit for hit in slop.located(character)
            if (hit['field'], hit['rule'], hit['match'], hit['context']) in wanted]


def spans(hits: list[dict]) -> dict[tuple[str, int | None], list[dict]]:
    """The hits by the text they are in (field and list item), in order, with overlapping ones joined into one span.
    A span's edges never include spaces."""
    found: dict[tuple[str, int | None], list[dict]] = {}
    for hit in sorted(hits, key=lambda hit: (hit['field'], hit['item'] if hit['item'] is not None else -1, hit['at'])):
        place = found.setdefault((hit['field'], hit['item']), [])
        if place and hit['at'] < place[-1]['end']:
            place[-1]['end'] = max(place[-1]['end'], hit['end'])
            place[-1]['rules'] = list(dict.fromkeys([*place[-1]['rules'], hit['rule']]))
        else:
            place.append({'field': hit['field'], 'label': hit['label'], 'item': hit['item'], 'at': hit['at'],
                          'end': hit['end'], 'rules': [hit['rule']]})
    return found


def text_of(character: dict, field: str, item: int | None) -> str:
    value = slop.at(character, path(field))
    return value[item] if item is not None else value


def trimmed(text: str, span: dict) -> dict:
    """The span without the spaces at its edges, with the words it holds."""
    at, end = span['at'], span['end']
    while at < end and text[at].isspace():
        at += 1
    while end > at and text[end - 1].isspace():
        end -= 1
    return span | {'at': at, 'end': end, 'words': text[at:end]}


def marked(character: dict, places: dict) -> str:
    """Each field with its spans marked, under the field's name; a list's items one per line."""
    blocks: dict[str, list[str]] = {}
    for (field, item), found in places.items():
        text, line, last = text_of(character, field, item), [], 0
        for span in found:
            line += [fenced(text[last:span['at']]), f"[[{span['n']}]]{fenced(span['words'])}[[/{span['n']}]]"]
            last = span['end']
        line.append(fenced(text[last:]))
        blocks.setdefault(found[0]['label'], []).append(('- ' if item is not None else '') + ''.join(line))
    return '\n\n'.join(f'### {label}\n' + '\n'.join(lines) for label, lines in blocks.items())


def put(text: str, span: dict, words: str) -> str:
    """The text with the span's words replaced, without doubled spaces or a space before punctuation."""
    before, after = text[:span['at']], text[span['end']:]
    if not words and before.endswith(' ') and (after[:1] in (' ', '') or after[:1] in PUNCTUATION):
        before = before.rstrip(' ')
    elif words[:1] in PUNCTUATION and before.endswith(' '):
        before = before.rstrip(' ')
    return before + words + after


class Fixed:
    """Shapes the model's replacements into each changed field, whole; see the module's notes for what goes back."""

    def __init__(self, character: dict, places: dict, numbered: list[dict], allowed: str):
        self.character, self.places, self.numbered, self.allowed = character, places, numbered, allowed

    def words(self, raw: dict, final: bool) -> dict[int, str]:
        given = raw.get('spans') if isinstance(raw.get('spans'), dict) else {}
        found, problems = {}, []
        for span in self.numbered:
            value = given.get(str(span['n']))
            if not isinstance(value, str):
                problems.append(f'{span["n"]} was missing')
                continue
            value = ' '.join(value.replace('[[', '').replace(']]', '').split())
            if value.casefold() == span['words'].casefold():
                problems.append(f'{span["n"]} was the marked words again')
            elif len(value) > max(80, 4 * len(span['words'])):
                problems.append(f'{span["n"]} was far longer than the words it replaces')
            else:
                found[span['n']] = value
        if problems and not final:
            raise Unusable('; '.join(problems) + '. Give a short replacement for every marked number.')
        return found

    def __call__(self, raw: dict, final: bool) -> dict:
        words = self.words(raw, final)
        values: dict[str, object] = {}
        for (field, item), found in self.places.items():
            text = text_of(self.character, field, item)
            for span in reversed(found):
                if span['n'] in words:
                    text = put(text, span, words[span['n']])
            if item is None:
                values[field] = text
            else:
                current = values.get(field, list(slop.at(self.character, path(field))))
                current[item] = text
                values[field] = current
        patched = self.character
        for field, value in values.items():
            patched = with_value(patched, path(field), value)
        if not final and fits(self.character) and not fits(patched):
            raise Unusable('a replacement made its field too long. Use fewer words.')
        labels = {field: found[0]['label'] for (field, _), found in self.places.items()}
        result = []
        for field, value in values.items():
            hits = slop.audit(drafting.placed(field, value), self.allowed)
            before = json.dumps(slop.at(self.character, path(field)), ensure_ascii=False).casefold()
            added = [hit for hit in slop.hard(hits) if hit['match'].strip().casefold() not in before]
            if added and not final:
                raise Unusable(slop.problem(added))
            result.append({'field': field, 'label': labels[field], 'value': value, 'audit': hits})
        return {'fields': result}


def with_value(character: dict, keys: tuple[str, ...], value) -> dict:
    if not keys:
        return value
    found = character if isinstance(character, dict) else {}
    return {**found, keys[0]: with_value(found.get(keys[0]), keys[1:], value)}


def fits(character: dict) -> bool:
    try:
        Character.model_validate({key: value for key, value in character.items() if key != 'intimacy'})
        return True
    except ValidationError:
        return False


def fix(character: dict, picked: list[dict], allowed: str = '') -> dict:
    """New text for every field the picked hits are in, with only those words changed; nothing is saved."""
    hits = chosen(character, picked)
    if not hits:
        raise DomainError('Those words are no longer in the form.', 409, 'nothing_to_fix')
    allowed = f'{allowed}\n{slop.ignored(character)}'
    places = {place: [trimmed(text_of(character, *place), span) for span in found]
              for place, found in spans(hits).items()}
    places = {place: [span for span in found if span['words']] for place, found in places.items()}
    places = {place: found for place, found in places.items() if found}
    # What may say their secret is written apart from the rest, so the secret is only shown where it belongs.
    groups: dict[bool, dict] = {}
    for place, found in places.items():
        groups.setdefault(drafting.sees_secret(place[0]), {})[place] = found
    fields = []
    for secret, group in groups.items():
        numbered = [span for found in group.values() for span in found]
        for number, span in enumerate(numbered, 1):
            span['n'] = number
        why = '\n'.join(f"- {span['n']}: \"{span['words']}\" ({'; '.join(span['rules'])})" for span in numbered)
        system = fill(template('fix.md'), rules=template('rules.md'), marked=marked(character, group),
                      why=why, character=json.dumps(drafting.for_model(character, secret=secret), ensure_ascii=False,
                                                     indent=1))
        fields += ask(system, Fixed(character, group, numbered, allowed))['fields']
    return {'fields': fields}


# Routes -----------------------------------------------------------------------------------------------------------

class Picked(BaseModel):
    model_config = {'extra': 'ignore'}
    field: str = Field(max_length=40)
    rule: str = Field(max_length=200)
    match: str = Field(max_length=400)
    context: str = Field(max_length=1000)


class FixBody(BaseModel):
    model_config = {'extra': 'forbid'}
    character: dict
    hits: list[Picked] = Field(min_length=1, max_length=200)
    allowed: str = Field(default='', max_length=60000)


router = APIRouter(prefix='/api/draft')


@router.post('/fix')
def fix_route(body: FixBody):
    return fix(body.character, [hit.model_dump() for hit in body.hits], body.allowed)

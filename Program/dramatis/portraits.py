"""Make a portrait: the text model turns a character's looks into one image prompt (prompts/portrait.md), a style
line is added (data/portrait-styles.json), and the image maker draws it (dramatis/images.py, with Companion's own
image adapters).

The prompt is built only from what a portrait shows: every set Looks field (the Details, which a draft settles
before it writes the Appearance, dramatis/looks.py), then the appearance, age, gender, kind, where and when they live,
and their personality for the expression. Where an older Appearance and a Details field disagree, the field wins. Nothing private goes in (how others see them, how they see
themselves, their background), and no name, so a model draws no text and no famous namesake. A prompt the model
writes with anything sexual or young in it is sent back once, then refused.

Nothing is saved: the picture comes back for the form to show beside the current portrait, and Use this saves it
through the existing `PUT /api/characters/{id}/portrait`.
"""
import base64
import json
import re
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field, ValidationError

from dramatis import ai, drafting, images, library
from dramatis.character import Character
from dramatis.formats.companion.errors import DomainError, require

STYLES = Path(__file__).parent / 'data' / 'portrait-styles.json'
PROMPT_LIMIT = 1200
LOOKS = (('height_cm', 'Height', ' cm'), ('weight_kg', 'Weight', ' kg'), ('build', 'Build', ''), ('skin', 'Skin', ''),
         ('face', 'Face', ''), ('jaw', 'Jaw', ''), ('nose', 'Nose', ''), ('eyes', 'Eyes', ''),
         ('eye_shape', 'Eye shape', ''), ('hair', 'Hair', ''), ('facial_hair', 'Facial hair', ''),
         ('feature', 'Something people notice', ''))
UNSAFE = re.compile(r'\b(?:nude|naked|nsfw|topless|lingerie|underwear|bikini|cleavage|sexy|sensual|seductive|erotic'
                    r'|child|kid|teen|teenage[rd]?|minor|schoolgirl|schoolboy|loli)\b', re.IGNORECASE)
UNSAFE_PROBLEM = ('the prompt must show a dressed adult with nothing sexual or young about the picture; it said '
                  '"{word}".')


def styles() -> list[dict]:
    """The styles a portrait can be drawn in: a name for the screen and the line added to the prompt."""
    return json.loads(STYLES.read_text(encoding='utf-8'))


def style_line(key: str) -> str:
    found = next((style for style in styles() if style['key'] == key), None)
    require(found is not None, f'{key} is not one of the portrait styles.', 422)
    return found['line']


def facts(character: Character) -> str:
    """What a portrait shows, one fact a line, and nothing else."""
    looks = character.looks.model_dump()
    rows = [('Age', str(character.age) if character.age else 'an adult; their age is not given'),
            ('Gender', character.gender), ('Kind', character.kind or 'human'),
            ('Where and when they live', character.setting or 'the present day')]
    rows += [(label, f'{looks[key]}{unit}') for key, label, unit in LOOKS if looks[key] not in (None, '')]
    rows.append(('Appearance', character.appearance))
    rows.append(('Temperament, for the expression only', character.personality[:600]))
    return '\n'.join(f'- {label}: {value}' for label, value in rows if value)


def prompt_value(raw: dict) -> str:
    text = raw.get('prompt')
    text = ' '.join(text.split())[:PROMPT_LIMIT] if isinstance(text, str) else ''
    if not text:
        raise drafting.Unusable('"prompt" was empty.')
    unsafe = UNSAFE.search(text)
    if unsafe:
        raise drafting.Unusable(UNSAFE_PROBLEM.format(word=unsafe[0]))
    return text


def described(character: Character) -> str:
    """The text model's image prompt for them, asked for once more with the problem named if it cannot be used."""
    system = drafting.fill(drafting.template('portrait.md'), facts=facts(character))
    asked = 'Write the JSON now.'
    for _ in range(2):
        reply = ai.complete(system, asked)
        try:
            return prompt_value(drafting.parse_object(reply))
        except drafting.Unusable as problem:
            found = problem
            asked = (f'Write the JSON now.\n\nYour last reply was:\n{reply[:3000]}\n\n'
                     + drafting.fill(drafting.template('repair.md'), problem=str(problem)))
    raise DomainError(f"The model's portrait prompt could not be used: {found} Try again, or add a picture of "
                      'your own.', 502, 'prompt_unusable')


def make(character: Character, style: str) -> dict:
    """A portrait to look at, as a card-sized PNG in base64, and the prompt it was drawn from. Nothing is saved."""
    line = style_line(style)
    require(images.config()['ready'], 'Set up an image maker first: Portraits, at the top, next to the model.', 409)
    drafting.adults_only(character.age, character.about)
    prompt = ' '.join(part for part in (described(character), line) if part)
    picture = images.card_picture(images.generate(prompt))
    return {'image': base64.b64encode(picture).decode('ascii'), 'prompt': prompt, 'style': style}


def form_character(raw: dict) -> Character:
    try:
        return Character.model_validate({key: value for key, value in raw.items() if key != 'intimacy'})
    except ValidationError as error:
        found = error.errors()[0]
        raise DomainError(f"{'.'.join(map(str, found['loc']))}: {found['msg']}", 422, 'invalid_character') from error


# Routes ------------------------------------------------------------------------------------------------------------

class Body(BaseModel):
    model_config = {'extra': 'forbid', 'str_strip_whitespace': True}


class ImageBody(Body):
    kind: str
    provider: str = Field(default='', max_length=40)
    base_url: str = Field(default='', max_length=500)
    model: str = Field(default='', max_length=300)
    family: str = Field(default='', max_length=40)
    key: str | None = Field(default=None, max_length=500)


class MakeBody(Body):
    style: str = Field(default='', max_length=40)


class DraftMakeBody(MakeBody):
    """For a character not saved yet: the form as it stands."""
    character: dict


def router() -> APIRouter:
    routes = APIRouter(prefix='/api')

    @routes.get('/images')
    def get_images():
        return images.config()

    @routes.put('/images')
    def put_images(body: ImageBody):
        return images.configure(body.kind, body.provider, body.base_url, body.model, body.family, body.key)

    @routes.post('/images/check')
    def check_images():
        return images.check()

    @routes.get('/portrait/styles')
    def get_styles():
        return [{'key': style['key'], 'name': style['name']} for style in styles()]

    @routes.post('/portrait/make')
    def make_draft(body: DraftMakeBody):
        return make(form_character(body.character), body.style)

    @routes.post('/characters/{character_id}/portrait/make')
    def make_saved(character_id: str, body: MakeBody):
        return make(form_character(library.get(character_id)['character']), body.style)

    return routes

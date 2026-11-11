"""Character cards in and out.

**Out.** A Character Card V3 (chara_card_v3), as JSON or inside a PNG, in one of two kinds (`Target`):

- `prospero`, for Prospero's Companion, Adventure and Dungeon: `data.extensions.prospero` holds the whole Dramatis
  character and each app's own shape of it (dramatis/character.py), so a Prospero app takes them with nothing lost.
- `chat`, for SillyTavern, Marinara Engine, Front Porch AI and other chat apps: the same card without Dramatis' own
  extension, so what only the Prospero apps use (Companion's schedule, routine, texting habits, emotional edges, the
  sliders) never leaves the suite. Those apps keep every extension a card carries and send it on when the card is
  shared again.

A character imported from another app's card (dramatis/imports.py) keeps that card's own parts in `card`: its
greetings, example messages, scenario, notes, prompts, tags, lorebook and the other apps' extensions go back into both
kinds as they came, so editing them here loses none of it.

Both kinds describe the character in the card's own fields, in words any app can read, their secret included: the
character's own model has to know it to keep it. A PNG card carries the V3 card in a `ccv3` text chunk and a V2 copy in `chara`: SillyTavern and Marinara read `ccv3` first, Front Porch reads only
`chara`. The picture is their portrait, or a plain one when they have none.

**In.** `own_character` finds the whole Dramatis character in a Prospero card it made. Every other character file is
dramatis/imports.py's, read with Companion's own importer.
"""
import base64
import json
import struct
import zlib
from datetime import datetime
from pathlib import PureWindowsPath
from typing import Literal

from pydantic import ValidationError

from dramatis import NAME, VERSION
from dramatis.character import CardParts, Character, secret_text, shapes
from dramatis.formats.companion.errors import DomainError
from dramatis.formats.companion.imports import cards as reader

FORMAT = 'prospero-character'
FORMAT_VERSION = 1
CARD_KEYS = (b'chara', b'ccv3')
MADE_WITH = f'Made with {NAME}.'
Target = Literal['prospero', 'chat']
# The plain portrait: a soft ink colour, the Dramatis look, at a card's usual 2:3.
PLAIN_SIZE, PLAIN_COLOUR = (400, 600), (58, 52, 66)


LOOKS = (('height_cm', 'Height', '{} cm'), ('weight_kg', 'Weight', '{} kg'), ('build', 'Build', '{}'),
         ('skin', 'Skin', '{}'), ('face', 'Face', '{}'), ('jaw', 'Jaw', '{}'), ('nose', 'Nose', '{}'),
         ('eyes', 'Eyes', '{}'), ('eye_shape', 'Eye shape', '{}'), ('hair', 'Hair', '{}'),
         ('facial_hair', 'Facial hair', '{}'), ('feature', 'Stands out', '{}'))
MONTHS = ('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
          'November', 'December')


def looks(character: Character) -> str:
    found = character.looks.model_dump()
    return '; '.join(f'{label}: {shape.format(found[key])}' for key, label, shape in LOOKS if found[key])


def birthday(value: str) -> str:
    if not value:
        return ''
    month, day = value.split('-')
    return f'{MONTHS[int(month) - 1]} {int(day)}'


def description(character: Character) -> str:
    """The card's description: who they are, how they look and talk, their story and inner life, in headed
    paragraphs. Only what describes the person goes in; how a Prospero app runs them (schedule, sliders, texting)
    does not."""
    sections = [('', character.about), ('Gender', character.gender),
                ('Age', '' if character.age is None else str(character.age)), ('Kind', character.kind),
                ('From', character.setting), ('Birthday', birthday(character.birthday)),
                ('Appearance', character.appearance), ('Looks', looks(character)), ('How they talk', character.voice),
                ('How they sound', character.sound), ('Background', character.background), ('Wants', character.wants),
                ('Fears', character.fears), ('Skills', '; '.join(character.skills)),
                ('Flaws', '; '.join(character.flaws)), ('Interests', '; '.join(character.interests)),
                ('How others see them', character.seen_as), ('How they see themselves', character.sees_self),
                ('Lie they believe', character.arc.lie), ('Truth they need', character.arc.truth),
                ('Secret', secret_text(character.secret))]
    return '\n\n'.join(f'{label}: {text}' if label else text for label, text in sections if text)


def sentence(text: str) -> str:
    text = text.strip()
    return text if not text or text[-1] in '.!?…"\'' else f'{text}.'


def place_text(cast: dict) -> str:
    """The description's last paragraph for a card exported from a cast (casts.context_for): their side's why, their
    own how, who stands beside and against them, and how they see the others they hold a view of."""
    side, corner = cast.get('side'), cast.get('corner')
    lines = []
    if side:
        lines.append(sentence(f"Their side: {side['label'] or 'unnamed'}" + (f", for {side['stance']}" if side['stance'] else '')))
    if corner:
        lines.append(sentence(f"Their way: {corner['label'] or corner['role'] or 'their own'}"
                              + (f", {corner['stance']}" if corner['stance'] else '')))
    if cast.get('beside'):
        lines.append(f"Beside them: {', '.join(cast['beside'])}.")
    if cast.get('against'):
        lines.append(f"Against them: {', '.join(cast['against'])}.")
    for row in cast.get('relationships', []):
        under = f" Underneath: {sentence(row['hidden_tension'])}" if row['hidden_tension'] else ''
        lines.append(f"Toward {row['to_name']}: {sentence(row['dynamic'] or 'no settled view')}{under} "
                     f"Trust {row['trust']} of 10.")
    return f"Their place in {cast.get('title') or 'the cast'}:\n" + '\n'.join(lines) if lines else ''


def card(character: Character, created: str, updated: str, target: Target = 'prospero', cast: dict | None = None) -> dict:
    """The V3 card. Tags are only the ones a card they were imported from had: chat apps file every tag a card brings
    into the user's own tag list. How they know the user is the scenario (a user persona has none), or the imported
    card's own one. `cast` is their place in a cast they are exported from (casts.context_for): the description ends
    with it, and the Prospero card keeps it whole; the apps' shapes stay as they are."""
    parts = character.card or CardParts()
    extensions = dict(parts.extensions)
    if target == 'prospero':
        extensions['prospero'] = {'format': FORMAT, 'format_version': FORMAT_VERSION, 'app': NAME,
                                  'app_version': VERSION, 'character': character.model_dump(),
                                  'apps': shapes(character), **({'cast': cast} if cast else {})}
    data = {
        'name': character.name or 'Unnamed',
        'description': '\n\n'.join(text for text in (description(character), place_text(cast or {})) if text),
        'personality': character.personality, 'scenario': ('' if character.is_persona() else character.companion.history_together) or parts.scenario,
        'first_mes': parts.first_mes, 'mes_example': parts.mes_example,
        'creator_notes': parts.creator_notes or MADE_WITH, 'system_prompt': parts.system_prompt,
        'post_history_instructions': parts.post_history_instructions,
        'alternate_greetings': parts.alternate_greetings, 'tags': parts.tags, 'creator': parts.creator,
        'character_version': parts.character_version or '1', 'extensions': extensions,
        'group_only_greetings': [], 'nickname': '',
        'creation_date': timestamp(created), 'modification_date': timestamp(updated),
    }
    if parts.character_book:
        data['character_book'] = parts.character_book
    return {'spec': 'chara_card_v3', 'spec_version': '3.0', 'data': data}


def timestamp(value: str) -> int:
    try:
        return int(datetime.fromisoformat(value).timestamp())
    except (TypeError, ValueError):
        return 0


def v2(full: dict) -> dict:
    """The same card as chara_card_v2, for apps that only read the older chunk."""
    keep = ('name', 'description', 'personality', 'scenario', 'first_mes', 'mes_example', 'creator_notes',
            'system_prompt', 'post_history_instructions', 'alternate_greetings', 'tags', 'creator',
            'character_version', 'extensions', 'character_book')
    return {'spec': 'chara_card_v2', 'spec_version': '2.0',
            'data': {key: full['data'][key] for key in keep if key in full['data']}}


# PNG ------------------------------------------------------------------------------------------------------------

def chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind + payload))


def plain_png(size: tuple[int, int] = PLAIN_SIZE, colour: tuple[int, int, int] = PLAIN_COLOUR) -> bytes:
    width, height = size
    row = b'\x00' + bytes(colour) * width
    header = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    return reader.SIGNATURE + chunk(b'IHDR', header) + chunk(b'IDAT', zlib.compress(row * height, 9)) + \
        chunk(b'IEND', b'')


def picture_chunks(picture: bytes) -> list[bytes]:
    """A PNG's chunks up to IEND, without any character card in them."""
    kept = []
    for kind, payload in reader.chunks(picture):
        if kind == b'IEND':
            break
        if kind in (b'tEXt', b'iTXt', b'zTXt') and payload.partition(b'\0')[0] in CARD_KEYS:
            continue
        kept.append(chunk(kind, payload))
    return kept


def without_card(picture: bytes) -> bytes:
    """A card's picture as a plain PNG, for their portrait."""
    return reader.SIGNATURE + b''.join(picture_chunks(picture)) + chunk(b'IEND', b'')


def with_card(picture: bytes, full: dict) -> bytes:
    """The picture with the card in it: any card it already held is taken out, and both chunks go before IEND."""
    kept = picture_chunks(picture)
    texts = [chunk(b'tEXt', key + b'\0' + base64.b64encode(json.dumps(value, ensure_ascii=False).encode('utf-8')))
             for key, value in ((b'chara', v2(full)), (b'ccv3', full))]
    return reader.SIGNATURE + b''.join(kept) + b''.join(texts) + chunk(b'IEND', b'')


# Reading a card ---------------------------------------------------------------------------------------------------

def own_character(filename: str, source: bytes) -> dict | None:
    """The Dramatis character inside a card, when there is one that still checks out."""
    try:
        is_png = PureWindowsPath(filename).suffix.lower() == '.png' or source.startswith(reader.SIGNATURE)
        raw = reader.embedded_card(source) if is_png else source
        data = reader.card_data(json.loads(raw.decode('utf-8-sig')))
    except (DomainError, UnicodeDecodeError, ValueError):
        return None
    extension = (data.get('extensions') or {}).get('prospero') if isinstance(data.get('extensions'), dict) else None
    if not isinstance(extension, dict) or extension.get('format') != FORMAT:
        return None
    try:
        return Character.model_validate(extension.get('character')).model_dump()
    except ValidationError:
        return None

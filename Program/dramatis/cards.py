"""Character cards in and out.

**Out.** A Character Card V3 (chara_card_v3), as JSON or inside a PNG, which every Prospero app and most chat apps
(SillyTavern, Chub, RisuAI, Backyard) import today. The card's own fields hold the character in words any of them can
read; `data.extensions.prospero` holds the whole Dramatis character and each app's own shape of it (dramatis/character.py),
so a Prospero app can take them with nothing lost. A PNG card carries the V3 card in a `ccv3` text chunk and a V2 copy
in `chara`, for apps that only read V2; the picture is their portrait, or a plain one when they have none.

**In.** A card file is read with Companion's own card reader (vendored). A card Dramatis made comes back whole, from
its extension; any other card becomes headed text for the paste box, to split into the fields with the model.
"""
import base64
import binascii
import json
import struct
import zlib
from datetime import datetime
from pathlib import PureWindowsPath

from pydantic import ValidationError

from dramatis import NAME, VERSION
from dramatis.character import Character, shapes
from dramatis.formats.companion import cards as reader
from dramatis.formats.companion.errors import DomainError

FORMAT = 'prospero-character'
FORMAT_VERSION = 1
CARD_KEYS = (b'chara', b'ccv3')
# The plain portrait: a soft ink colour, the Dramatis look, at a card's usual 2:3.
PLAIN_SIZE, PLAIN_COLOUR = (400, 600), (58, 52, 66)


def description(character: Character) -> str:
    """The card's description: who they are, how they look and talk, and their story, in headed paragraphs."""
    sections = [('', character.about), ('Appearance', character.appearance), ('How they talk', character.voice), ('How they sound', character.sound),
                ('Background', character.background), ('Wants', character.wants), ('Fears', character.fears),
                ('Skills', '; '.join(character.skills)), ('Flaws', '; '.join(character.flaws)),
                ('How others see them', character.seen_as)]
    return '\n\n'.join(f'{label}: {text}' if label else text for label, text in sections if text)


def card(character: Character, created: str, updated: str) -> dict:
    """The V3 card."""
    extension = {'format': FORMAT, 'format_version': FORMAT_VERSION, 'app': NAME, 'app_version': VERSION,
                 'character': character.model_dump(), 'apps': shapes(character)}
    data = {
        'name': character.name or 'Unnamed', 'description': description(character),
        'personality': character.personality, 'scenario': character.companion.history_together,
        'first_mes': '', 'mes_example': '', 'creator_notes': f"Made with {NAME}.", 'system_prompt': '',
        'post_history_instructions': '', 'alternate_greetings': [], 'tags': character.interests[:10],
        'creator': '', 'character_version': '1', 'extensions': {'prospero': extension},
        'group_only_greetings': [], 'nickname': '', 'assets': [],
        'creation_date': timestamp(created), 'modification_date': timestamp(updated),
    }
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
            'character_version', 'extensions')
    return {'spec': 'chara_card_v2', 'spec_version': '2.0', 'data': {key: full['data'][key] for key in keep}}


# PNG ------------------------------------------------------------------------------------------------------------

def chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind + payload))


def plain_png(size: tuple[int, int] = PLAIN_SIZE, colour: tuple[int, int, int] = PLAIN_COLOUR) -> bytes:
    width, height = size
    row = b'\x00' + bytes(colour) * width
    header = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    return reader.SIGNATURE + chunk(b'IHDR', header) + chunk(b'IDAT', zlib.compress(row * height, 9)) + \
        chunk(b'IEND', b'')


def with_card(picture: bytes, full: dict) -> bytes:
    """The picture with the card in it: any card it already held is taken out, and both chunks go before IEND."""
    kept = []
    for kind, payload in reader.chunks(picture):
        if kind == b'IEND':
            break
        if kind == b'tEXt' and payload.partition(b'\0')[0] in CARD_KEYS:
            continue
        kept.append(chunk(kind, payload))
    texts = [chunk(b'tEXt', key + b'\0' + base64.b64encode(json.dumps(value, ensure_ascii=False).encode('utf-8')))
             for key, value in ((b'chara', v2(full)), (b'ccv3', full))]
    return reader.SIGNATURE + b''.join(kept) + b''.join(texts) + chunk(b'IEND', b'')


# Reading a card ---------------------------------------------------------------------------------------------------

def opened(filename: str, encoded: str) -> dict:
    """A card file: the whole character when Dramatis made it, otherwise its text for the paste box."""
    try:
        source = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise reader.problem('Choose the card file again; it did not arrive whole.') from error
    ours = own_character(filename, source)
    if ours is not None:
        return {'kind': 'character', 'character': ours}
    return {'kind': 'text', **reader.read_card(filename, encoded)}


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

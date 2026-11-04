"""Cards as SillyTavern, Marinara Engine and Front Porch AI read them.

Each reader below is that app's own import path, cut down to what decides whether a card loads and what it gets:

- SillyTavern: src/character-card-parser.js `read` (the `ccv3` chunk first, then `chara`) and
  src/validator/TavernCardValidator.js (V2 needs every V2 field; V3 needs spec, spec_version 3.x and data).
- Marinara Engine: packages/client/src/lib/png-parser.ts (`ccv3` first, then `chara`) and
  packages/server/src/services/import/st-character.importer.ts `normalizeCharacterData` (chara_card_v2 or _v3 with data).
- Front Porch AI: lib/services/v2_card_service.dart `readCard` (the first `chara` chunk only; it never reads `ccv3`)
  and `parseCardJson` (fields under `data`, or at the top for a V1 card).

All three keep every key under `extensions` as it came and write it back out when the card is shared again, which is
why the chat card carries none.
"""
import base64
import json

from dramatis.cards import card, plain_png, with_card
from dramatis.character import Character
from dramatis.formats.companion import cards as reader
from tests.helpers import reply

V2_FIELDS = ('name', 'description', 'personality', 'scenario', 'first_mes', 'mes_example', 'creator_notes',
             'system_prompt', 'post_history_instructions', 'alternate_greetings', 'tags', 'creator',
             'character_version', 'extensions')
DATES = ('2026-11-04T03:00:00+00:00', '2026-11-04T04:00:00+00:00')


def dana() -> Character:
    found = json.loads(reply())
    life = {key: found.pop(key) for key in ('routine', 'life_themes', 'schedule', 'emotional_traits', 'absence_reaction')}
    return Character.model_validate(found | {
        'setting': 'Baltimore, today', 'birthday': '03-04', 'looks': {'height_cm': 180, 'eyes': 'brown'},
        'companion': life | {'history_together': 'You met in the ER waiting room.', 'texting': {'lowercase': True}}})


def text_chunks(png: bytes) -> list[tuple[str, dict]]:
    found = []
    for kind, payload in reader.chunks(png):
        if kind == b'tEXt':
            key, _, text = payload.partition(b'\0')
            found.append((key.decode('latin-1'), json.loads(base64.b64decode(text).decode('utf-8'))))
    return found


def sillytavern(png: bytes) -> dict:
    chunks = dict(reversed(text_chunks(png)))
    found = chunks.get('ccv3') or chunks['chara']
    if found.get('spec') == 'chara_card_v2':
        assert found['spec_version'] == '2.0' and all(key in found['data'] for key in V2_FIELDS)
    else:
        assert found['spec'] == 'chara_card_v3' and 3 <= float(found['spec_version']) < 4
    assert isinstance(found['data'], dict) and isinstance(found['data']['extensions'], dict)
    return found['data']


def marinara(png: bytes) -> dict:
    chunks = dict(reversed(text_chunks(png)))
    found = chunks.get('ccv3') or chunks['chara']
    assert found['spec'] in ('chara_card_v2', 'chara_card_v3') and found['data']
    return found['data']


def front_porch(png: bytes) -> dict:
    found = next(value for key, value in text_chunks(png) if key == 'chara')
    return found['data'] if isinstance(found.get('data'), dict) else found


def test_each_app_reads_the_same_person_from_either_card():
    character = dana()
    for target in ('prospero', 'chat'):
        png = with_card(plain_png(), card(character, *DATES, target))
        assert [key for key, _ in text_chunks(png)] == ['chara', 'ccv3']
        read = [sillytavern(png), marinara(png), front_porch(png)]
        for data in read:
            assert data['name'] == 'Dana Okafor' and data['personality'].startswith('Steady at work')
            assert data['scenario'] == 'You met in the ER waiting room.'
            assert all(key in data for key in V2_FIELDS)
        assert len({data['description'] for data in read}) == 1


def test_the_description_holds_everything_that_describes_them():
    text = card(dana(), *DATES, 'chat')['data']['description']
    for part in ('Gender: woman', 'Age: 38', 'From: Baltimore, today', 'Birthday: March 4',
                 'Looks: Height: 180 cm; Eyes: brown', 'How they talk: Short sentences', 'Wants: To get onto day',
                 'Skills: Starts an IV in the dark; ', 'Interests: true crime podcasts; duckpin bowling',
                 'How others see them: Comes across as curt'):
        assert part in text


def test_the_chat_card_carries_nothing_only_the_prospero_apps_use():
    character = dana()
    full = card(character, *DATES, 'chat')
    png = with_card(plain_png(), full)
    for data in (full['data'], sillytavern(png), marinara(png), front_porch(png)):
        assert data['extensions'] == {} and data['tags'] == []
        flat = json.dumps(data)
        for private in ('Ward shifts', 'Saturdays are for the bowling league', 'Jealousy', 'Sulks a little',
                        'hospital', 'personality_sliders', 'lowercase'):
            assert private not in flat


def test_the_prospero_card_keeps_it_all():
    character = dana()
    extension = card(character, *DATES, 'prospero')['data']['extensions']['prospero']
    assert Character.model_validate(extension['character']) == character
    assert extension['apps']['companion']['schedule'] == character.companion.schedule

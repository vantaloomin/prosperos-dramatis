import base64
import json

from fastapi.testclient import TestClient

from dramatis import drafting, library
from dramatis.cards import card, description
from dramatis.character import Character, for_adventure, for_companion, problems
from dramatis.main import create_app
from tests.helpers import SLEEP, reply

ARC = {'lie': 'that needing anyone gets you left', 'truth': 'that people stay when asked',
       'catalyst': 'her brother moving out'}
SECRET = {'truth': 'She stole morphine from the ward once', 'cover_story': 'She left her last job over pay',
          'known_by': 'only her brother'}
CHARACTER = {'name': 'Dana Okafor', 'about': 'An ER nurse.', 'background': 'Grew up in Dundalk.',
             'sees_self': 'I keep things moving.', 'wants': 'Day shifts', 'companion': {'schedule': [SLEEP]},
             'arc': ARC, 'secret': SECRET, 'interview': '**What do you do?**\n\n"Nights."'}


def test_older_characters_load_with_no_depth():
    character = Character.model_validate({'name': 'Dana'})
    assert character.arc.lie == '' and character.secret.truth == '' and character.interview == ''
    assert character.psyche is None


def test_arc_and_secret_go_where_each_app_reads_them():
    character = Character.model_validate(CHARACTER)
    assert problems(character) == {}
    background = for_companion(character)['background']
    assert background == ('Grew up in Dundalk.\n\nWhat they want: Day shifts.\n\nThey tell themselves that needing '
                          'anyone gets you left; what they need to learn is that people stay when asked.\n\nSomething '
                          'they keep to themselves: She stole morphine from the ward once. What people believe '
                          'instead: She left her last job over pay. Who knows: only her brother.')
    sees_self = for_adventure(character)['made']['sees_self'].split('\n')
    assert sees_self[0] == 'I keep things moving.'
    assert sees_self[1] == 'What I tell myself: that needing anyone gets you left.'
    assert sees_self[2].startswith('Something I keep to myself: She stole morphine')


def test_companion_keeps_within_its_background_limit_and_never_cuts_their_own_text():
    character = Character.model_validate(CHARACTER | {'background': 'x' * 11900})
    background = for_companion(character)['background']
    assert background.startswith('x' * 11900) and len(background) <= 12000
    assert 'morphine' not in background and 'What they want: Day shifts.' in background
    assert problems(character) == {}


def test_the_card_carries_the_arc_and_the_secret():
    character = Character.model_validate(CHARACTER)
    full = card(character, '', '')
    assert 'Lie they believe: that needing anyone gets you left' in full['data']['description']
    assert 'Truth they need: that people stay when asked' in full['data']['description']
    assert 'Secret: She stole morphine from the ward once.' in full['data']['description']
    assert full['data']['extensions']['prospero']['character']['secret'] == SECRET
    assert 'morphine' in full['data']['extensions']['prospero']['apps']['companion']['background']
    assert description(Character.model_validate({'about': 'A nurse.'})) == 'A nurse.'


def test_arc_and_secret_round_trip_through_save_load_and_card():
    api = TestClient(create_app())
    made = api.post('/api/characters', json={'character': CHARACTER}).json()
    assert made['problems'] == {}
    loaded = api.get(f"/api/characters/{made['id']}").json()['character']
    assert loaded['arc'] == ARC and loaded['secret'] == SECRET and loaded['interview'].startswith('**What')
    plain = api.get(f"/api/characters/{made['id']}/card.json")
    assert plain.json()['data']['extensions']['prospero']['character']['arc'] == ARC
    png = api.get(f"/api/characters/{made['id']}/card.png")
    assert png.status_code == 200
    chat = api.get(f"/api/characters/{made['id']}/card.json?for=chat").json()
    assert 'Secret: She stole morphine' in chat['data']['description'] and 'Lie they believe' in chat['data']['description']
    opened = api.post('/api/cards/open', json={'filename': 'Dana.json',
                                                'data': base64.b64encode(plain.content).decode()}).json()
    assert opened['character']['arc'] == ARC and opened['character']['secret'] == SECRET


def test_a_saved_character_from_before_the_new_fields_opens_with_them_empty():
    api = TestClient(create_app())
    made = api.post('/api/characters', json={'character': {'name': 'Dana'}}).json()
    record = json.loads(library.path_of(made['id']).read_text())
    for key in ('arc', 'secret', 'interview', 'psyche'):
        record['character'].pop(key)
    library.path_of(made['id']).write_text(json.dumps(record))
    loaded = api.get(f"/api/characters/{made['id']}").json()['character']
    assert loaded['arc'] == {'lie': '', 'truth': '', 'catalyst': ''} and loaded['psyche'] is None


def test_help_me_write_fills_one_part_of_the_arc_and_audits_it(model):
    model.replies = ['{"value": "that she has to earn her place every shift"}']
    found = drafting.rewrite(CHARACTER, 'arc.lie')
    assert found == {'field': 'arc.lie', 'value': 'that she has to earn her place every shift', 'audit': []}
    assert 'that needing anyone gets you left' in model.asked[0][0] and 'morphine' in model.asked[0][0]
    model.replies = ['{"value": "Elara knows"}', '{"value": "only her brother and his wife"}']
    found = drafting.rewrite(CHARACTER, 'secret.known_by')
    assert 'Elara' in model.asked[2][1]
    assert found['value'] == 'only her brother and his wife'


def test_the_draft_writes_an_arc_only_when_asked(model):
    picks = {'idea': 'a night nurse', 'apps': ['dungeon']}
    model.replies = [reply(arc={'lie': 'x', 'truth': 'y', 'catalyst': 'z'})]
    assert drafting.draft(picks)['character']['arc'] == {'lie': '', 'truth': '', 'catalyst': ''}
    assert '"arc"' not in model.asked[0][0]
    model.replies = [reply(arc={'lie': 'x', 'truth': 'y', 'catalyst': 'z'})]
    found = drafting.draft(picks | {'idea': 'a night nurse with a redemption arc'})
    assert found['character']['arc'] == {'lie': 'x', 'truth': 'y', 'catalyst': 'z'}
    assert 'The user asked for an arc' in model.asked[1][0]


def test_the_rules_carry_the_new_lines():
    rules = drafting.template('rules.md')
    assert 'three steps ahead' in rules and 'attachment style' in rules and 'Vance, Kaela' in rules

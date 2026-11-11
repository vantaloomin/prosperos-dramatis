from fastapi.testclient import TestClient

from dramatis import drafting, slop
from dramatis.cards import card
from dramatis.character import Character, for_adventure, for_companion, for_dungeon, problems
from dramatis.main import create_app
from tests.helpers import SLEEP, reply

PSYCHE = {'was': {'text': 'the eldest who fixed everyone else'},
          'expected': {'text': 'the one who never needs help', 'pressed_by': ['a1b2c3d4e5f6']},
          'wants_to_be': {'text': 'someone with a day off'},
          'fears_becoming': {'text': 'her mother, bitter at sixty'}}


def made(**changes) -> Character:
    return Character.model_validate({'name': 'Dana Okafor', 'about': 'An ER nurse.', 'background': 'Grew up in Dundalk.',
                                     'sees_self': 'I keep things moving.', 'companion': {'schedule': [SLEEP]},
                                     'psyche': PSYCHE} | changes)


def test_an_empty_psyche_saves_as_null():
    assert made(psyche={'was': {'text': ''}}).psyche is None
    assert made(psyche=None).psyche is None
    assert made(psyche={'was': {'pressed_by': ['a1b2c3d4e5f6']}}).psyche is not None


def test_the_psyche_round_trips_through_the_library():
    api = TestClient(create_app())
    saved = api.post('/api/characters', json={'character': made().model_dump()}).json()
    loaded = api.get(f"/api/characters/{saved['id']}").json()['character']
    assert loaded['psyche']['expected'] == {'text': 'the one who never needs help', 'pressed_by': ['a1b2c3d4e5f6']}
    empty = api.post('/api/characters', json={'character': made(psyche={'was': {'text': ''}}).model_dump()}).json()
    assert empty['character']['psyche'] is None


def test_each_app_gets_the_psyche_where_it_reads_it():
    character = made()
    companion = for_companion(character)
    assert companion['background'] == 'Grew up in Dundalk.\n\nWho they were: the eldest who fixed everyone else.'
    assert companion['sees_self'].split('\n') == [
        'I keep things moving.', 'People expect me to be: the one who never needs help',
        'I want to be: someone with a day off', "I'm afraid of turning into: her mother, bitter at sixty"]
    adventure = for_adventure(character)['made']['sees_self']
    assert adventure == companion['sees_self'] and 'eldest' not in adventure
    assert for_dungeon(character)['persona']['about'].endswith('Who they were: the eldest who fixed everyone else.')
    # Library ids never leave the extension.
    full = card(character, '', '')
    assert 'a1b2c3d4e5f6' not in str(full['data']['extensions']['prospero']['apps'])
    assert full['data']['extensions']['prospero']['character']['psyche']['expected']['pressed_by'] == ['a1b2c3d4e5f6']


def test_psyche_lines_drop_from_last_to_first_and_their_own_text_is_never_cut():
    own = 'y' * 1140
    character = made(sees_self=own)
    sees_self = for_companion(character)['sees_self']
    assert sees_self == own + '\nPeople expect me to be: the one who never needs help'
    assert for_adventure(character)['made']['sees_self'] == sees_self
    full = made(sees_self='z' * 1200)
    assert for_companion(full)['sees_self'] == 'z' * 1200
    assert problems(full) == {} and problems(made(background='b' * 12000)) == {}


def test_a_draft_always_writes_the_psyche_and_a_paste_only_from_its_text(model):
    picks = {'idea': 'a night nurse', 'apps': ['adventure']}
    psyche = {'was': 'a lifeguard', 'expected': 'x', 'wants_to_be': 'y', 'fears_becoming': 'z'}
    model.replies = [reply(psyche=psyche)]
    found = drafting.draft(picks)['character']['psyche']
    assert found['was'] == {'text': 'a lifeguard', 'pressed_by': []} and '"psyche": {"was"' in model.asked[0][0]
    model.replies = [reply(psyche=psyche, filled_in=[])]
    assert drafting.split(picks | {'text': 'Dana is a night nurse.'})['character']['psyche'] is None
    assert '"psyche"' not in model.asked[1][0]
    model.replies = [reply(psyche=psyche | {'expected': ''}, filled_in=[])]
    found = drafting.split(picks | {'text': 'Dana is a night nurse who used to be a lifeguard.'})['character']['psyche']
    assert found['was'] == {'text': 'a lifeguard', 'pressed_by': []} and found['expected']['text'] == ''


def test_a_split_never_lists_the_psyche_as_filled_in(model):
    model.replies = [reply(psyche={'was': 'a lifeguard'}, filled_in=['psyche', 'fears'], schedule=[SLEEP])]
    found = drafting.split({'text': 'Dana used to be a lifeguard.', 'apps': ['companion']})
    assert found['filled_in'] == ['fears'] and found['character']['psyche']['was']['text'] == 'a lifeguard'


def test_help_me_write_and_the_audit_cover_each_impulse(model):
    model.replies = ['{"value": "the one everyone calls at 3am"}']
    found = drafting.rewrite(made().model_dump(), 'psyche.expected')
    assert found['value'] == 'the one everyone calls at 3am'
    assert 'a1b2c3d4e5f6' not in model.asked[0][0]
    hits = slop.audit(made(psyche={'wants_to_be': {'text': 'a woman named Elara'}}).model_dump())
    assert [hit['field'] for hit in hits if hit['severity'] == 'hard'] == ['psyche.wants_to_be']

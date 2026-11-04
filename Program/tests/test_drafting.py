import json

import pytest

from dramatis import drafting
from dramatis.formats.companion.errors import DomainError
from tests.helpers import SLEEP, WORK, reply

PICKS = {'idea': 'a shy night nurse', 'name': '', 'gender': '', 'age': None, 'setting': 'Baltimore, today',
         'vibe': '', 'apps': ['companion', 'adventure', 'dungeon'], 'relationship': 'friendship', 'timezone': '',
         'emotional_edges': False}


def system_of(model) -> str:
    return model.asked[0][0]


def test_a_draft_comes_back_shaped_with_the_users_picks_winning(model):
    model.replies = [reply()]
    found = drafting.draft(PICKS | {'name': 'Dana Price', 'relationship': 'romance'})
    character = found['character']
    assert character['name'] == 'Dana Price'
    assert character['age'] == 38 and character['gender'] == 'woman' and character['setting'] == 'Baltimore, today'
    assert character['companion']['relationship'] == 'romance'
    assert character['companion']['texting']['lowercase'] is True
    # How others see them and how they see themselves are drafted, apart from plain looks.
    assert character['seen_as'].startswith('Comes across as curt') and character['sees_self'].startswith('I am')
    # How they talk and how they sound stay two fields.
    assert character['sound'] == 'A low, slightly hoarse alto, unhurried.' and 'never personality or their name' in system_of(model)
    # Emotional edges stay off unless asked for.
    assert character['companion']['emotional_traits'] == [] and character['companion']['absence_reaction'] == ''
    # "shy" settles a slider from the user's own idea; the rest are rolled.
    assert character['personality_sliders']['social'] == {'level': 0, 'source': 'idea'}
    system, _ = model.asked[0]
    assert 'Where and when they come from: Baltimore, today' in system and '"schedule"' in system
    assert 'Needs time alone to recharge' in system and found['seed']


def test_without_companion_no_everyday_life_is_asked_for(model):
    model.replies = [reply(schedule=[])]
    found = drafting.draft(PICKS | {'apps': ['adventure']})
    assert found['character']['companion']['schedule'] == []
    assert '"schedule"' not in model.asked[0][0]


def test_a_reply_that_cannot_be_used_is_asked_for_again_with_the_problem(model):
    model.replies = ['Sure! Here you go: {"name": "Dana"', reply(personality='')]
    with pytest.raises(DomainError) as refused:
        drafting.draft(PICKS)
    assert refused.value.code == 'draft_unusable' and 'left out personality' in refused.value.message
    assert 'did not contain a JSON object' in model.asked[1][1]
    # On the retry, a week without sleep every day is kept as far as it goes rather than refused.
    model.replies = [reply(schedule=[WORK]), reply(schedule=[WORK])]
    assert drafting.draft(PICKS)['character']['companion']['schedule'] == [WORK | {'key': ''}]
    model.replies = [reply(schedule=[WORK]), reply(schedule=[WORK, SLEEP])]
    assert drafting.draft(PICKS)['character']['companion']['schedule'][1]['kind'] == 'sleep'
    assert 'sleep blocks that cover every day' in model.asked[-1][1]


def test_characters_are_adults(model):
    with pytest.raises(DomainError):
        drafting.draft(PICKS | {'age': 16})
    model.replies = [reply(age=15)]
    with pytest.raises(DomainError):
        drafting.draft(PICKS)
    model.replies = [json.dumps({'under_18': True})]
    with pytest.raises(DomainError):
        drafting.split(PICKS | {'text': 'A teenager.'})


def test_a_pasted_character_is_split_and_names_what_was_filled_in(model):
    model.replies = [reply(filled_in=['fears', 'name', 'nonsense'], emotional_traits=[])]
    found = drafting.split(PICKS | {'text': 'Dana {{char}} works nights. {weird braces}'})
    assert found['filled_in'] == ['fears']
    assert '{weird braces}' in model.asked[0][0]


def test_one_field_is_rewritten_to_fit(model):
    model.replies = ['{"value": ["Bakes bread badly", "Bakes bread badly", "Fixes bikes"]}']
    found = drafting.rewrite({'name': 'Dana', 'skills': ['x']}, 'skills', 'more practical')
    assert found == {'field': 'skills', 'value': ['Bakes bread badly', 'Fixes bikes'], 'audit': []}
    assert 'What the user wants changed: more practical' in model.asked[0][0]
    with pytest.raises(DomainError):
        drafting.rewrite({}, 'apps')

import pytest
from pydantic import ValidationError

from dramatis.character import Character, for_adventure, for_companion, for_dungeon, problems, shapes
from tests.helpers import SLEEP


def made(**changes) -> Character:
    return Character.model_validate({
        'name': 'Dana Okafor', 'gender': 'woman', 'age': 38, 'about': 'An ER nurse.', 'wants': 'Day shifts',
        'fears': 'Mistakes.', 'background': 'Grew up in Dundalk.', 'looks': {'hair': 'cropped grey'},
        'personality_sliders': {'social': {'level': 0, 'source': 'rolled'}},
        'companion': {'schedule': [SLEEP], 'relationship': 'mentor'}} | changes)


def test_every_app_takes_a_whole_character():
    character = made()
    assert problems(character) == {}
    assert set(shapes(character)) == {'companion', 'adventure', 'dungeon'}


def test_companion_reads_wants_and_fears_in_the_background_and_age_in_its_looks():
    definition = for_companion(made())
    assert definition['identity'] == 'An ER nurse.'
    assert definition['background'] == 'Grew up in Dundalk.\n\nWhat they want: Day shifts. What they fear: Mistakes.'
    assert definition['looks']['age'] == 38 and definition['looks']['hair'] == 'cropped grey'
    assert definition['relationship'] == 'mentor' and definition['timezone'] == 'UTC'
    assert definition['schedule'][0]['kind'] == 'sleep'


def test_adventure_and_dungeon_get_a_persona_and_adventure_its_made_character():
    adventure = for_adventure(made())
    assert adventure['persona']['name'] == 'Dana Okafor' and adventure['persona']['gender'] == 'woman'
    assert adventure['made']['wants'] == 'Day shifts' and adventure['made']['looks']['age'] == 38
    assert adventure['made']['personality_sliders']['social'] == {'level': 0, 'source': 'rolled'}
    assert for_dungeon(made())['persona']['about'] == ('An ER nurse.\n\nWhat they want: Day shifts.\n\n'
                                                       'What they fear: Mistakes.')


def test_dungeon_gets_the_whole_character_in_about_you_as_far_as_it_fits():
    character = made(appearance='Tall.', voice='Dry.', skills=['triage', 'night driving'], flaws=['curt'],
                     arc={'lie': 'asking for help gets you left', 'truth': ''},
                     secret={'truth': 'She failed her exam twice', 'cover_story': '', 'known_by': ''})
    about = for_dungeon(character)['persona']['about'].split('\n\n')
    assert about == ['An ER nurse.', 'How they look: Tall.', 'How they talk: Dry.', 'What they want: Day shifts.',
                     'What they fear: Mistakes.', 'Skills: triage; night driving.', 'Flaws: curt.',
                     'They tell themselves asking for help gets you left.',
                     'Something they keep to themselves: She failed her exam twice.']
    crowded = for_dungeon(made(about='x' * 1990, appearance='Tall.'))['persona']['about']
    assert crowded == 'x' * 1990  # Their own About is kept whole; what doesn't fit stays out.
    assert for_dungeon(made(about='', wants='', fears=''))['persona']['about'] is None


def test_how_others_see_them_reaches_every_app_that_feeds_it_to_other_characters():
    character = made(seen_as='Comes across as curt; always early.', sees_self='I keep things moving.')
    assert for_companion(character)['seen_as'] == 'Comes across as curt; always early.'
    assert for_adventure(character)['made']['seen_as'] == 'Comes across as curt; always early.'
    assert for_adventure(character)['made']['sees_self'] == 'I keep things moving.'


def test_a_long_lived_kind_keeps_its_age_out_of_companion_looks():
    character = made(age=400, kind='elf', lifespan=1000)
    assert for_companion(character)['looks'].get('age') is None
    assert for_adventure(character)['persona']['age'] == 400


def test_the_shared_limits_are_the_tightest_apps():
    with pytest.raises(ValidationError):
        made(voice='x' * 601)
    with pytest.raises(ValidationError):
        made(age=17)
    with pytest.raises(ValidationError):
        made(lifespan=90)
    with pytest.raises(ValidationError):
        made(companion={'schedule': [{'label': 'Nap', 'start': '10:00', 'end': '10:00'}]})


def test_a_user_persona_goes_to_companion_as_a_persona_not_a_companion():
    character = made(appearance='Tall, freckled, red hair.', companion={'schedule': [SLEEP], 'relationship': 'persona'})
    assert character.is_persona() and problems(character) == {}
    shaped = for_companion(character)
    assert set(shaped) == {'persona'}
    assert shaped['persona']['name'] == 'Dana Okafor' and shaped['persona']['about'] == 'An ER nurse.'
    assert shaped['persona']['looks'] == 'Tall, freckled, red hair.' and shaped['persona']['age'] == 38
    assert for_dungeon(character)['persona'] == for_dungeon(made(appearance='Tall, freckled, red hair.'))['persona']

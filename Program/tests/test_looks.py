import json

from dramatis import drafting, looks
from dramatis.character import Character
from dramatis.formats.companion import looks as companion_looks
from tests.helpers import reply
from tests.test_drafting import PICKS


def test_what_their_words_speak_of_is_read_from_them_and_the_rest_is_rolled():
    plan = looks.Plan('seed-1', words='a nurse with red hair and soft freckles, curvy', gender='woman', age=34)
    assert plan.words == ['build', 'hair', 'feature']
    # The weight waits for the build their words give; nothing their words speak of is rolled.
    assert not {'build', 'hair', 'feature', 'weight_kg'} & set(plan.rolled)
    assert plan.rolled['height_cm'] and plan.rolled['skin'] and plan.rolled['eyes']
    assert 'Height: ' in plan.brief() and '"looks": {"build"' in plan.shape()


def test_a_roll_is_the_roll_companion_makes_for_the_same_seed():
    plan = looks.Plan('seed-2', gender='man', age=30)
    stand_in = {'key': 'seed-2', 'seed': 'seed-2', 'age': 30, 'pronouns': 'he/him', 'heritage': '', 'goals': [''],
                'occupation': ''}
    drawn = companion_looks.drawn('seed-2', stand_in, {'era': 'modern'})
    assert plan.rolled == {field: drawn[field] for field in looks.FIELDS if drawn[field]}
    assert looks.Plan('seed-2', gender='man', age=30).rolled == plan.rolled


def test_settling_keeps_their_words_rolls_what_is_left_and_fits_the_weight_to_their_build():
    plan = looks.Plan('seed-3', words='curvy, with red hair', gender='woman', age=34)
    found, sources = plan.settle({'build': 'curvy', 'hair': 'copper-red hair, clipped up'},
                                 'She has copper-red hair clipped up and wears leggings.')
    assert found['build'] == 'curvy' and sources['build'] == sources['hair'] == 'idea'
    assert sources['height_cm'] == 'rolled' and sources['weight_kg'] == 'rolled'
    assert found['weight_kg'] == companion_looks.weight_kg('seed-3', found['height_cm'], 'curvy')
    assert Character.model_validate({'looks': found, 'looks_from': sources}).looks.build == 'curvy'


def test_heights_and_weights_come_in_whatever_units_the_model_uses():
    assert looks.number('height_cm', '5\'5"') == 165 and looks.number('height_cm', '170 cm') == 170
    assert looks.number('weight_kg', '130 lb') == 59 and looks.number('weight_kg', 61.4) == 61
    assert looks.number('height_cm', 400) is None and looks.number('height_cm', True) is None


def test_another_kind_of_being_gets_its_size_from_their_words_and_a_period_gets_no_tattoo_sleeve():
    plan = looks.Plan('seed-4', words='a grumpy dwarf smith', setting='a fantasy kingdom', gender='man', age=140)
    assert {'height_cm', 'build', 'skin'} <= set(plan.words) and 'weight_kg' not in plan.rolled
    assert looks.era_of('a frontier town in 1870') == 'period' and looks.era_of('Baltimore, today') == 'modern'
    assert looks.era_of('a starship in 2240') == 'future'


def test_a_draft_writes_the_appearance_from_the_settled_details(model):
    model.replies = [reply(looks={'build': 'curvy', 'hair': 'thick copper-red hair, usually clipped up'})]
    found = drafting.draft(PICKS | {'idea': 'a night nurse with red hair, curvy', 'gender': 'woman', 'age': 34})
    character = found['character']
    system = model.asked[0][0]
    # The rolled details go to the model as facts before it writes, and the ones their words speak of are asked for.
    assert 'Their looks, decided by the app.' in system and f"Height: {looks.line('height_cm', character['looks']['height_cm'])}" in system
    assert '"looks": {"build"' in system and 'describe their build and hair' in system
    assert character['looks']['hair'] == 'thick copper-red hair, usually clipped up'
    assert character['looks_from']['hair'] == 'idea' and character['looks_from']['height_cm'] == 'rolled'
    assert character['looks']['weight_kg'] and all(character['looks'][field] for field in ('skin', 'eyes', 'face'))
    # The marks stay out of every prompt.
    assert 'looks_from' not in json.dumps(drafting.for_model(character))


def test_a_pasted_character_keeps_the_looks_it_gives(model):
    model.replies = [reply(looks={'height_cm': '5\'5"', 'hair': 'a grey buzz cut'}, filled_in=[])]
    found = drafting.split(PICKS | {'text': 'Dana is 5\'5" with a grey buzz cut. Works nights.'})
    character = found['character']
    assert character['looks']['height_cm'] == 165 and character['looks_from']['height_cm'] == 'idea'
    assert character['looks']['hair'] == 'a grey buzz cut' and 'Height:' not in model.asked[0][0]


def test_the_hair_their_words_give_steers_the_colouring_rolled_around_it():
    assert looks.heritage('a nurse with red hair') == 'irish' and looks.heritage('a blonde barista') == 'english'
    assert looks.heritage('a Nigerian nurse with red hair') == 'nigeria' and looks.heritage('a nurse') == ''
    skins = {looks.Plan(f'seed-{n}', words='red hair', gender='woman').rolled['skin'] for n in range(30)}
    assert skins <= {'very fair', 'fair', 'light', 'light olive'}


def test_the_everyday_detail_is_rolled_and_no_mark_is_left_to_the_model():
    plan = looks.Plan('seed-5', gender='woman', age=30)
    assert f'An everyday detail: {plan.everyday}' in plan.brief() and 'Give them no scar' in plan.brief()
    details = {looks.Plan(f'seed-{n}', gender='woman').everyday for n in range(40)}
    assert len(details) > 15
    period = {looks.Plan(f'seed-{n}', setting='a frontier town in 1870').everyday for n in range(60)}
    assert not period & set(looks.everyday_bank()['modern'])


def test_the_stock_eyebrow_scar_is_worth_a_look():
    from dramatis import slop
    text = 'Her knuckles are scraped, and she has a faint chickenpox scar above her left eyebrow.'
    rules = {hit['rule'] for hit in slop.scan(text)}
    assert rules == {'Stock looks'} and all(hit['severity'] == 'flag' for hit in slop.scan(text))
    assert slop.scan('a small scar breaking through his right eyebrow')
    # Companion's own rolled detail is not the stock one.
    assert not slop.scan('a scar through one eyebrow')

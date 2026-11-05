import json

from fastapi.testclient import TestClient

from dramatis import drafting, names, slop
from dramatis.formats.companion import naming
from dramatis.main import create_app
from tests.helpers import reply

PICKS = {'idea': '', 'name': '', 'gender': '', 'age': None, 'setting': '', 'vibe': '', 'apps': ['dungeon'],
         'relationship': 'friendship', 'timezone': '', 'emotional_edges': False}


def feminine(given: str) -> bool:
    """Whether Companion's birth-year lists give this name to girls anywhere."""
    return any(given in cohort['feminine'] for culture in naming.data()['cultures'].values()
               for cohort in culture['cohorts'])


def test_a_setting_reads_as_the_place_companion_would_name_them_in():
    assert names.Place().city() == {'id': '', 'era': 'modern', 'country': '', 'names': None}
    assert names.Place('Victorian London').city()['era'] == 'victorian'
    assert names.Place('a mining camp in the wild west').city()['era'] == 'frontier'
    assert names.Place('a fantasy kingdom of elves').city()['era'] == 'fantasy'
    assert names.Place('Kyoto in the Edo period').city()['names'] == {'bank': 'edo-japan'}
    assert names.Place('Chicago, 1925').city() == {'id': '', 'era': 'jazz-age', 'country': '', 'names': {'year': 1925}}
    assert names.Place('Baltimore in 1987').city()['names'] == {'year': 1987}
    assert names.Place('Osaka, Japan').city() == {'id': '', 'era': 'modern', 'country': 'japan',
                                                  'names': {'mix': {'anglo': 1.0}}}
    assert names.Place('Victorian Dublin, Ireland').city()['names'] == {'mix': {'irish': 1.0}}


def test_a_people_their_idea_names_is_where_half_their_names_come_from():
    place = names.Place('Houston', 'a Korean grandmother')
    assert place.kin == 'korea' and place.city()['country'] == '' and place.city(kin=True)['country'] == 'south korea'
    assert names.Place('Seoul, South Korea', 'a Korean grandmother').kin is None
    cultures = {naming.local_culture(names.Place('Houston', 'a Korean grandmother').city(kin)['country']) for kin in
                (False, True)}
    assert cultures == {'us', 'korea'}


def test_offered_names_fit_their_age_and_gender_and_are_never_on_the_audit_list():
    roll = names.Roll('seed', gender='woman', age=40)
    offered = roll.candidates()
    assert len(offered) >= 6 and all(37 <= age <= 43 for _name, age in offered)
    assert all(feminine(name.split()[0]) for name, _age in offered)
    given, family = roll.others()
    assert not any(slop.scan(name) for name in [*(name for name, _age in offered), *given, *family])
    assert names.Roll('seed', gender='woman', age=40).candidates() == offered


def test_a_name_the_audit_flags_is_drawn_again(monkeypatch):
    calls = []

    def flagged(city, **kwargs):
        calls.append(kwargs['seed'])
        return {'given': 'Nora' if len(calls) == 1 else 'Dana', 'family': 'Smith',
                'full': ('Nora' if len(calls) == 1 else 'Dana') + ' Smith'}

    monkeypatch.setattr(names.generators, 'name', flagged)
    assert names.Roll('seed').drawn('one')['full'] == 'Dana Smith' and len(calls) == 2


def test_a_draft_with_no_name_chooses_from_drawn_ones_and_one_with_a_name_does_not(model):
    model.replies = [reply()]
    drafting.draft(PICKS | {'age': 45, 'setting': 'Victorian London'})
    system = model.asked[0][0]
    assert 'choose one of these names, which people their age commonly have' in system
    assert 'Their parents and siblings share their family name' in system
    model.replies = [reply()]
    drafting.draft(PICKS | {'name': 'Dana Okafor'})
    system = model.asked[1][0]
    assert 'choose one of these names' not in system and 'Their parents and siblings share' in system


def test_help_me_write_offers_names_only_where_people_turn_up(model):
    model.replies = [json.dumps({'value': 'Grew up in Dundalk.'}), json.dumps({'value': 'Dry and short.'})]
    drafting.rewrite({'name': 'Dana', 'setting': 'Osaka, Japan'}, 'background')
    drafting.rewrite({'name': 'Dana'}, 'voice')
    assert 'Anyone it mentions who has no name yet' in model.asked[0][0]
    assert 'Anyone it mentions' not in model.asked[1][0]


def test_help_me_write_swaps_a_stock_name_it_keeps_after_the_retry(model):
    model.replies = [json.dumps({'value': 'Her mother Seraphina raised her.'})] * 2
    found = drafting.rewrite({'name': 'Dana Okafor', 'gender': 'woman'}, 'background')
    assert 'Seraphina' not in found['value'] and found['value'].startswith('Her mother ')
    assert not slop.hard(found['audit'])


def test_roll_a_name_draws_one_from_what_the_form_says_with_no_model():
    client = TestClient(create_app())
    found = client.post('/api/names/roll', json={'gender': 'woman', 'age': 34, 'setting': '', 'about': ''}).json()
    assert feminine(found['name'].split()[0]) and not slop.scan(found['name'])
    victorian = client.post('/api/names/roll', json={'gender': 'man', 'setting': 'Victorian London'}).json()['name']
    groups = names.catalog.names()['banks']['victorian'].values()
    assert victorian.split()[-1] in {family for group in groups for family in group['family']} | \
        {family for key in ('england-wales', 'ireland', 'scotland', 'italy', 'jewish-diaspora')
         for family in naming.culture(key)['surnames']}

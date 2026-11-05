import json

import pytest

from dramatis import drafting, slop
from dramatis.formats.companion.errors import DomainError
from tests.helpers import reply

PICKS = {'idea': '', 'name': '', 'gender': '', 'age': None, 'setting': '', 'vibe': '', 'apps': ['dungeon'],
         'relationship': 'friendship', 'timezone': '', 'emotional_edges': False}


def test_hard_hits_are_names_dashes_and_the_assistants_voice():
    found = slop.scan('Elara Voss works nights — mostly. Feel free to ask.')
    assert {hit['match'] for hit in found if hit['severity'] == 'hard'} >= {'Elara', 'Voss', '—', 'Feel free to'}


def test_ordinary_text_passes_and_flags_are_only_flags():
    assert slop.scan('Works 07:00-19:30. Ash on the grate.') == []
    found = slop.scan('A vibrant woman with an ash-blond bob. She met Ash later.')
    assert [(hit['severity'], hit['match']) for hit in found] == [('hard', 'Ash'), ('flag', 'vibrant')]


def test_the_audit_reads_every_field_and_leaves_the_users_own_words():
    character = {'name': 'Kael Thorne', 'skills': ['Delves into old maps'], 'companion': {'routine': 'Ever since.'}}
    hits = slop.audit(character)
    assert {(hit['field'], hit['match']) for hit in hits} >= {('name', 'Kael'), ('name', 'Thorne'), ('skills', 'Delves')}
    assert not [hit for hit in slop.audit(character, allowed='Call him Kael Thorne') if hit['field'] == 'name']


def test_a_draft_with_stock_names_is_sent_back_once(model):
    model.replies = [reply(name='Elara Voss', background='Grew up by the sea — mostly.'), reply()]
    found = drafting.draft(PICKS)
    assert found['character']['name'] == 'Dana Okafor' and not slop.hard(found['audit'])
    retry = model.asked[1][1]
    assert 'Elara (Name)' in retry and 'instead of dashes' in retry
    # The list itself is never in the drafting prompt.
    assert 'Seraphina Vale' not in model.asked[0][0]


def test_what_survives_the_retry_comes_back_for_the_form(model):
    model.replies = [reply(background='Grew up by the sea — mostly.')] * 2
    found = drafting.draft(PICKS)
    assert {hit['match'] for hit in slop.hard(found['audit'])} == {'—'}


def test_a_stock_name_kept_after_the_retry_is_swapped_for_a_drawn_one_everywhere(model):
    kept = reply(name='Elara Voss', about='Elara is 38 and works nights.', background='The Voss family ran a bakery. '
                 'Her friend Kaelith Duskwhisper moved away.')
    model.replies = [kept, kept]
    found = drafting.draft(PICKS | {'gender': 'woman'})
    character = found['character']
    given = character['about'].removesuffix(' is 38 and works nights.')
    family = character['background'].split(' family ran')[0].removeprefix('The ')
    assert character['name'].startswith(f'{given} ') and character['name'].endswith(f' {family}')
    assert not {'Elara', 'Voss', 'Kaelith', 'Duskwhisper'} & set(json.dumps(character).replace('"', ' ').split())
    assert not slop.hard(found['audit'])


def test_made_up_names_are_hard_hits():
    found = slop.scan('Raised by Vaelith Ravencrest in a village of farmers. Mary Smith taught her to read.')
    assert [(hit['rule'], hit['match']) for hit in slop.hard(found)] == [
        (slop.MADE_UP, 'Vaelith'), (slop.MADE_UP, 'Ravencrest')]


def test_a_name_the_user_asked_for_is_theirs(model):
    model.replies = [reply(name='Elara Voss')]
    found = drafting.draft(PICKS | {'name': 'Elara Voss'})
    assert found['character']['name'] == 'Elara Voss' and not slop.hard(found['audit'])
    model.replies = [json.dumps({'value': 'Elara keeps the ledger.'}), json.dumps({'value': 'Keeps the books.'})]
    rewritten = drafting.rewrite({'name': 'Dana'}, 'about')
    assert rewritten['value'] == 'Keeps the books.'
    model.replies = [json.dumps({'value': 'Elara keeps the books.'})]
    assert drafting.rewrite({'name': 'Elara'}, 'about')['value'] == 'Elara keeps the books.'


def test_an_unusable_reply_still_fails_plainly(model):
    model.replies = ['nothing', 'nothing']
    with pytest.raises(DomainError):
        drafting.draft(PICKS)


def test_wikipedias_signs_are_read_with_wrens_list():
    found = slop.scan("Here is a character: [Insert name] stands as a reminder of home, reflecting her roots.")
    assert {(hit['severity'], hit['match']) for hit in found} == {
        ('hard', 'Here is a'), ('hard', '[Insert name]'), ('flag', 'stands as'), ('flag', 'a reminder of'),
        ('flag', ', reflecting')}
    found = slop.scan("You're absolutely right. Not only a smith but a poet, quietly. No maps, no plans, just nerve.")
    assert [hit['severity'] for hit in found][:1] == ['hard'] and len(found) == 4


def test_card_macros_and_ordinary_brackets_are_not_placeholders():
    assert slop.scan('Calls {{user}} by a nickname [sometimes]. Here is where she lives.') == []

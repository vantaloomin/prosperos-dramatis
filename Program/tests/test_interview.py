import json

import pytest
from fastapi.testclient import TestClient

from dramatis import ai, interview
from dramatis.formats.companion.errors import DomainError
from dramatis.main import create_app

CHARACTER = {'name': 'Dana Okafor', 'about': 'An ER nurse in Baltimore.', 'voice': 'Short sentences, dry jokes.',
             'sound': 'A low alto.', 'flaws': ['Cancels plans when tired'], 'interests': ['duckpin bowling'],
             'secret': {'truth': 'She stole morphine once.'}, 'personality_sliders': {'social': {'level': 0}}}
TRANSCRIPT = ('**What do you do?**\n\n"Nights. ER." She rubs her eye with the heel of her hand. "Somebody has to."\n\n'
              '**What do you love?**\n\n"Bowling. Duckpin, not the big balls."')


def answer(**changes) -> str:
    return json.dumps({'interview': TRANSCRIPT, 'sample': 'Somebody has to.'} | changes)


def test_the_interview_comes_back_with_a_sample_from_it(model):
    model.replies = [answer()]
    found = interview.interview(CHARACTER)
    assert found['interview'] == TRANSCRIPT and found['sample'] == 'Somebody has to.' and found['audit'] == []
    system = model.asked[0][0]
    # The secret never reaches the interview, so a card exported without it carries no trace of it.
    assert 'morphine' not in system and 'Dana Okafor' in system and 'Needs time alone to recharge' in system


def test_a_sample_not_in_the_transcript_is_taken_from_it_instead(model):
    model.replies = [answer(sample='Something she never said.')]
    assert interview.interview(CHARACTER)['sample'] == 'Nights. ER.'


def test_the_transcript_is_trimmed_to_its_limit_at_a_paragraph(model):
    long = '\n\n'.join(f'**Question {number}?**\n\n"{"word " * 60}"' for number in range(80))
    model.replies = [answer(interview=long)]
    found = interview.interview(CHARACTER)['interview']
    assert len(found) <= interview.LIMIT and found.endswith('"')


def test_the_slop_audit_sends_a_stock_name_back_once(model):
    model.replies = [answer(interview=TRANSCRIPT + '\n\n"My friend Elara says so."'), answer()]
    found = interview.interview(CHARACTER)
    assert 'Elara' in model.asked[1][1] and found['interview'] == TRANSCRIPT


def test_an_empty_character_has_nothing_to_talk_from():
    with pytest.raises(DomainError) as refused:
        interview.interview({'name': 'Dana'})
    assert refused.value.status == 422


def test_without_a_model_the_routes_say_so(monkeypatch):
    monkeypatch.setattr(ai, 'api_key', lambda provider: '')
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    found = TestClient(create_app()).post('/api/draft/interview', json={'character': CHARACTER})
    assert found.status_code == 409 and 'No model is set up' in found.json()['error']


def test_proposals_are_only_for_listed_fields_and_never_sound(model):
    model.replies = [json.dumps({'proposals': [
        {'field': 'voice', 'value': 'Two or three words at a time; jokes flat.', 'reason': 'Her first answer.'},
        {'field': 'sound', 'value': 'Hoarse.', 'reason': 'x'},
        {'field': 'name', 'value': 'Dee', 'reason': 'x'},
        {'field': 'voice', 'value': 'A second voice.', 'reason': 'x'},
        {'field': 'interests', 'value': ['duckpin bowling'], 'reason': 'Nothing new.'},
        {'field': 'flaws', 'value': ['Cancels plans when tired', 'Rubs her eyes raw', 'x' * 400], 'reason': 'Habits.'},
        {'field': 'appearance', 'value': 'y' * 900, 'reason': 'Long.'}]})]
    found = interview.proposals(CHARACTER | {'interview': TRANSCRIPT})
    fields = [item['field'] for item in found['proposals']]
    assert fields == ['voice', 'flaws', 'appearance']
    assert found['proposals'][0]['value'] == 'Two or three words at a time; jokes flat.'
    assert all(len(item) <= 300 for item in found['proposals'][1]['value'])
    assert len(found['proposals'][2]['value']) == 600
    assert 'Nights. ER.' in model.asked[0][0] and 'morphine' not in model.asked[0][0]


def test_proposals_need_an_interview_and_go_through_the_api(model):
    api = TestClient(create_app())
    assert api.post('/api/draft/from-interview', json={'character': CHARACTER}).status_code == 422
    model.replies = [json.dumps({'proposals': []})]
    found = api.post('/api/draft/from-interview', json={'character': CHARACTER | {'interview': TRANSCRIPT}})
    assert found.json() == {'proposals': [], 'audit': []}

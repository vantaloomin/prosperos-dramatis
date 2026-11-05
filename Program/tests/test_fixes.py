import json

import pytest
from fastapi.testclient import TestClient

from dramatis import fixes, slop
from dramatis.formats.companion.errors import DomainError
from dramatis.main import create_app

CIARA = {
    'name': 'Ciara McCann', 'about': 'Married to Michael Hale, 38, who is also her handler.',
    'sound': 'Northern Irish accent, slightly husky, gets louder when she is cross.',
    'interview': '"Don\'t put that in." A beat. "That was a joke."',
    'skills': ['reads maps upside down', 'a vibrant cook'],
    'secret': {'truth': 'She informs on her own street.', 'cover_story': 'She works at the council.'},
    'arc': {'lie': 'Nobody would miss her, the husky fool.'},
}


def picked(character: dict, *matches: str) -> list[dict]:
    return [hit for hit in slop.audit(character) if hit['match'] in matches]


def test_only_the_marked_words_change(model):
    model.replies = [json.dumps({'spans': {'1': 'Moore', '2': 'Belfast'}})]
    found = fixes.fix(CIARA, picked(CIARA, 'Hale', 'Irish'))
    assert {item['field']: item['value'] for item in found['fields']} == {
        'about': 'Married to Michael Moore, 38, who is also her handler.',
        'sound': 'Northern Belfast accent, slightly husky, gets louder when she is cross.'}
    asked = model.asked[0][0]
    assert '[[1]]Hale[[/1]]' in asked and '[[2]]Irish[[/2]]' in asked and 'Overdrawn surnames' in asked
    # Help me write's rule: a field anyone may read is written without their secret in front of the model.
    assert 'informs on her own street' not in asked and 'works at the council' in asked


def test_overlapping_hits_are_one_span_and_an_empty_replacement_leaves_clean_text(model):
    model.replies = [json.dumps({'spans': {'1': ''}})]
    found = fixes.fix(CIARA, picked(CIARA, 'A beat', 'beat.'))
    assert found['fields'] == [{'field': 'interview', 'label': 'Interview', 'value': '"Don\'t put that in." "That was a joke."',
                                'audit': []}]


def test_a_list_item_changes_in_place(model):
    model.replies = [json.dumps({'spans': {'1': 'decent'}})]
    found = fixes.fix(CIARA, picked(CIARA, 'vibrant'))
    assert found['fields'][0]['value'] == ['reads maps upside down', 'a decent cook']


def test_what_may_say_their_secret_is_asked_apart(model):
    model.replies = [json.dumps({'spans': {'1': 'soft'}}), json.dumps({'spans': {'1': 'low'}})]
    found = fixes.fix(CIARA, picked(CIARA, 'husky'))
    assert {item['field']: item['value'] for item in found['fields']} == {
        'sound': 'Northern Irish accent, slightly low, gets louder when she is cross.',
        'arc.lie': 'Nobody would miss her, the soft fool.'}
    private, public = model.asked[0][0], model.asked[1][0]
    assert 'informs on her own street' not in public and 'informs on her own street' in private
    assert 'the [[1]]husky[[/1]] fool' in private


def test_an_unchanged_or_missing_replacement_is_sent_back_once(model):
    model.replies = [json.dumps({'spans': {'1': 'Hale'}}), json.dumps({'spans': {'1': 'Moore'}})]
    found = fixes.fix(CIARA, picked(CIARA, 'Hale'))
    assert 'Michael Moore' in found['fields'][0]['value']
    assert '1 was the marked words again' in model.asked[1][1]


def test_a_new_stock_name_is_sent_back_once(model):
    model.replies = [json.dumps({'spans': {'1': 'Voss'}}), json.dumps({'spans': {'1': 'Moore'}})]
    found = fixes.fix(CIARA, picked(CIARA, 'Hale'))
    assert 'Michael Moore' in found['fields'][0]['value'] and 'Voss (About them)' in model.asked[1][1]


def test_words_no_longer_there_are_a_plain_error(model):
    gone = picked(CIARA, 'Hale')
    with pytest.raises(DomainError) as raised:
        fixes.fix(CIARA | {'about': 'Married to Michael Moore.'}, gone)
    assert raised.value.status == 409 and not model.asked


def test_ignored_words_stay_off_the_audit():
    hits = slop.audit(CIARA | {'ignored_flags': ['Irish', 'Hale']})
    assert not {'Irish', 'Hale'} & {hit['match'] for hit in hits} and 'husky' in {hit['match'] for hit in hits}


def test_the_fix_and_check_routes(model):
    client = TestClient(create_app())
    model.replies = [json.dumps({'spans': {'1': 'Moore'}})]
    answer = client.post('/api/draft/fix', json={'character': CIARA, 'hits': picked(CIARA, 'Hale')})
    assert answer.status_code == 200 and answer.json()['fields'][0]['field'] == 'about'
    checked = client.post('/api/check', json={'character': CIARA | {'ignored_flags': ['Irish']}}).json()
    assert 'Irish' not in {hit['match'] for hit in checked['audit']}

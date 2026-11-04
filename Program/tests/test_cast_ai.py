import json

import pytest
from fastapi.testclient import TestClient

from dramatis import ai, cast_ai, casts, library, settings
from dramatis.character import Character
from dramatis.formats.companion.errors import DomainError
from dramatis.main import create_app
from tests.test_casts import board

WEB = {'title': 'Small Hours', 'theme': 'Can you keep a promise to someone who left?', 'genre': 'four-corner-web',
       'outer': {'axis': {'kind': 'dilemma', 'label': 'Stay for family, or go for yourself?'},
                 'corners': [{'id': 'a', 'label': 'Main', 'role': 'main', 'stance': 'Stays, and calls it love.'},
                             {'id': 'b', 'label': 'Challenger', 'role': 'challenger', 'stance': 'Left at nineteen.'},
                             {'id': 'c', 'label': 'Comforter', 'role': 'comforter', 'stance': 'Stayed too.'},
                             {'id': 'd', 'label': 'Warning', 'role': 'warning', 'stance': 'Stayed for forty years.'}]}}


def blank(**changes) -> dict:
    """A new political fantasy board, as the board makes one: four named sides with no stance yet."""
    sides = [{'id': key, 'label': label} for key, label in zip('abcd', ('The throne', 'The guilds', 'The temple',
                                                                         'The rebels'))]
    return {'title': '', 'theme': 'Who should the realm answer to?', 'genre': 'political-fantasy',
            'group': 'movement', 'outer': {'axis': {'kind': 'value'}, 'corners': sides}} | changes


def made(name: str, **more) -> str:
    return library.save(Character(name=name, about=f'{name}, for the test.', **more))['id']


def suggested(*proposals) -> str:
    return json.dumps({'proposals': list(proposals)})


def nothing_written():
    home = settings.home()
    assert not (home / 'casts').exists()


# ---- Suggest corners ----------------------------------------------------------------------------------------------

def test_suggestions_fill_the_empty_corners_and_keep_tags_the_bank_lacks(model):
    model.replies = [suggested(
        {'corner_id': 'a', 'label': 'The throne', 'stance': 'One crown, so the roads stay safe.',
         'tags': ['Law', 'Tradition', 'law']},
        {'corner_id': 'zz', 'label': 'The guilds', 'stance': 'Whoever pays the realm should run it.',
         'tags': ['Negotiating', 'bribes', 'Street Theatre']},
        {'label': 'The temple', 'stance': 'The realm belongs to the gods first.', 'tags': ['faith'], 'role': 'Priest'},
        {'corner_id': 'a', 'label': 'The rebels', 'stance': 'Nobody should rule anybody.', 'tags': 'revolt'},
        {'label': 'A fifth', 'stance': 'Too many.'}, {'label': '', 'stance': 'No name.'})]
    found = cast_ai.suggest(casts.checked(blank()), 'outer')
    proposals = found['proposals']
    assert [item['corner_id'] for item in proposals] == ['a', 'b', 'c', 'd']
    assert proposals[0]['tags'] == ['law', 'tradition']
    assert proposals[1]['tags'] == ['negotiation', 'bribes', 'street-theatre']  # out of the bank, and kept
    assert proposals[2]['role'] == 'priest' and proposals[3]['tags'] == ['revolt'] and found['audit'] == []
    system = model.asked[0][0]
    assert 'Who should the realm answer to?' in system and 'No therapy-speak' in system and 'negotiation' in system
    assert 'a (The throne), b (The guilds)' in system
    nothing_written()


def test_an_inner_suggestion_that_reads_as_a_value_is_still_returned_and_check_flags_it(model):
    cast = casts.checked(board())
    model.replies = [suggested({'label': 'The Believer', 'stance': 'Order itself, for its own sake.', 'tags': ['faith']},
                               {'label': 'The Clerk', 'stance': 'By keeping every record straight.',
                                'tags': ['rules']})]
    found = cast_ai.suggest(cast, 'a')
    assert [item['stance'] for item in found['proposals']] == ['Order itself, for its own sake.',
                                                               'By keeping every record straight.']
    # The Order is full (three corners, all with a stance), so both are new; the board says where each goes.
    assert [item['corner_id'] for item in found['proposals']] == [None, None]
    assert 'Each stance is a how' in model.asked[0][0] and 'How to keep order' in model.asked[0][0]

    with_it = board()
    with_it['outer']['corners'][0]['inner']['corners'].append(
        {'id': 'a4', 'label': 'The Believer', 'stance': 'Order itself, for its own sake.'})
    model.replies = [json.dumps({'flags': [
        {'corner_id': 'a4', 'reads_as': 'value', 'message': 'This is a why, not a how: say how they keep order.'},
        {'corner_id': 'a', 'reads_as': 'value', 'message': 'A side should read as a value, so this is fine.'},
        {'corner_id': 'nope', 'reads_as': 'method', 'message': 'Not on the board.'},
        {'corner_id': 'b1', 'reads_as': 'mood', 'message': 'Not a kind.'}], 'judgements': []})]
    flags = cast_ai.check(casts.checked(with_it))
    assert flags == {'flags': [{'corner_id': 'a4', 'reads_as': 'value',
                                'message': 'This is a why, not a how: say how they keep order.'}],
                     'judgements': [], 'audit': []}
    assert 'a4 (The Believer, in The Order\'s split): should read as a how' in model.asked[1][0]
    nothing_written()


def test_a_full_square_offers_alternatives_and_web_roles_get_their_fields(model):
    model.replies = [suggested(
        {'label': 'Challenger', 'stance': 'Went to the city and made it work.', 'role': 'challenger',
         'fields': {'way_of_living': 'Rents alone, calls home on Sundays.', 'why_appealing': 'She is happy.',
                    'stray': 'dropped'}},
        {'label': 'Warning', 'stance': 'Stayed until there was nothing left to stay for.', 'role': 'warning'})]
    found = cast_ai.suggest(casts.checked(WEB), 'outer')
    first, second = found['proposals']
    assert first['corner_id'] is None and first['fields'] == {'way_of_living': 'Rents alone, calls home on Sundays.',
                                                              'why_appealing': 'She is happy.'}
    assert second['fields'] == {'how_they_ended_up': '', 'wake_up_call': ''}
    assert 'a way of living with it' in model.asked[0][0] and 'challenger: fields way_of_living' in model.asked[0][0]


def test_a_malformed_reply_is_asked_for_again_and_refused_after_that(model):
    good = suggested({'label': 'The throne', 'stance': 'One crown.'}, {'label': 'The guilds', 'stance': 'Money.'})
    model.replies = ['Here are some ideas!', good]
    assert len(cast_ai.suggest(casts.checked(blank()), 'outer')['proposals']) == 2
    assert 'did not contain a JSON object' in model.asked[1][1]

    model.replies = [suggested({'label': 'Only one', 'stance': 'Alone.'}), '{"proposals": []}']
    with pytest.raises(DomainError) as refused:
        cast_ai.suggest(casts.checked(blank()), 'outer')
    assert refused.value.status == 502 and 'needs 2 to 4 proposals' in refused.value.message

    model.replies = [suggested({'label': 'Only one', 'stance': 'Alone.'}),
                     suggested({'label': 'Still one', 'stance': 'Alone again.'})]
    assert [item['label'] for item in cast_ai.suggest(casts.checked(blank()), 'outer')['proposals']] == ['Still one']


def test_a_stock_name_goes_back_once_but_the_authors_own_words_are_theirs(model):
    mine = blank()
    mine['outer']['corners'][0]['label'] = "Elara's Guard"
    model.replies = [suggested({'label': "Elara's Guard", 'stance': 'One crown keeps the roads safe.'},
                               {'label': 'The guilds', 'stance': 'Coin rules — always has.'}),
                     suggested({'label': "Elara's Guard", 'stance': 'One crown keeps the roads safe.'},
                               {'label': 'The guilds', 'stance': 'Coin rules, and always has.'})]
    found = cast_ai.suggest(casts.checked(mine), 'outer')
    assert 'proposals.1.stance' not in json.dumps(found['audit']) and found['audit'] == []
    assert 'dash' in model.asked[1][1] and 'Elara' not in model.asked[1][1].split('Your last reply could not')[1]


def test_suggestions_need_a_split_side_that_is_on_the_board(model):
    cast = casts.checked(board())
    with pytest.raises(DomainError) as refused:
        cast_ai.suggest(cast, 'c')
    assert refused.value.status == 422 and 'Split The Faithful first' in refused.value.message
    with pytest.raises(DomainError) as gone:
        cast_ai.suggest(cast, 'z')
    assert gone.value.status == 404
    assert model.asked == []


@pytest.mark.parametrize(('typed', 'banked'), [('Negotiating', 'negotiation'), ('FORCE', 'force'),
                                               ('forced', 'force'), ('Family ties', 'family-ties'),
                                               ('Hard work!', 'hard-work'), ('street theatre', 'street-theatre'),
                                               (7, '')])
def test_tags_are_matched_to_the_bank_where_they_can_be(typed, banked):
    assert cast_ai.bank_tag(typed) == banked


# ---- Check my square ----------------------------------------------------------------------------------------------

def test_the_web_template_gets_its_three_judgements(model):
    model.replies = [json.dumps({'flags': [{'corner_id': 'b', 'reads_as': 'method', 'message': 'This says what '
                                            'she did, not the answer she lives by.'}],
                                 'judgements': [
                                     {'code': 'challenger-has-flaw', 'holds': False, 'message': 'She has no cost.'},
                                     {'code': 'comforter-not-villain', 'holds': True, 'message': 'Fine.'},
                                     {'code': 'role-fields', 'holds': False, 'message': 'Not a judgement.'},
                                     {'code': 'warning-sympathetic', 'holds': 'yes', 'message': 'Not a yes or no.'}]})]
    found = cast_ai.check(casts.checked(WEB))
    assert found['flags'][0]['corner_id'] == 'b'
    assert found['judgements'] == [
        {'code': 'challenger-has-flaw', 'corner_id': 'b', 'holds': False, 'message': 'She has no cost.'},
        {'code': 'comforter-not-villain', 'corner_id': 'c', 'holds': True, 'message': 'Fine.'}]
    system = model.asked[0][0]
    assert 'challenger-has-flaw: Challenger should be tempting' in system and 'warning-sympathetic' in system


def test_a_goal_definition_split_is_read_leniently_and_an_empty_board_has_nothing_to_check(model):
    raw = board()
    raw['outer']['corners'][0]['inner']['axis'] = {'kind': 'goal-definition'}
    model.replies = [json.dumps({'flags': [], 'judgements': []})]
    assert cast_ai.check(casts.checked(raw)) == {'flags': [], 'judgements': [], 'audit': []}
    assert "In The Order's split the corners disagree about what winning means" in model.asked[0][0]
    assert 'Leave "judgements" as []' in model.asked[0][0]
    with pytest.raises(DomainError) as refused:
        cast_ai.check(casts.checked(blank()))
    assert refused.value.status == 422


# ---- Find the turn ------------------------------------------------------------------------------------------------

def linked_board() -> tuple[dict, str, str]:
    """The Salt Crown with the Pragmatist and the Negotiator played by two library characters, and their link
    confirmed."""
    ida = made('Ida Brandt', wants='To keep the harbour open.', flaws=['Lies when cornered'],
               secret={'truth': 'She sold the harbour plans.'})
    tom = made('Tom Achebe', wants='A seat at the table.', flaws=['Trusts the wrong people'])
    raw = board(resonance=[{'a': 'a2', 'b': 'b1', 'on': 'negotiation', 'status': 'confirmed', 'role': 'bridge'}])
    raw['outer']['corners'][0]['inner']['corners'][1]['character_id'] = ida
    raw['outer']['corners'][1]['inner']['corners'][0]['character_id'] = tom
    return raw, ida, tom


def test_the_turn_is_found_on_a_confirmed_link_and_kept_to_the_note(model):
    raw, _, _ = linked_board()
    long = 'Ida moves first, the night the harbour vote fails. ' * 12
    model.replies = [json.dumps({'turn': long}), json.dumps({'turn': long})]
    found = cast_ai.turn(casts.checked(raw), 'b1', 'a2')
    assert len(found['turn']) <= cast_ai.TURN and found['turn'].endswith('fails.')
    assert 'keep it within 400' in model.asked[1][1]
    system = model.asked[0][0]
    assert 'To keep the harbour open.' in system and 'Lies when cornered' in system and 'bridge' in system
    assert 'She sold the harbour plans.' in system  # a secret travels with the character, and may be the turn
    nothing_written()


def test_the_turn_needs_the_link_confirmed(model):
    raw, _, _ = linked_board()
    with pytest.raises(DomainError) as refused:
        cast_ai.turn(casts.checked(raw | {'resonance': []}), 'a2', 'b1')
    assert refused.value.status == 422 and model.asked == []


# ---- Suggest a relationship ---------------------------------------------------------------------------------------

def test_a_relationship_reads_one_side_s_wants_against_the_other_s_flaws(model):
    raw, ida, tom = linked_board()
    raw['relationships'] = [{'from': tom, 'to': ida, 'dynamic': 'Thinks she is the only honest one.'}]
    model.replies = [json.dumps({'dynamic': 'Sees him as useful and a little naive.',
                                 'hidden_tension': 'She needs him to trust the wrong people a while longer.',
                                 'trust': '4 out of 10'})]
    found = cast_ai.relationship(casts.checked(raw), ida, tom)
    assert found == {'proposal': {'dynamic': 'Sees him as useful and a little naive.',
                                  'hidden_tension': 'She needs him to trust the wrong people a while longer.',
                                  'trust': 4}, 'audit': []}
    system = model.asked[0][0]
    assert "what Ida Brandt wants against Tom Achebe's flaws" in system
    assert 'Trusts the wrong people' in system and 'Thinks she is the only honest one.' in system
    assert 'She sold the harbour plans.' in system
    nothing_written()


@pytest.mark.parametrize(('given', 'trust'), [(15, 10), (0, 1), ('none', 5), (True, 5), (7.6, 7)])
def test_trust_is_a_whole_number_from_1_to_10(given, trust):
    assert cast_ai.trust_value(given) == trust


def test_a_relationship_needs_two_characters_in_the_library(model):
    raw, ida, _ = linked_board()
    with pytest.raises(DomainError) as same:
        cast_ai.relationship(casts.checked(raw), ida, ida)
    assert same.value.status == 422
    with pytest.raises(DomainError) as gone:
        cast_ai.relationship(casts.checked(raw), ida, 'aaaaaaaaaaaa')
    assert gone.value.status == 404 and model.asked == []


# ---- The routes ---------------------------------------------------------------------------------------------------

def test_the_routes_answer_and_save_nothing(model):
    api = TestClient(create_app())
    raw, ida, tom = linked_board()
    model.replies = [suggested({'label': 'The throne', 'stance': 'One crown.'}, {'label': 'The guilds', 'stance': 'Coin.'}),
                     json.dumps({'flags': [], 'judgements': []}), json.dumps({'turn': 'Ida moves first.'}),
                     json.dumps({'dynamic': 'Useful.', 'hidden_tension': '', 'trust': 6})]
    assert len(api.post('/api/cast-ai/suggest', json={'cast': blank(), 'target': 'outer'}).json()['proposals']) == 2
    assert api.post('/api/cast-ai/check', json={'cast': raw}).json()['flags'] == []
    assert api.post('/api/cast-ai/turn', json={'cast': raw, 'a': 'a2', 'b': 'b1'}).json()['turn'] == 'Ida moves first.'
    found = api.post('/api/cast-ai/relationship', json={'cast': raw, 'from': ida, 'to': tom}).json()
    assert found['proposal'] == {'dynamic': 'Useful.', 'hidden_tension': '', 'trust': 6}
    broken = api.post('/api/cast-ai/check', json={'cast': {'outer': {'axis': {'kind': 'value'}, 'corners': []}}})
    assert broken.status_code == 422 and broken.json()['code'] == 'invalid_cast'
    assert api.get('/api/casts').json() == []
    nothing_written()


def test_without_a_model_the_routes_say_so(monkeypatch):
    monkeypatch.setattr(ai, 'api_key', lambda provider: '')
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    found = TestClient(create_app()).post('/api/cast-ai/suggest', json={'cast': blank(), 'target': 'outer'})
    assert found.status_code == 409 and 'No model is set up' in found.json()['error']


def test_the_one_looked_at_keeps_their_secret_from_the_one_looking(model):
    raw, ida, tom = linked_board()
    model.replies = [json.dumps({'dynamic': 'Thinks she is the only honest one.', 'hidden_tension': 'He needs her vote.',
                                 'trust': 7})]
    cast_ai.relationship(casts.checked(raw), tom, ida)
    system = model.asked[0][0]
    assert 'Lies when cornered' in system and 'She sold the harbour plans.' not in system

import json

from fastapi.testclient import TestClient

from dramatis import assistant
from dramatis.main import create_app

CHARACTER = {
    'name': 'Dana Okafor', 'apps': ['companion', 'adventure'], 'about': 'An ER nurse in Baltimore.',
    'personality': 'Steady at work, scattered at home.', 'voice': 'Short sentences, dry jokes.',
    'flaws': ['Cancels plans when tired'], 'arc': {'lie': '', 'truth': '', 'catalyst': ''},
    'secret': {'truth': 'She stole morphine once.', 'cover_story': '', 'known_by': ''}, 'psyche': None,
    'companion': {'routine': 'Nights, then sleep till two.', 'life_themes': [], 'schedule': []},
    'personality_sliders': {'social': {'level': 0, 'source': 'rolled'}},
}


def said(reply='Done.', edits=()) -> str:
    return json.dumps({'reply': reply, 'edits': list(edits)})


def ask(message='Make her flaws harsher.', character=CHARACTER, **body):
    return assistant.answer(assistant.AssistantBody(message=message, character=character, **body))


def test_it_sees_the_form_as_typed_and_its_edits_come_back_shaped(model):
    model.replies = [said('Two harsher flaws.', [{'field': 'flaws', 'value': ['Holds grudges for years', ' ']},
                                                 {'field': 'arc.lie', 'value': 'Needing help means failing.'}])]
    found = ask()
    assert found['reply'] == 'Two harsher flaws.'
    assert found['edits'] == [
        {'field': 'flaws', 'label': 'Flaws', 'path': ['flaws'], 'value': ['Holds grudges for years']},
        {'field': 'arc.lie', 'label': 'Lie they believe', 'path': ['arc', 'lie'], 'value': 'Needing help means failing.'}]
    system, prompt = model.asked[0]
    # The form as it stands, but not the sliders as numbers, and not the secret: the message is not about it.
    assert 'Steady at work' in system and 'morphine' not in system and '"level"' not in system
    assert '- secret.truth (' not in system
    assert prompt.startswith('Their new message:\nMake her flaws harsher.')


def test_it_is_told_what_the_user_changed_since_and_where_they_are(model):
    model.replies = [said()]
    seen = CHARACTER | {'voice': 'Long, careful sentences.'}
    ask('Shorter?', seen=seen, focus='personality')
    system = model.asked[0][0]
    assert 'How they talk ("voice"): was Long, careful sentences.; now Short sentences, dry jokes.' in system
    assert 'They are in the Personality field ("personality")' in system


def test_the_conversation_goes_with_the_message(model):
    model.replies = [said()]
    ask('And her sister?', history=[{'role': 'user', 'content': 'Give her a sister.'},
                                    {'role': 'assistant', 'content': 'Added one. (You changed Background.)'}])
    prompt = model.asked[0][1]
    assert 'Them: Give her a sister.\n\nYou: Added one.' in prompt and prompt.index('Them:') < prompt.index('And her')


def test_a_field_it_may_not_touch_is_sent_back_once_then_dropped(model):
    model.replies = [said(edits=[{'field': 'personality_sliders', 'value': {}}]),
                     said(edits=[{'field': 'companion.relationship', 'value': 'romance'},
                                 {'field': 'wants', 'value': 'Day shifts.'}])]
    found = ask()
    assert 'is not a field you may change' in model.asked[1][1]
    assert [edit['field'] for edit in found['edits']] == ['wants']


def test_companion_fields_only_for_a_companion_character(model):
    model.replies = [said(edits=[{'field': 'routine', 'value': 'Days now.'}]), said()]
    found = ask(character=CHARACTER | {'apps': ['dungeon']})
    assert found['edits'] == [] and '"routine" is not a field' in model.asked[1][1]
    model.replies = [said(edits=[{'field': 'routine', 'value': 'Days now.'}])]
    assert ask()['edits'][0]['path'] == ['companion', 'routine']
    model.replies = [said(edits=[{'field': 'routine', 'value': 'Days now.'}]), said()]
    persona = CHARACTER | {'companion': CHARACTER['companion'] | {'relationship': 'persona'}}
    assert ask(character=persona)['edits'] == []


def test_an_age_under_18_never_lands(model):
    model.replies = [said(edits=[{'field': 'age', 'value': 16}]), said(edits=[{'field': 'age', 'value': '15'}])]
    assert ask('Make her younger.')['edits'] == []
    model.replies = [said(edits=[{'field': 'age', 'value': 'about 41'}])]
    assert ask('Make her older.')['edits'][0]['value'] == 41


def test_the_slop_audit_sends_a_stock_name_back_once_and_reports_what_is_left(model):
    model.replies = [said(edits=[{'field': 'background', 'value': 'Raised by her aunt Elara.'}]),
                     said(edits=[{'field': 'background', 'value': 'Raised by her aunt Elara.'}])]
    found = ask('Write her background.')
    assert 'Elara' in model.asked[1][1]
    assert found['edits'][0]['value'] == 'Raised by her aunt Elara.'
    assert [hit['match'] for hit in found['audit'] if hit['severity'] == 'hard'] == ['Elara']


def test_a_name_the_user_typed_is_theirs(model):
    model.replies = [said(edits=[{'field': 'background', 'value': 'Raised by her aunt Elara.'}])]
    found = ask('Her aunt Elara raised her; write that in.')
    assert len(model.asked) == 1 and found['edits'][0]['value'] == 'Raised by her aunt Elara.'


def test_an_edit_that_changes_nothing_is_left_out(model):
    model.replies = [said('It already fits.', [{'field': 'voice', 'value': ' Short sentences, dry jokes. '}])]
    assert ask()['edits'] == []


def test_an_empty_value_clears_the_field(model):
    model.replies = [said(edits=[{'field': 'flaws', 'value': []}, {'field': 'secret.truth', 'value': ''}])]
    assert [(edit['field'], edit['value']) for edit in ask('Clear those.', focus='secret.truth')['edits']] == [('flaws', []), ('secret.truth', '')]


def test_the_route_answers_with_the_reply(model):
    model.replies = [said('Hello.')]
    found = TestClient(create_app()).post('/api/assistant', json={'message': 'Hi', 'character': CHARACTER})
    assert found.status_code == 200 and found.json() == {'reply': 'Hello.', 'edits': [], 'audit': []}


def test_braces_in_the_users_words_stay_as_typed(model):
    model.replies = [said()]
    ask(character=CHARACTER | {'about': 'Writes {{fields}} on every form.'})
    assert 'Writes {{fields}} on every form.' in model.asked[0][0]


def test_it_sees_the_secret_it_may_edit_and_never_gives_an_adult_a_child_s_look(model):
    model.replies = [said(edits=[{'field': 'appearance', 'value': 'Slight, with a childlike face.'}]),
                     said(edits=[{'field': 'appearance', 'value': 'Slight, with a childlike face.'}])]
    found = ask('Make her look younger.')
    assert found['edits'] == [] and 'younger than 18' in model.asked[1][1]
    model.replies = [said(edits=[{'field': 'secret.truth', 'value': 'She stole morphine twice.'}])]
    found = ask('Make it worse.', focus='secret.truth')
    assert 'She stole morphine once.' in model.asked[2][0]
    assert found['edits'][0]['value'] == 'She stole morphine twice.'


def test_it_may_edit_emotional_edges_shaped_like_companion_keeps_them(model):
    model.replies = [said('Jealous, gently.', [{'field': 'emotional_traits', 'value': [
        {'name': 'Jealousy', 'intensity': 'fierce', 'note': 'Goes quiet when you mention friends.'}, {'name': ''}]}])]
    found = ask('Give her a jealous streak.')
    assert found['edits'] == [{'field': 'emotional_traits', 'label': 'Emotional edges',
                               'path': ['companion', 'emotional_traits'],
                               'value': [{'name': 'Jealousy', 'intensity': 'mild',
                                          'note': 'Goes quiet when you mention friends.'}]}]


SECRET = CHARACTER | {'secret': {'truth': 'She froze on a 911 call at the county dispatch center and a man died.',
                                 'cover_story': 'She left the county job for nursing.', 'known_by': 'no one'}}


def test_the_secret_is_shown_only_when_the_message_is_about_it(model):
    model.replies = [said(), said()]
    ask('Tighten her background.', character=SECRET)
    assert 'froze' not in model.asked[0][0] and 'She left the county job for nursing.' in model.asked[0][0]
    ask('What is she hiding from her sister?', character=SECRET)
    assert 'froze' in model.asked[1][0] and '- secret.truth (' in model.asked[1][0]


def test_an_edit_anyone_reads_that_tells_the_secret_is_sent_back_once_then_dropped(model):
    leak = {'field': 'background', 'value': 'She froze on a call once, and a man died on the line.'}
    model.replies = [said(edits=[leak]), said(edits=[leak, {'field': 'wants', 'value': 'Day shifts.'}])]
    found = ask('How does her secret shape her? Fix her background to fit.', character=SECRET)
    assert 'other characters read' in model.asked[1][1]
    assert [edit['field'] for edit in found['edits']] == ['wants']


def test_the_secret_goes_where_the_user_asks_for_it(model):
    model.replies = [said(edits=[{'field': 'background', 'value': 'She froze on a call once, and a man died.'}])]
    found = ask('Put her secret in the background, everyone knows now.', character=SECRET)
    assert len(model.asked) == 1 and found['edits'][0]['field'] == 'background'


def test_a_text_edit_or_reply_that_makes_them_a_minor_never_lands(model):
    model.replies = [said(edits=[{'field': 'background', 'value': 'Going to the local high school.'}]),
                     said(edits=[{'field': 'setting', 'value': 'Baltimore, still in high school'}])]
    found = ask('Make her younger in spirit.')
    assert found['edits'] == [] and 'younger than 18' in model.asked[1][1]
    model.replies = [said("Here's Dana: she is 16 now."), said("Here's Dana: she is 16 now.")]
    found = ask('Make her younger.')
    assert found == {'reply': assistant.adults.ADULTS_ONLY, 'edits': [], 'audit': []}

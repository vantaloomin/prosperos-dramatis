"""A stand-in model for walking the screen without one: `python -m dramatis --stub`.

Every model call (dramatis/ai.py `complete`) gets a fixed answer in the shape its prompt asks for, after a short pause
so Stop and the progress line show. The library is a throwaway folder unless DRAMATIS_HOME says otherwise, and the
model profile lives only in memory, so nothing here touches the real library or the keyring. CI's screen walk
(`tests/walk/walk.mjs`) runs against this; tests/test_stub.py keeps each answer in step with its prompt.
"""
import json
import os
import tempfile
import time

from dramatis import ai, profiles
from dramatis.formats.companion.providers.config import ProfileCreate
from dramatis.formats.companion.providers.vault import MemoryVault

DELAY = float(os.environ.get('DRAMATIS_STUB_DELAY', '0.3'))

CHARACTER = {
    'name': 'Dana Okafor', 'gender': 'woman', 'age': 38, 'kind': '',
    'about': 'Dana is 38 and works night shifts as an ER nurse in Baltimore. She lives with her brother.',
    'personality': 'Steady at work, scattered at home. Holds grudges over small things.',
    'voice': 'Short sentences, dry jokes, rarely uses capital letters.',
    'sound': 'A low, slightly hoarse alto, unhurried.',
    'appearance': 'Tall and broad-shouldered, cropped grey-streaked hair, scrubs under a parka.',
    'seen_as': 'Comes across as curt; always early; sets off when people waste her time.',
    'sees_self': 'I am the only one who keeps things moving.\nI am not unkind, just tired.',
    'background': 'Grew up in Dundalk. Trained late, after years waiting tables.',
    'wants': 'To get onto day shifts before her knees give out.', 'fears': 'Making a mistake that kills someone.',
    'skills': ['Starts an IV in the dark', 'Backs a van into anything', 'Middling at Spanish'],
    'flaws': ['Cancels plans when tired', 'Talks over people when excited'],
    'interests': ['true crime podcasts', 'duckpin bowling'],
    'routine': 'Weekdays I sleep till two. Saturdays are for the bowling league.',
    'life_themes': ['hospital', 'bowling league', 'her brother'],
    'schedule': [{'label': 'Sleep', 'kind': 'sleep', 'days': [0, 1, 2, 3, 4, 5, 6], 'start': '23:30', 'end': '07:00'},
                 {'label': 'Ward shifts', 'kind': 'work', 'days': [2, 4, 6], 'start': '07:00', 'end': '19:30',
                  'themes': ['patients']}],
    'emotional_traits': [{'name': 'Jealousy', 'intensity': 'moderate',
                          'note': 'Goes quiet when you mention other friends.'}],
    'absence_reaction': 'Sulks a little, then texts as if nothing happened.',
    'arc': {'lie': 'That asking for help gets you left.', 'truth': 'People stay when they are let in.',
            'catalyst': 'A colleague who covers for her without being asked.'},
    'psyche': {'was': 'The kid who held the family together.', 'expected': 'The one who never needs anything.',
               'wants_to_be': 'Someone who gets to rest.', 'fears_becoming': 'Her mother, bitter and alone.'},
    'secret': {'truth': 'She failed her licensing exam twice.', 'cover_story': 'She passed first time.',
               'known_by': 'Her brother.'},
}

# What each prompt asks for, by a mark only it carries (dramatis/prompts/), checked in order: the first that matches
# answers. A whole character answers everything else (the quick start and the split).
ANSWERS = [
    ('Sidebar Assistant', {'reply': 'I gave her a sister and made her wants plainer.', 'edits': [
        {'field': 'background', 'value': 'Grew up in Dundalk with a sister, Ruth, she no longer talks to.'},
        {'field': 'wants', 'value': 'To get onto day shifts.'}]}),
    ('{"spans"', {'spans': {str(number): 'plain words' for number in range(1, 40)}}),
    ('{"interview"', {'interview': '**What do you do?**\n\nShe shrugs. "Nights, mostly. Somebody has to."\n\n'
                                   '**What do you love?**\n\n"Bowling. Don\'t laugh."',
                      'sample': 'Nights, mostly. Somebody has to.'}),
    ('{"flags"', {'flags': [], 'judgements': []}),
    ('{"corner_id"', {'proposals': [
        {'corner_id': None, 'label': 'The Order', 'stance': 'Peace is worth what it costs.', 'tags': ['law'],
         'role': '', 'fields': {}},
        {'corner_id': None, 'label': 'The Free', 'stance': 'No one should be ruled.', 'tags': ['sabotage'],
         'role': '', 'fields': {}}]}),
    ('{"proposals"', {'proposals': [{'field': 'voice', 'value': 'Clipped and dry; deflects with jokes.',
                                     'reason': 'She deflects twice in the interview.'}]}),
    ('{"turn"', {'turn': 'At the inquest she sides with the other nurse, and it costs her the promotion.'}),
    ('{"dynamic"', {'dynamic': 'Thinks he is soft, and relies on him anyway.',
                    'hidden_tension': 'He covered for her once.', 'trust': 6}),
    ('{"prompt"', {'prompt': 'A tall woman in her late thirties in scrubs under a parka, waist up, plain light.'}),
    ('{"value"', {'value': 'Short sentences, dry jokes, and a long pause before she says anything kind.'}),
]


def answer(system: str, prompt: str) -> str:
    time.sleep(DELAY)
    found = next((reply for mark, reply in ANSWERS if mark in system), CHARACTER)
    return json.dumps(found, ensure_ascii=False)


def install() -> str:
    """Answers every model call with `answer`, from a profile kept in memory, in a throwaway library unless
    DRAMATIS_HOME is set. Returns the library folder."""
    home = os.environ.setdefault('DRAMATIS_HOME', tempfile.mkdtemp(prefix='dramatis-stub-'))
    profiles.VAULT = MemoryVault()
    if not profiles.overview()['profiles']:
        profiles.create(ProfileCreate.model_validate({'name': 'Stand-in model', 'config': {
            'provider': 'local', 'model': 'stub', 'base_url': 'http://127.0.0.1:1/v1', **profiles.DRAFTING}}))
    ai.complete = answer
    return home

import json

SLEEP = {'label': 'Sleep', 'kind': 'sleep', 'days': [0, 1, 2, 3, 4, 5, 6], 'start': '23:30', 'end': '07:00'}
WORK = {'label': 'Ward shifts', 'kind': 'work', 'days': [2, 4, 6], 'start': '07:00', 'end': '19:30',
        'themes': ['patients']}


def reply(**changes) -> str:
    """A model's whole-character reply, as JSON text: every field a draft asks for, filled."""
    found = {
        'under_18': False, 'name': 'Dana Okafor', 'gender': 'woman', 'age': 38, 'kind': '',
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
        'schedule': [SLEEP, WORK], 'emotional_traits': [{'name': 'Jealousy', 'intensity': 'strong'}],
        'absence_reaction': 'Sulks a little.',
        'arc': {'lie': 'That asking for help gets you left.', 'truth': 'People stay when they are let in.',
                'catalyst': 'A colleague who covers for her without being asked.'},
        'psyche': {'was': 'The kid who held the family together.', 'expected': 'The one who never needs anything.',
                   'wants_to_be': 'Someone who gets to rest.', 'fears_becoming': 'Her mother, bitter and alone.'},
        'secret': {'truth': 'She failed her licensing exam twice.', 'cover_story': 'She passed first time.',
                   'known_by': 'Her brother.'},
    }
    return json.dumps(found | changes)

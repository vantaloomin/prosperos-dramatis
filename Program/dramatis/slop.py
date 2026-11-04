"""The AI-slop audit: names, words, phrases and patterns that mark text as model-written, checked on what the model
drafts before the form shows it.

The list is Wren Halloway's (data/ai-slop.json, 2026-11-03, with its own notes in ai-slop.md beside the original
slop_check.py); `scan` is that checker's matching, kept as it works there. Beside it, data/ai-slop-wikipedia.json adds
the signs from Wikipedia's "Signs of AI writing" that can turn up in a character (puffed-up significance, its AI
vocabulary, the chatbot talking to its user, unfilled placeholders, "-ing" analyses, "not just X but Y", "rather
than", "no X, no Y, just Z", emoji), read the same way:

- **hard** entries are defects: stock names (Elara, Kael, Voss), em dashes, the assistant's voice. A draft with a
  hard hit the user didn't write themselves is sent back once, naming the hits (dramatis/drafting.py), and any still
  there after that are shown on the form.
- **flag** entries are for review: one hit means nothing, so the form lists them under "Worth a look" and never
  refuses a draft for them.

It runs as an audit pass, never in the drafting prompts: putting the list in front of the model can make those words
more likely. The scene-level density rules (a word echoed three times in 200 words, 500 words without a question) are
for prose chapters, not a character's fields, so they are left out here.
"""
import json
import re
from functools import cache
from pathlib import Path

DATA = Path(__file__).parent / 'data'
LISTS = (DATA / 'ai-slop.json', DATA / 'ai-slop-wikipedia.json')
# The character's fields the audit reads, with the names the form shows them by.
FIELDS = {'name': 'Name', 'about': 'About them', 'personality': 'Personality', 'voice': 'How they talk',
          'sound': 'How they sound', 'appearance': 'Appearance', 'seen_as': 'Outward appearance',
          'sees_self': 'How they see themselves', 'background': 'Background', 'wants': 'What they want',
          'fears': 'What they fear', 'skills': 'Skills', 'flaws': 'Flaws', 'interests': 'Interests',
          'interview': 'Interview'}
LIFE_FIELDS = {'routine': 'Their routine', 'life_themes': 'Life themes', 'history_together': 'How you know each other',
               'absence_reaction': 'When you are away'}
# Their depth, inside the character: the key the form and Help me write use, its label, and where it sits.
DEPTH = {'arc.lie': ('Lie they believe', ('arc', 'lie')), 'arc.truth': ('Truth they need', ('arc', 'truth')),
         'arc.catalyst': ('What could force it', ('arc', 'catalyst')),
         'secret.truth': ("What's really true", ('secret', 'truth')),
         'secret.cover_story': ('What people believe instead', ('secret', 'cover_story')),
         'secret.known_by': ('Who knows', ('secret', 'known_by')),
         'psyche.was': ('Who they were', ('psyche', 'was', 'text')),
         'psyche.expected': ("Who they're expected to be", ('psyche', 'expected', 'text')),
         'psyche.wants_to_be': ('Who they want to be', ('psyche', 'wants_to_be', 'text')),
         'psyche.fears_becoming': ('Who they fear becoming', ('psyche', 'fears_becoming', 'text'))}
# Real words that only count as names mid-sentence, and that never match a longer word.
NO_DERIVATIVES = ('names_word', 'surnames_overdrawn', 'places_overdrawn')
PAD = 30


@cache
def data() -> dict:
    """Every list's categories and patterns together."""
    lists = [json.loads(path.read_text(encoding='utf-8')) for path in LISTS]
    return {key: [entry for found in lists for entry in found.get(key, [])] for key in ('categories', 'patterns')}


def compiled(item: str, kind: str) -> re.Pattern:
    escaped = re.escape(item)
    if kind == 'name':
        # Whole word, case-sensitive, plus derivatives (Kael catches Kaelen and Kaelith).
        return re.compile(r'(?<![A-Za-z])' + escaped + r'[a-z]{0,4}(?![A-Za-z])')
    lead = r'(?<![A-Za-z])' if item[:1].isalnum() else ''
    tail = r'(?![A-Za-z])' if item[-1:].isalnum() else ''
    return re.compile(lead + escaped + tail, re.IGNORECASE)


@cache
def rules() -> tuple[tuple[dict, list[tuple[str, re.Pattern]]], ...]:
    """Each category with its items' expressions, then each pattern with its own."""
    found = [(category, [(item, compiled(item, category['match'])) for item in category['items']])
             for category in data()['categories']]
    found += [(pattern, [('', re.compile(pattern['regex']))]) for pattern in data()['patterns']]
    return tuple(found)


def sentence_start(text: str, position: int) -> bool:
    before = text[:position].rstrip(' \t"\'“‘*_(')
    return not before or before[-1] in '.!?\n:'


def scan(text: str) -> list[dict]:
    """Every hit in one text: its severity, the rule's title and what matched, in order."""
    hits = []
    for rule, expressions in rules():
        for item, expression in expressions:
            for match in expression.finditer(text):
                if rule.get('id') == 'names_word' and sentence_start(text, match.start()):
                    continue
                if rule.get('id') in NO_DERIVATIVES and len(match[0]) > len(item):
                    continue
                hits.append({'severity': rule['severity'], 'rule': rule['title'], 'match': match[0],
                             'context': text[max(0, match.start() - PAD):match.end() + PAD].replace('\n', ' ').strip(),
                             'at': match.start()})
    hits.sort(key=lambda hit: (hit['severity'] != 'hard', hit['at']))
    return [{key: value for key, value in hit.items() if key != 'at'} for hit in hits]


def at(source, path: tuple[str, ...]):
    for key in path:
        source = source.get(key) if isinstance(source, dict) else None
    return source


def texts(character: dict) -> list[tuple[str, str, str]]:
    """(key, label, text) for each field the audit reads; a list is read one item at a time."""
    life = character.get('companion') or {}
    found = []
    for source, labels in ((character, FIELDS), (life, LIFE_FIELDS)):
        for key, label in labels.items():
            value = source.get(key)
            items = value if isinstance(value, list) else [value]
            found += [(key, label, item) for item in items if isinstance(item, str) and item.strip()]
    for key, (label, path) in DEPTH.items():
        value = at(character, path)
        if isinstance(value, str) and value.strip():
            found.append((key, label, value))
    return found


def audit(character: dict, allowed: str = '') -> list[dict]:
    """Every hit in the character's fields, by field. A hit whose text is in `allowed` (what the user typed or pasted)
    is theirs, not the model's, and is left out: a user may want an Elara."""
    return audit_texts(texts(character), allowed)


def audit_texts(found: list[tuple[str, str, str]], allowed: str = '') -> list[dict]:
    """Every hit in (key, label, text) triples that are not a character's fields, such as a cast's suggestions, with
    the same rule for what the user wrote themselves."""
    mine = allowed.casefold()
    return [{'field': key, 'label': label, **hit} for key, label, text in found for hit in scan(text)
            if not (mine and hit['match'].strip().casefold() in mine)]


def hard(hits: list[dict]) -> list[dict]:
    return [hit for hit in hits if hit['severity'] == 'hard']


def problem(hits: list[dict]) -> str:
    """The hard hits, for the one retry: what to change and where, without the rest of the list."""
    named = list(dict.fromkeys(f"{hit['match'].strip() or 'a dash'} ({hit['label']})" for hit in hits))
    dashes = any(hit['rule'].startswith('Em dash') for hit in hits)
    return ('it used names, words or punctuation that read as model-written: ' + ', '.join(named[:12]) + '. Use '
            'ordinary names real people are given and plain words' + (', and commas, colons or full stops instead of '
                                                                      'dashes' if dashes else '') + '.')

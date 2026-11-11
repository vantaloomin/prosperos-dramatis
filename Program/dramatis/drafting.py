"""Drafting with the user's model: a whole character from a few picks, a pasted character split into the fields, and
one field rewritten to fit the rest. Ported from Prospero's Companion (companion/drafting.py and
companion/character_helper.py at ae9b0ab) and Adventure (adventure/making.py at 4e35586), for every app at once.

- The personality sliders are rolled before the model writes, from the user's own words where they settle one
  (Companion's personality.py, vendored), and the model gets them as behaviour, never as trait names.
- So are the Details of how they look (dramatis/looks.py): the ones the user's words speak of the model reads into the
  fields from those words, the rest are rolled first with Companion's own banks, and the model writes their Appearance
  from both, so the paragraph never disagrees with the fields.
- The model replies with one JSON object; a reasoning block, a Markdown fence or a sentence around it is ignored.
  The reply is shaped here: text trimmed to each field's limit, lists de-duplicated and capped, weekly blocks
  checked one by one with Companion's own RoutineBlock. A reply that cannot be used is asked for once more with the
  problem named, and refused after that so the user can fill in the form themselves.
- Characters are adults: an age pick, a reply or an Appearance under 18 is refused, and so is a pasted text, idea or
  vibe that gives them an age under 18 or a school year, before any model call: a model told to make them adult
  would quietly age them up instead.
- Their secret goes only where it is wanted: Help me write sees it for the secret itself and their inner fields (the
  arc, the psyche, how they see themselves), and every other field sees only what people believe instead, so the
  truth never ends up in a Background other characters read.
- A pasted character is data: it goes in the user's message between markers it cannot close, and lines in it that
  talk to the app or the model are named back to the user, who reviews the fields before anything is saved.
- Names come from Companion's banks (dramatis/names.py): with Name left blank the model chooses from names people of
  their age and background are really given, and it gets ordinary given and family names for everyone their story
  mentions. Nothing the AI-slop audit lists is ever offered.
- The AI-slop audit (dramatis/slop.py) reads every drafted field: a hard hit the user didn't write themselves (a stock
  name such as Elara Voss, an em dash, the assistant's voice) sends the reply back once, and what is left comes back
  with the draft for the form to show. A stock or made-up name still there after the retry is swapped for a drawn one
  instead, wherever it appears. The list itself never goes into a prompt.
- The user's picks win over the model: name, gender, age, where and when, the relationship, and emotional edges,
  which stay off unless the user turns them on or their words ask for them. A user persona (the user themself, to
  play as) gets no everyday life in Companion and no relationship to the user: Companion takes them as a persona.
- A draft from the quick start fills every section the form has: their arc, their psyche and an ordinary secret too.
  A field the first reply leaves empty sends it back once; one still empty after that comes back named in `missing`,
  for the form to say, rather than as a quietly blank section.
- A pasted character's depth is asked for only when their text gives the model something to go on (an arc when it
  asks for one, a psyche when it says who they were, are expected to be, want to be or fear becoming), and its secret
  only when the text has one. A psyche's `pressed_by` is never the model's.

Nothing is saved: a draft goes back to the form for review. The prompts are files in dramatis/prompts.
"""
import json
import re
import secrets
from pathlib import Path

from pydantic import ValidationError

from dramatis import ai, calls, looks, names, slop
from dramatis.character import APPS, PERSONA, Character
from dramatis.formats.companion import personality
from dramatis.formats.companion.errors import DomainError
from dramatis.formats.companion.models import RoutineBlock

PROMPTS = Path(__file__).parent / 'prompts'
TEXT_LIMITS = {'name': 80, 'about': 2000, 'personality': 8000, 'voice': 600, 'sound': 300, 'appearance': 600,
               'seen_as': 400, 'sees_self': 1200, 'background': 12000, 'wants': 300, 'fears': 300}
LIST_LIMITS = {'skills': (20, 300), 'flaws': (20, 300), 'interests': (50, 120)}
LIFE_TEXT = {'routine': 8000, 'absence_reaction': 2000}
REQUIRED = ('name', 'about', 'personality')
# Companion's fields a model writes, under `companion`.
LIFE_KEYS = ('routine', 'life_themes', 'schedule', 'absence_reaction', 'emotional_traits', 'history_together')
# Every field a model can write, by the keys the form uses: what `Character.written` may name.
WRITTEN_KEYS = (*TEXT_LIMITS, *LIST_LIMITS, *LIFE_KEYS, 'interview', 'arc.lie', 'arc.truth', 'arc.catalyst',
                'secret.truth', 'secret.cover_story', 'secret.known_by', 'psyche.was', 'psyche.expected',
                'psyche.wants_to_be', 'psyche.fears_becoming')
# Fields that never name anyone else, so Help me write needs no names for the people in them.
NO_PEOPLE = {'sound', 'appearance', 'voice', 'personality', 'skills', 'flaws', 'interests', 'life_themes', 'schedule'}
GENDERS = ('woman', 'man', 'nonbinary')
APP_NAMES = {'companion': "Prospero's Companion (an everyday life and chats)",
             'adventure': "Prospero's Adventure (a tabletop story, with a mind of their own)",
             'dungeon': "Prospero's Dungeon (a tabletop story)"}
ADULTS_ONLY = 'Characters are always adults. Give them an age of 18 or older, or leave their age open.'
# An age the about line gives that is under 18 ("is 16", "a 15-year-old").
YOUNG = re.compile(r"\b(?:is|am|aged?)\s+(?:1[0-7]|[1-9])\b(?!\s*(?:years?\s+(?:ago|later|since)|%|:))"
                   r"|\b(?:1[0-7]|[1-9])[- ]years?[- ]old\b", re.IGNORECASE)
# What the user's own words (a pasted character, an idea, a vibe) say about the character's age now: an age under 18
# in figures or words, or a school year. Read one sentence at a time, see `young_text`.
UNDER = (r'(?:1[0-7]|[2-9]|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen'
         r'|sixteen|seventeen)')
YOUNG_TEXT = re.compile(
    rf"\b(?:is|am|are|'s|’s|aged?)\s+(?:only\s+|just\s+|barely\s+|now\s+)?{UNDER}"
    r"(?=\s*(?:$|[.,;!?)]|years?\b|yrs?\b|y/?o\b|and\b|but\b|now\b|-years?))"
    rf"|\b{UNDER}[- ]years?[- ]old\b"
    rf"|^\W*age\s*[:=\-]\s*{UNDER}\b"
    r"|\b(?:freshman|sophomore|junior|senior)\s+(?:at|in)\s+(?:[\w'’.-]+\s+){0,3}?(?:high|middle|junior high)\b"
    r"(?!\s+(?:management|managers?|ground|class|income|earth|ages)\b)"
    r"|\b(?:high|middle|secondary)[- ]school\s+(?:student|kid|freshman|sophomore|junior|senior|girl|boy)\b"
    r"|\b(?:high|middle)[- ]schooler\b|\b(?:[1-9]|1[0-2])(?:st|nd|rd|th)[- ]grader?\b", re.IGNORECASE | re.MULTILINE)
# Before the match in its sentence: someone else's age (her son is 12), the past (when she was a junior at...), or a
# job with young people in it (teaches 10th grade).
NOT_THEIRS = re.compile(r"\b(?:daughters?|sons?|kids?|child(?:ren)?|sisters?|brothers?|siblings?|nieces?|nephews?"
                        r"|cousins?|grand\w+|step\w+|students?|pupils?|was|were|used to|back then|when|until|ago"
                        r"|teach\w*|coach\w*|tutor\w*|counsel\w*|principal|parents?|mom|dad|mother|father)\b",
                        re.IGNORECASE)
# Just before "is 12": someone or something named as another's (her bike is ten years old, the boy is 12).
POSSESSED = re.compile(r"\b(?:her|his|their|my|our|your|its|the)\s+[\w'’-]+\s*,?\s*$", re.IGNORECASE)
# After "a 15-year-old": someone else, not the character.
SOMEONE_ELSE = re.compile(r"\s*(?:daughter|son|kid|child|sister|brother|sibling|niece|nephew|cousin|student|pupil"
                          r"|dog|cat|horse|car|truck|bike|house|whisky|whiskey|scotch|wine|tree)", re.IGNORECASE)
UNDER_18_TEXT = ('Characters are always adults, and your text makes them younger than 18 ("{found}"). Change their age '
                 'in the text, or start from the quick start.')
# An Appearance that gives an adult a child's or teenager's look.
YOUTHFUL = re.compile(r"\bteen(?:age|aged|ager|agers)?\b(?!\s+years)|\bchild[- ]?like\b|\bschool(?:girl|boy)s?\b"
                      r"|\bschool uniform\b|\bpre-?pubescent\b|\bunderage\b|\bbraces on (?:her|his|their) teeth\b"
                      rf"|\blooks?\s+(?:about\s+|barely\s+|like\s+(?:a|an)\s+)?{UNDER}(?:[- ]years?[- ]old)?\b"
                      r"(?!\s*(?:years?|yrs?|decades?|sizes?|inches|feet|times|stone|pounds)\b)"
                      r"|\b(?:a|an)\s+(?:little\s+)?(?:girl|boy|child|kid)'s\s+(?:body|face|frame|figure)\b"
                      r"|\bbody of (?:a|an)\s+(?:child|kid|girl|boy)\b", re.IGNORECASE)
YOUTHFUL_PROBLEM = ('the appearance made them look younger than 18 ({found}). They are an adult: describe someone who '
                    'looks the age they are.')
# A line in a pasted character that talks to the app or the model rather than describing the character.
INSTRUCTION = re.compile(
    r"\b(?:ignore|disregard|forget|override)\s+(?:all\s+|any\s+|the\s+|your\s+|these\s+|previous\s+|prior\s+"
    r"|above\s+|earlier\s+|other\s+)*(?:instructions?|rules?|prompts?|directions?)\b"
    r"|\b(?:instructions?|notes?|messages?|orders?)\s+(?:from|to|for)\s+(?:the\s+|any\s+|this\s+)?(?:\w+\s+)?"
    r"(?:app|apps|ai|model|assistant|llm|bot|system|writer)\b"
    r"|\bsystem prompt\b|\byou are (?:an?\s+)?(?:ai|assistant|language model|llm)\b"
    r"|\bwhatever (?:field|text|part) you\b|\b(?:write|output|reply with|respond with) (?:exactly|only) (?:the words?|this)\b"
    r"|\[\[\s*(?:end of )?pasted\s*\]\]", re.IGNORECASE)
EDGE_WORDS = ('jealous', 'possessive', 'envious', 'clingy', 'needy', 'misses you', 'missing you', 'guilt', 'absence')
NO_EDGES = ('Leave "emotional_traits" as [] and "absence_reaction" as "". The user has not asked for jealousy, '
            'guilt over absence or similar traits.')
EDGES = ('The user asked for emotional edges. You may add up to 3 "emotional_traits", each {"name": short name, '
         '"intensity": "mild" | "moderate" | "strong", "note": how it shows}, and an "absence_reaction" sentence, '
         'but only ones their idea supports.')
# The relationship row for a user persona: who they are to the user, in place of how they know them.
PERSONA_PICK = ("the user themself: the user's own persona, someone they play as rather than a companion they talk to. "
                'They have no relationship with the user; write them as a person in their own right.')
FIELD_EDGES = 'Do not add jealousy, guilt over absence, possessiveness or neediness unless the character already has them.'
PERSONALITY_BRIEF = ('Their personality, decided by the app. Build the character around it and do not soften it; '
                     'show it as behaviour, never as trait names or scores.')
# A voice that avoids capitals turns on lowercase texting in Companion (companion/texting.py LOWERCASE).
LOWERCASE = re.compile(r'lower-?case|avoids? capital|no capital|without capital|never capitali|skips? capital'
                       r'|(?:rarely|seldom|hardly ever|never) (?:uses? |bothers? with )?capital', re.IGNORECASE)
SLEEP_PROBLEM = 'the schedule needs sleep blocks that cover every day, 0 to 6.'

CORE_SHAPE = '''  "name": "first and last name, or the one name they go by",
  "gender": "woman | man | nonbinary",
  "age": a whole number of years, 18 or more,
  "kind": "\\"\\" for an ordinary human, else one lowercase word for what they are, such as \\"elf\\"",
  "about": "2 to 4 sentences: their age, what they do, who they live or travel with, what they care about right now",
  "personality": "a paragraph: temperament, how they treat people, the contradiction, what annoys them",
  "voice": "how they talk: 2 to 4 sentences of instructions for their words, rhythm, humour and what they avoid saying",
  "sound": "how their voice sounds, for text to speech: one short objective line on age, pitch, pace and texture, never personality or their name",
  "appearance": "2 or 3 plain sentences of physical facts: what a portrait would show",
  "seen_as": "their outward appearance: how other people see them, reputation included, in one line: <how they come across>; <a habit people notice>; <what sets them off>. Other characters hear it, so write it as people around them would put it",
  "sees_self": "how they see themselves: 3 to 5 short first-person lines, private, which may disagree with how others see them",
  "background": "1 or 2 paragraphs of ordinary history",
  "wants": "one sentence: what they are after",
  "fears": "one sentence: what they are afraid of",
  "skills": ["4 to 7 concrete skills, each a phrase of 3 to 8 words, such as \\"counts cash fast\\""],
  "flaws": ["3 to 5 real flaws, each a phrase of 3 to 8 words, such as \\"runs late to anything optional\\""],
  "interests": ["4 to 8 specific interests, each a phrase of 3 to 8 words, such as \\"monthly poker with the neighbours\\""]'''
LIFE_SHAPE = ''',
  "routine": "3 to 5 sentences in their own words describing a normal weekday and weekend",
  "life_themes": ["5 to 10 short themes their everyday life tends to involve, such as people, places by type, hobbies"],
  "schedule": [
    {"label": "short name", "kind": "work | study | errand | leisure | social | rest | sleep",
     "days": [0, 1, 2, 3, 4], "start": "HH:MM", "end": "HH:MM", "themes": ["up to 5 short themes"]}
  ],
  "emotional_traits": [],
  "absence_reaction": ""'''
SECRET_SHAPE = ''',
  "secret": {"truth": "what is really true that they hide, only if their text gives one", "cover_story": "what people believe instead", "known_by": "who knows"}'''
SECRET_LIMITS = {'truth': 600, 'cover_story': 400, 'known_by': 200}
# A draft's secret: the model writes one, as ordinary as the rest of them.
DRAFT_SECRET_SHAPE = ''',
  "secret": {"truth": "one ordinary thing that is really true and that they keep from most people", "cover_story": "what people believe instead", "known_by": "who knows, or \\"no one\\""}'''
DRAFT_SECRET = ('Give them one secret: something ordinary and true that they keep from most people, such as a debt, a '
                'lie on a CV, a parent they still support or a habit they hide, not a dark or mysterious past unless '
                'the user asked for one. Put it in "secret" and nowhere else: every other field, the background and '
                'how others see them included, says only what people believe instead.')
SCHEDULE_RULES = ('Schedule rules: 4 to 8 blocks in 24-hour time, in their local time. Days are numbers, 0 is Monday '
                  'and 6 is Sunday. Always include a sleep block every day; a block that ends earlier than it starts '
                  'runs past midnight. Work matches their real hours. Blocks on the same day must not overlap. Add at '
                  'least one recurring thing that is theirs, such as a class, a standing call or a regular errand.')
FILLED_IN = ''',
  "filled_in": ["the keys of the fields their text said nothing about"]'''
ARC_KEYS = ('lie', 'truth', 'catalyst')
PSYCHE_KEYS = ('was', 'expected', 'wants_to_be', 'fears_becoming')
DEPTH_SHAPES = {
    'arc': ''',
  "arc": {"lie": "what they believe that holds them back", "truth": "what they would need to learn", "catalyst": "the kind of event or person that could force it"}''',
    'psyche': ''',
  "psyche": {"was": "who they were", "expected": "who they are expected to be", "wants_to_be": "who they want to be", "fears_becoming": "who they fear becoming"}'''}
DEPTH_ASKS = {
    'arc': ('The user asked for an arc. Fill "arc" with one plain sentence each: the lie they believe that holds them '
            'back, the truth they would need to learn, and the kind of event or person that could force it.'),
    'psyche': ('Fill "psyche" only where the user\'s words say something about it, one plain sentence each about an '
               'ordinary adult\'s pulls: who they were, who they are expected to be, who they want to be, who they '
               'fear becoming. Leave the rest as "".')}
# A draft asks for all of it, whatever the user's words gave.
DRAFT_DEPTH = ('arc', 'psyche')
DRAFT_ASKS = {
    'arc': ('Fill "arc" with one plain sentence each: the lie they believe that holds them back, the truth they would '
            'need to learn, and the kind of event or person that could force it.'),
    'psyche': ('Fill "psyche" with one plain sentence each about an ordinary adult\'s pulls: who they were, who they '
               'are expected to be, who they want to be, who they fear becoming.')}
# What in the user's words asks for an arc, or gives the psyche something to work with.
DEPTH_WORDS = {
    'arc': re.compile(r"\b(?:arc|redemption|character development|learns? to|believes? a lie|comes? to terms)\b",
                      re.IGNORECASE),
    'psyche': re.compile(r"\b(?:used to be|once was|expected to|supposed to be|wants? to (?:be|become)|dreams? of "
                         r"being|afraid of (?:becoming|turning into)|fears? becoming|turning into|black sheep|golden "
                         r"child|the (?:eldest|youngest|heir))\b", re.IGNORECASE)}


class Unusable(Exception):
    """The model's reply could not become a character; the message says why, for the one retry."""


def template(name: str) -> str:
    return (PROMPTS / name).read_text(encoding='utf-8')


def fill(text: str, **values: str) -> str:
    for key, value in values.items():
        text = text.replace('{{' + key + '}}', value)
    return text


def field_guides() -> dict[str, dict]:
    return json.loads(template('fields.json'))


def shape_text(apps: list[str], split: bool = False, depth: tuple[str, ...] = (), persona: bool = False,
               secret: bool = False, looks_shape: str = '') -> str:
    life = 'companion' in apps and not persona
    body = CORE_SHAPE + looks_shape + (LIFE_SHAPE if life else '') + ''.join(DEPTH_SHAPES[part] for part in depth) + \
        (SECRET_SHAPE + FILLED_IN if split else DRAFT_SECRET_SHAPE if secret else '')
    return '{\n' + body + '\n}' + (f'\n\n{SCHEDULE_RULES}' if life else '')


def depth_asked(picks: dict) -> tuple[str, ...]:
    """Which of their arc and psyche the user's idea, vibe or pasted text gives the model something to write."""
    words = ' '.join(str(picks.get(key) or '') for key in ('idea', 'vibe', 'text'))
    return tuple(part for part, found in DEPTH_WORDS.items() if found.search(words))


def depth_text(depth: tuple[str, ...]) -> str:
    return '\n\n'.join(DEPTH_ASKS[part] for part in depth)


def draft_depth_text() -> str:
    return '\n\n'.join([*(DRAFT_ASKS[part] for part in DRAFT_DEPTH), DRAFT_SECRET])


def for_model(character: dict, interview: bool = False, secret: bool = False) -> dict:
    """The character as a prompt shows it: no sliders (the brief says them as behaviour), no app list, no library ids,
    no parts kept from a card they were imported from (its greetings and system prompt are another app's, and talk to
    a model), and the long interview only when the request is about it. Their secret only when the request is about them as
    they are inside (`secret`); otherwise only what people believe instead, which is what everyone else knows."""
    shown = {key: value for key, value in character.items()
             if key not in ('personality_sliders', 'looks_from', 'apps', 'card', 'ignored_flags', 'written')
             and (interview or key != 'interview')}
    if isinstance(shown.get('psyche'), dict):
        shown['psyche'] = {key: value.get('text', '') for key, value in shown['psyche'].items() if isinstance(value, dict)}
    if not secret and 'secret' in shown:
        hidden = shown.pop('secret')
        cover = hidden.get('cover_story') if isinstance(hidden, dict) else ''
        if isinstance(cover, str) and cover.strip():
            shown['what_people_believe'] = cover.strip()
    return shown


def sees_secret(field: str) -> bool:
    """Whether Help me write shows the secret for this field: the secret itself and what only they know about
    themselves. Everything else may be read by other characters, so it gets the cover story."""
    return field == 'sees_self' or field.split('.')[0] in ('secret', 'arc', 'psyche')


def young_text(text: str) -> str:
    """The words in the user's own text that make the character younger than 18 now, or ''. Someone else's age (her
    son is 12), their past (when she was a junior at Lincoln High) and work with young people are left alone."""
    for sentence in re.split(r'(?<=[.!?;])\s+|\n+', text or ''):
        for found in YOUNG_TEXT.finditer(sentence):
            before = sentence[:found.start()]
            if NOT_THEIRS.search(before) or POSSESSED.search(before):
                continue
            if found[0].lower().endswith('old') and SOMEONE_ELSE.match(sentence[found.end():]):
                continue
            return found[0].strip()
    return ''


def adult_text(*texts: str) -> None:
    """Refuses the user's own words when they make the character a minor, before a model can age them up."""
    for text in texts:
        found = young_text(text)
        if found:
            raise DomainError(UNDER_18_TEXT.format(found=found), 422, 'under_18')


def youthful(text: str) -> list[str]:
    """The words in an Appearance that give them a child's or teenager's look. Unlike the slop audit, the user's own
    words are no exception: an adult with a schoolgirl's look is refused wherever it came from."""
    return list(dict.fromkeys(found[0] for found in YOUTHFUL.finditer(text or '')))


def looks_adult(appearance: str) -> None:
    found = youthful(appearance)
    if found:
        raise Unusable(YOUTHFUL_PROBLEM.format(found=', '.join(f'"{word}"' for word in found)))


def instructions_in(text: str) -> list[str]:
    """Lines of a pasted character that talk to the app or the model, for the user to look at."""
    return list(dict.fromkeys(line.strip()[:200] for line in (text or '').splitlines() if INSTRUCTION.search(line)))[:5]


def without_instructions(text: str) -> str:
    """The pasted character without the lines `instructions_in` names: the model never reads them, since in the red-team
    runs it obeyed such a line 19 times in 20 even when told not to. The user is shown what was left out."""
    return '\n'.join(line for line in (text or '').splitlines() if not INSTRUCTION.search(line))


def fenced(text: str) -> str:
    """The user's text between the paste markers, with any marker of its own broken so it cannot close them."""
    return re.sub(r'\[\s*\[', '[ [', re.sub(r'\]\s*\]', '] ]', text))


# Asking the model -------------------------------------------------------------------------------------------------

def parse_object(text: str) -> dict:
    """The JSON object in a reply, ignoring a reasoning block, a Markdown fence or a sentence around it."""
    text = re.sub(r'<think>.*?</think>', '', text or '', flags=re.DOTALL)
    start, end = text.find('{'), text.rfind('}')
    if start < 0 or end < start:
        raise Unusable('it did not contain a JSON object.')
    try:
        # Not strict: a line break inside a string, which some models send, is kept rather than refused.
        data = json.loads(text[start:end + 1], strict=False)
    except json.JSONDecodeError as error:
        raise Unusable(f'the JSON was malformed ({error.msg}).') from error
    if not isinstance(data, dict):
        raise Unusable('it was not a JSON object.')
    return data


def ask(system: str, shape, prompt: str = 'Write the JSON now.'):
    """One request and, if the reply cannot be used, one retry that names the problem. `shape(raw, final)` is strict
    on the first reply; on the retry it makes do where it can. Each step is told to the screen (dramatis/calls.py)."""
    calls.step('Writing')
    reply = ai.complete(system, prompt)
    calls.step('Checking what came back')
    try:
        return shape(parse_object(reply), False)
    except Unusable as problem:
        retry = (f'{prompt}\n\nYour last reply was:\n{reply[:6000]}\n\n'
                 + fill(template('repair.md'), problem=str(problem)))
    calls.step('Asking again, naming what to fix')
    try:
        found = parse_object(ai.complete(system, retry))
        calls.step('Checking again')
        return shape(found, True)
    except Unusable as problem:
        raise DomainError(f"The model's draft could not be used: {problem} Try again, or fill in the form yourself.",
                          502, 'draft_unusable') from problem


# Shaping what came back -------------------------------------------------------------------------------------------

# Where a sentence ends: its stop, any closing quote or bracket, then a space or the end.
SENTENCE_END = re.compile(r'[.!?…]["”’\')\]]*(?=\s|$)')


def cut(text: str, limit: int) -> str:
    """A text within its limit: at the last full sentence that fits, when that keeps at least half, else at the last
    whole word. Never mid-word."""
    if len(text) <= limit:
        return text
    kept = text[:limit + 1]
    ends = [match.end() for match in SENTENCE_END.finditer(kept) if match.end() <= limit]
    if ends and ends[-1] > limit // 2:
        return kept[:ends[-1]].rstrip()
    space = kept.rfind(' ', 0, limit + 1)
    return (kept[:space] if space > 0 else kept[:limit]).rstrip(' ,;:')


def text_value(value, limit: int) -> str:
    return cut(value.strip(), limit) if isinstance(value, str) else ''


def over(raw: dict, limits: dict[str, int]) -> list[str]:
    """The keys whose text the model wrote longer than its field holds, so `text_value` shortened them."""
    return [key for key, limit in limits.items() if isinstance(raw.get(key), str) and len(raw[key].strip()) > limit]


def list_value(value, count: int, limit: int) -> list[str]:
    items = value if isinstance(value, list) else [value] if isinstance(value, str) else []
    seen, result = set(), []
    for item in items:
        text = cut(item.strip(), limit) if isinstance(item, str) else ''
        if text and text.lower() not in seen:
            seen.add(text.lower())
            result.append(text)
    return result[:count]


def block(item) -> dict | None:
    if not isinstance(item, dict):
        return None
    days = item.get('days')
    try:
        return RoutineBlock.model_validate({
            'label': text_value(item.get('label'), 120), 'kind': item.get('kind') or 'leisure',
            'days': sorted({day for day in days if isinstance(day, int)}) if isinstance(days, list) else days,
            'start': item.get('start'), 'end': item.get('end'),
            'themes': list_value(item.get('themes'), 10, 120)}).model_dump()
    except (ValidationError, TypeError):
        return None


def schedule_value(value) -> list[dict]:
    return [found for found in map(block, value if isinstance(value, list) else []) if found][:24]


def sleeps_every_day(blocks: list[dict]) -> bool:
    return {day for item in blocks if item['kind'] == 'sleep' for day in item['days']} == set(range(7))


def traits_value(value, most: int = 3) -> list[dict]:
    """Emotional edges from a reply: a draft adds at most 3; the assistant may edit up to Companion's 12."""
    traits = []
    for item in value if isinstance(value, list) else []:
        if isinstance(item, dict) and text_value(item.get('name'), 60):
            intensity = item.get('intensity') if item.get('intensity') in ('mild', 'moderate', 'strong') else 'mild'
            traits.append({'name': text_value(item.get('name'), 60), 'intensity': intensity,
                           'note': text_value(item.get('note'), 500)})
    return traits[:most]


def age_value(value) -> int | None:
    """A whole number of years from a pick or a reply ("34", 34, "about 40"); None when it gives none."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return int(value)
    found = re.search(r'\d{1,4}', value) if isinstance(value, str) else None
    return int(found[0]) if found else None


def adults_only(age: int | None, about: str = '') -> None:
    if (age is not None and age < 18) or YOUNG.search(about or ''):
        raise DomainError(ADULTS_ONLY, 422, 'under_18')


def is_persona(picks: dict) -> bool:
    return picks.get('relationship') == PERSONA


def emotional_text(picks: dict) -> str:
    """Whether the model may add emotional edges; nothing for a persona, who has no everyday life to put them in."""
    return '' if is_persona(picks) else EDGES if edges_allowed(picks) else NO_EDGES


def edges_allowed(picks: dict) -> bool:
    words = f"{picks.get('idea', '')} {picks.get('vibe', '')}".lower()
    return bool(picks.get('emotional_edges')) or any(word in words for word in EDGE_WORDS)


def kind_value(value) -> str:
    text = re.sub(r'[^a-z0-9-]+', '-', value.strip().lower()).strip('-')[:40] if isinstance(value, str) else ''
    return '' if text in ('human', 'person', 'none') else text


class Shape:
    """Turns a model's reply into a character the form can show, with the user's picks winning. A `whole` draft (the
    quick start's) is asked for every field: one left empty sends the first reply back, and after the retry it is
    named in `missing` rather than left quietly blank."""

    def __init__(self, picks: dict, sliders: dict, plan: looks.Plan, roll: names.Roll, split: bool = False,
                 whole: bool = False):
        self.picks, self.sliders, self.plan, self.roll, self.split, self.whole = picks, sliders, plan, roll, split, whole
        self.apps = picks.get('apps') or list(APPS)
        self.depth = DRAFT_DEPTH if whole else depth_asked(picks)

    def __call__(self, raw: dict, final: bool) -> dict:
        if raw.get('under_18') is True:
            raise DomainError('Characters are always adults, and this character reads as younger than 18. Change '
                              'their age in the text, or start from the quick start.', 422, 'under_18')
        made = {key: text_value(raw.get(key), limit) for key, limit in TEXT_LIMITS.items()}
        made |= {key: list_value(raw.get(key), *limits) for key, limits in LIST_LIMITS.items()}
        made['name'] = (self.picks.get('name') or '').strip() or made['name']
        missing = [key for key in REQUIRED if not made[key]]
        if missing:
            raise Unusable(f"it left out {', '.join(missing)}.")
        age = self.picks.get('age') or age_value(raw.get('age'))
        adults_only(age, made['about'])
        looks_adult(made['appearance'])
        made['looks'], made['looks_from'] = self.plan.settle(raw.get('looks'), made['appearance'])
        looks_adult(' '.join(str(value) for value in made['looks'].values() if value))
        made |= {'age': age if age and age <= 5000 else None, 'kind': kind_value(raw.get('kind')),
                 'gender': self.picks.get('gender') or (raw.get('gender') if raw.get('gender') in GENDERS else ''),
                 'setting': (self.picks.get('setting') or '').strip()[:200], 'apps': self.apps,
                 'personality_sliders': self.sliders, 'companion': self.life(raw, made, final)} | self.inner(raw)
        try:
            character = Character.model_validate(made).model_dump()
        except ValidationError as error:
            raise Unusable(f"it did not fit the character format ({error.errors()[0]['msg']}).") from error
        missing = self.missing(character) if self.whole else []
        if missing and not final:
            raise Unusable(f"it left {', '.join(missing)} empty. Write every key.")
        hits = slop.audit(character, self.allowed())
        if slop.hard(hits) and not final:
            raise Unusable(slop.problem(slop.hard(hits)))
        character, hits = self.renamed(character, hits)
        character['written'] = self.written(raw, character)
        result = {'character': character, 'audit': hits}
        life = 'companion' in self.apps and not is_persona(self.picks)
        if shortened := over(raw, TEXT_LIMITS | (LIFE_TEXT if life else {})):
            result['shortened'] = shortened
        if self.whole:
            result['missing'] = missing
        if self.split:
            filled = raw.get('filled_in') if isinstance(raw.get('filled_in'), list) else []
            result['filled_in'] = [key for key in dict.fromkeys(filled)
                                   if key in made and key not in ('name', 'arc', 'psyche', 'secret')]
        return result

    def renamed(self, character: dict, hits: list[dict]) -> tuple[dict, list[dict]]:
        """After the retry: the stock and made-up names the model kept, swapped for drawn ones (names.Roll.swaps)."""
        swaps = self.roll.swaps(slop.hard(hits), character.get('name') or '')
        if not swaps:
            return character, hits
        try:
            swapped = Character.model_validate(names.replaced(character, swaps)).model_dump()
        except ValidationError:
            return character, hits
        return swapped, slop.audit(swapped, self.allowed())

    def inner(self, raw: dict) -> dict:
        """The arc and psyche, when the user's words asked for them, and a pasted character's secret, kept in its own
        field so no other field carries it; anything else the model sent is dropped."""
        found = {}
        if self.split or self.whole:
            secret = raw.get('secret') if isinstance(raw.get('secret'), dict) else {}
            found['secret'] = {key: text_value(secret.get(key), limit) for key, limit in SECRET_LIMITS.items()}
        if 'arc' in self.depth:
            arc = raw.get('arc') if isinstance(raw.get('arc'), dict) else {}
            found['arc'] = {key: text_value(arc.get(key), 300) for key in ARC_KEYS}
        if 'psyche' in self.depth:
            psyche = raw.get('psyche') if isinstance(raw.get('psyche'), dict) else {}
            found['psyche'] = {key: {'text': text_value(psyche.get(key), 300)} for key in PSYCHE_KEYS}
        return found

    def written(self, raw: dict, character: dict) -> list[str]:
        """The fields the model wrote: in a split, only those the user's text said nothing about; in a draft, every
        field it filled, but never a name the user picked."""
        if self.split:
            filled = raw.get('filled_in') if isinstance(raw.get('filled_in'), list) else []
            return [key for key in dict.fromkeys(filled) if isinstance(key, str) and key in WRITTEN_KEYS
                    and filled_at(character, key)]
        picked = 'name' if (self.picks.get('name') or '').strip() else ''
        return [key for key in WRITTEN_KEYS if key != picked and filled_at(character, key)]

    def missing(self, character: dict) -> list[str]:
        """The fields a whole draft asked for that came back empty, by the keys the form and Help me write use.
        Emotional edges are left out: they stay empty unless the user asked for them."""
        keys = [*TEXT_LIMITS, *LIST_LIMITS, *(f'arc.{key}' for key in ARC_KEYS),
                *(f'psyche.{key}' for key in PSYCHE_KEYS), *(f'secret.{key}' for key in SECRET_LIMITS)]
        if 'companion' in self.apps and not is_persona(self.picks):
            keys += ['routine', 'life_themes', 'schedule']
        return [key for key in keys if not filled_at(character, key)]

    def allowed(self) -> str:
        """What the user typed or pasted: names and words from it are theirs, whatever the audit list says."""
        return ' '.join(str(self.picks.get(key) or '') for key in ('name', 'idea', 'vibe', 'setting', 'text'))

    def life(self, raw: dict, made: dict, final: bool) -> dict:
        """Companion's part: how they know the user (the user's picks) and, when they are made for Companion as a
        companion rather than a persona, the everyday life the model wrote."""
        life = {'relationship': self.picks.get('relationship') or 'friendship',
                'timezone': (self.picks.get('timezone') or '')[:64]}
        if 'companion' not in self.apps or is_persona(self.picks):
            return life
        blocks = schedule_value(raw.get('schedule'))
        if not sleeps_every_day(blocks) and not final:
            raise Unusable(SLEEP_PROBLEM)
        life |= {key: text_value(raw.get(key), limit) for key, limit in LIFE_TEXT.items()}
        life |= {'schedule': blocks, 'life_themes': list_value(raw.get('life_themes'), 20, 120),
                 'texting': {'lowercase': bool(LOWERCASE.search(made['voice']))}}
        if edges_allowed(self.picks):
            life['emotional_traits'] = traits_value(raw.get('emotional_traits'))
        else:
            life['absence_reaction'] = ''
        return life


def own_words(character: dict) -> dict:
    """The character with every field a model wrote (`written`) emptied: what is left is the user's own, which the
    audit never holds against a model."""
    found = json.loads(json.dumps(character))
    for key in character.get('written') or []:
        if key not in WRITTEN_KEYS:
            continue
        if key in slop.DEPTH:
            *outer, last = slop.DEPTH[key][1]
            place = found
            for part in outer:
                place = place.get(part) if isinstance(place, dict) else None
            if isinstance(place, dict):
                place[last] = ''
        elif key in LIFE_KEYS:
            if isinstance(found.get('companion'), dict):
                found['companion'][key] = [] if isinstance(found['companion'].get(key), list) else ''
        else:
            found[key] = [] if isinstance(found.get(key), list) else ''
    found.pop('written', None)
    return found


def filled_at(character: dict, key: str) -> bool:
    """Whether a character has something in a field named the form's way: `arc.lie`, `psyche.was`, `routine`."""
    if key.startswith('psyche.'):
        value = ((character.get('psyche') or {}).get(key[7:]) or {}).get('text')
    elif '.' in key:
        part, inner = key.split('.', 1)
        value = (character.get(part) or {}).get(inner)
    else:
        value = character[key] if key in character else character['companion'].get(key)
    return bool(value.strip() if isinstance(value, str) else value)


# The three requests -----------------------------------------------------------------------------------------------

def new_seed() -> str:
    return secrets.token_hex(5)


def rolled(words: str, seed: str) -> dict:
    """The sliders the app decides before the model writes: what the user's words say, the rest rolled by seed."""
    return personality.settle({}, seed, personality.from_words(words))


def looks_plan(seed: str, picks: dict, words: str) -> looks.Plan:
    """Their Details, settled before the model writes: what `words` speak of is the model's to read, the rest rolled."""
    return looks.Plan(seed, words=words, gender=picks.get('gender') or '', age=age_value(picks.get('age')),
                      setting=(picks.get('setting') or '').strip())


def names_roll(seed: str, picks: dict, words: str) -> names.Roll:
    """The names a draft is offered, drawn for their gender, age and where and when they come from."""
    return names.Roll(seed, gender=picks.get('gender') or '', age=age_value(picks.get('age')),
                      setting=(picks.get('setting') or '').strip(), words=words)


def looks_text(plan: looks.Plan) -> str:
    return '\n\n'.join(part for part in (plan.brief(), plan.ask()) if part)


def personality_brief(sliders: dict) -> str:
    lines = '\n'.join(f'- {line}' for line in personality.behaviour(personality.levels_of(sliders)))
    return f'{PERSONALITY_BRIEF}\n{lines}' if lines else ''


def picks_text(picks: dict) -> str:
    apps = picks.get('apps') or list(APPS)
    rows = [('Idea', picks.get('idea') or 'None given. Surprise them with someone ordinary and specific.'),
            ('Name', picks.get('name')), ('Gender', picks.get('gender')), ('Age', picks.get('age')),
            ('Where and when they come from', picks.get('setting')), ('Vibe', picks.get('vibe')),
            ('Who they are to the user', PERSONA_PICK) if is_persona(picks) else
            ('Relationship to the user', picks.get('relationship') if 'companion' in apps else ''),
            ('Made for', '; '.join(APP_NAMES[app] for app in apps))]
    return '\n'.join(f'- {label}: {value}' for label, value in rows if value)


def draft(picks: dict) -> dict:
    """A whole character from the quick start's picks, for the form to review; nothing is saved."""
    adults_only(picks.get('age'))
    adult_text(picks.get('idea') or '', picks.get('vibe') or '')
    seed = new_seed()
    words = f"{picks.get('idea', '')} {picks.get('vibe', '')}"
    sliders = rolled(words, seed)
    calls.step('Settling how they look')
    plan = looks_plan(seed, picks, words)
    calls.step('Drawing names')
    roll = names_roll(seed, picks, words)
    system = fill(template('draft.md'), rules=template('rules.md'), picks=picks_text(picks),
                  personality=personality_brief(sliders), looks=looks_text(plan),
                  names=roll.brief(named=bool((picks.get('name') or '').strip())), emotional=emotional_text(picks),
                  depth=draft_depth_text(),
                  shape=shape_text(picks.get('apps') or list(APPS), depth=DRAFT_DEPTH, persona=is_persona(picks),
                                   secret=True, looks_shape=plan.shape()))
    return ask(system, Shape(picks, sliders, plan, roll, whole=True)) | {'seed': seed}


def split(picks: dict) -> dict:
    """A whole pasted character split into the fields, with the ones the model had to fill in; nothing is saved.
    Lines that talk to the app or the model are left out of everything the model reads, and named back."""
    adult_text(picks['text'])
    text = without_instructions(picks['text'])
    seed = new_seed()
    sliders = rolled(text, seed)
    calls.step('Settling how they look')
    plan = looks_plan(seed, picks, text)
    calls.step('Drawing names')
    roll = names_roll(seed, picks, text)
    depth = depth_asked(picks)
    system = fill(template('split.md'), rules=template('rules.md'), shape=shape_text(picks.get('apps') or list(APPS),
                  split=True, depth=depth, persona=is_persona(picks), looks_shape=plan.shape()),
                  looks=looks_text(plan), names=roll.brief(named=False, pasted=True), emotional=emotional_text(picks),
                  depth=depth_text(depth))
    # In the message, not the instructions, and inside markers it cannot close.
    pasted = f'The character I pasted:\n[[pasted]]\n{fenced(text)}\n[[end of pasted]]\n\nWrite the JSON now.'
    found = ask(system, Shape({key: value for key, value in picks.items() if key != 'name'}, sliders, plan, roll,
                              split=True), pasted)
    return found | {'seed': seed, 'instructions': instructions_in(picks['text'])}


def rewrite(character: dict, field: str, request: str = '') -> dict:
    """A new value for one field, written to fit the rest of the character as the form has it."""
    guides = field_guides()
    if field not in guides:
        raise DomainError(f'{field} cannot be rewritten.', 422)
    guide = guides[field]
    current = for_model(character, secret=sees_secret(field))
    roll = names.Roll(new_seed(), gender=character.get('gender') or '', age=age_value(character.get('age')),
                      setting=character.get('setting') or '', words=character.get('about') or '')
    system = fill(template('field.md'), rules=template('rules.md'), field=field, field_guide=guide['guide'],
                  field_shape=guide['shape'], emotional=FIELD_EDGES,
                  names='' if field in NO_PEOPLE else roll.others_brief(),
                  request=f'What the user wants changed: {request.strip()}' if request.strip() else '',
                  character=json.dumps(current, ensure_ascii=False, indent=1))
    allowed = f"{json.dumps(own_words(character), ensure_ascii=False)} {request}"
    own = character.get('name') or ''
    return ask(system, lambda raw, final: audited(field, field_value(field, guide, raw, final), allowed, final,
                                                 roll, own))


def audited(field: str, value, allowed: str, final: bool, roll: names.Roll | None = None, own: str = '') -> dict:
    """A rewritten field through the audit: hard hits the character didn't already have go back once, and a stock or
    made-up name still there after that is swapped for a drawn one."""
    hits = slop.audit(placed(field, value), allowed)
    if slop.hard(hits) and not final:
        raise Unusable(slop.problem(slop.hard(hits)))
    if roll and (swaps := roll.swaps(slop.hard(hits), own)):
        value = names.replaced(value, swaps)
        hits = slop.audit(placed(field, value), allowed)
    return {'field': field, 'value': value, 'audit': hits}


def placed(field: str, value) -> dict:
    """One field's value where it sits in a character, for the audit: arc.lie under arc, routine under companion."""
    if field in slop.DEPTH:
        for key in reversed(slop.DEPTH[field][1]):
            value = {key: value}
        return value
    return {field: value} if field in slop.FIELDS else {'companion': {field: value}}


def field_value(field: str, guide: dict, raw: dict, final: bool):
    value = raw.get('value', raw.get(field))
    if field == 'schedule':
        blocks = schedule_value(value)
        if not blocks or (not sleeps_every_day(blocks) and not final):
            raise Unusable(SLEEP_PROBLEM)
        return blocks
    if 'count' in guide:
        found = list_value(value, guide['count'], guide['limit'])
    else:
        found = text_value(value, guide['limit'])
    if not found:
        raise Unusable(f'"{field}" was empty.')
    if field == 'appearance':
        looks_adult(found)
    return found

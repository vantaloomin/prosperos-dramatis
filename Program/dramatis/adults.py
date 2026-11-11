"""Characters are always adults: an age pick, a reply or an About under 18 is refused, and so is the user's own text
(a pasted character, an idea, a vibe) when it gives them an age under 18 or a school year, before any model call,
since a model told to make them adult would quietly age them up instead. An Appearance that gives an adult a child's
or teenager's look is refused wherever it came from."""
import re

from dramatis.asking import Unusable
from dramatis.formats.companion.errors import DomainError

ADULTS_ONLY = 'Characters are always adults. Give them an age of 18 or older, or leave their age open.'
# An age the about line gives that is under 18 ("is 16", "a 15-year-old").
YOUNG = re.compile(r"\b(?:is|am|aged?)\s+(?:1[0-7]|[1-9])\b(?!\s*(?:years?\s+(?:ago|later|since)|%|:))"
                   r"|\b(?:1[0-7]|[1-9])[- ]years?[- ]old\b", re.IGNORECASE)
# What the user's own words (a pasted character, an idea, a vibe) say about the character's age now: an age under 18
# in figures or words, or a school year. Read one sentence at a time, see `young_text`.
UNDER = (r'(?:1[0-7]|[2-9]|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen'
         r'|sixteen|seventeen)')
# A number that is not an age: "ten times angrier", "16 years older", "sixteen years sober" ("16 years old" is one).
NOT_AN_AGE = (r"(?!\s*(?:times|percent|%|(?:years?|yrs?)\b(?![- ]old)|minutes|hours|days|weeks|months|feet|inches"
              r"|pounds|kilos|kg|lbs|of)\b)")
ORDINAL = r'(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth|(?:[1-9]|1[0-2])(?:st|nd|rd|th))'
# A school for teenagers, but not a game, a reunion or a building someone works at.
SCHOOL = (r"(?:(?:the|a)\s+)?(?:[\w'’.-]+\s+){0,2}?(?:high|middle|secondary|junior high)[- ]?school\b"
          r"(?!['’]s|\s+(?:football|basketball|games?|reunions?|sports|plays?|dances?|events?|teachers?|staff)\b)")
YOUNG_TEXT = re.compile(
    rf"\b(?:is|am|are|'s|’s|aged?)\s+(?:only\s+|just\s+|barely\s+|now\s+)?{UNDER}"
    r"(?=\s*(?:$|[.,;!?)]|years?\b|yrs?\b|y/?o\b|and\b|but\b|now\b|-years?))"
    rf"|\b{UNDER}[- ]years?[- ]old\b"
    rf"|^\W*age\s*[:=\-]\s*{UNDER}\b"
    r"|\b(?:freshman|sophomore|junior|senior)\s+(?:at|in)\s+(?:[\w'’.-]+\s+){0,3}?(?:high|middle|junior high)\b"
    r"(?!\s+(?:management|managers?|ground|class|income|earth|ages)\b)"
    r"|\b(?:high|middle|secondary)[- ]school\s+(?:student|kid|freshman|sophomore|junior|senior|girl|boy)\b"
    rf"|\b(?:high|middle)[- ]schooler\b|\b{ORDINAL}[- ]grader?\b"
    # "just turned 14", "at sixteen she raises her brothers" (now, not "at 15 she ran away"), a sentence that opens
    # with the age ("Seventeen, with a fake ID").
    rf"|\bturned\s+{UNDER}\b{NOT_AN_AGE}"
    rf"|\bat\s+{UNDER}\b,?\s+(?:she|he|they|i)\s+(?:\w+ly\s+|still\s+|already\s+)?(?:(?!was\b|has\b)\w+s|is|are|am)\b"
    r"|^\W*(?:1[3-7]|thirteen|fourteen|fifteen|sixteen|seventeen)\s*[,;:]"
    # Still at school now: still in, finishing or going to high school, a year left of it, on the student council.
    rf"|\b(?:still|currently)\s+(?:in|at|attending)\s+{SCHOOL}"
    rf"|\b(?:finishing|finishes|attends|attending|goes\s+to|going\s+to)\s+{SCHOOL}"
    rf"|\b(?:a|one|two|three)\s+(?:more\s+)?years?\s+(?:left|to go)\s+(?:of|in|at|until|before)\s+{SCHOOL}"
    r"|\bstudent council\b", re.IGNORECASE | re.MULTILINE)
# An age set beside the name a sentence opens with: "Mara, 15, lives with her aunt", "Theo (16) skateboards". The
# name is matched as written.
NAMED_AGE = re.compile(rf"^\W*[A-Z][\w'’-]+(?:\s+[A-Z][\w'’-]+)?(?:,\s*|\s*\(\s*)(?i:{UNDER})\s*[,)]")
# Before the match in its sentence: the past (when she was a junior at...), or a job with young people in it (teaches
# 10th grade). These hold for the whole sentence.
NOT_NOW = re.compile(r"\b(?:was|were|used to|back then|when|until|ago|the (?:year|summer|day|night|week|month)"
                     r"|teach\w*|coach\w*|tutor\w*|counsel\w*|principal)\b", re.IGNORECASE)
# Someone else whose age it may be (her son is 12): only when the age follows them with no she, he or they between,
# so "she lives with her mom, and she is 15" is still hers.
RELATIVE = re.compile(r"\b(?:daughters?|sons?|kids?|child(?:ren)?|sisters?|brothers?|siblings?|nieces?|nephews?"
                      r"|cousins?|grand\w+|step\w+|students?|pupils?|parents?|mom|dad|mother|father|aunt|uncle|friends?"
                      r"|boyfriend|girlfriend)\b", re.IGNORECASE)
# After a named age: "Tom (12) is her nephew".
NAMED_RELATIVE = re.compile(r"\W*(?:is|was)?\s*(?:her|his|their|my)\s+(?:\w+\s+)?" + RELATIVE.pattern, re.IGNORECASE)
SUBJECT = re.compile(r"\b(?:she|he|they|i|we)\b", re.IGNORECASE)
# Just before "is 12": someone or something named as another's (her bike is ten years old, the boy is 12).
POSSESSED = re.compile(r"\b(?:her|his|their|my|our|your|its|the)\s+(?!(?:a|an|the)\b)[\w'’-]+\s*,?\s*$",
                       re.IGNORECASE)
# After "a 15-year-old": someone else, not the character.
SOMEONE_ELSE = re.compile(r"\s*(?:daughter|son|kid|child|sister|brother|sibling|niece|nephew|cousin|student|pupil"
                          r"|dog|cat|horse|car|truck|bike|house|whisky|whiskey|scotch|wine|tree)", re.IGNORECASE)
# A request to make the character younger than 18 ("make her sixteen", "turn Dana into a high school sophomore",
# "age her down to 17"), and a reply that says it did ("her age is now 16").
ASKS_YOUNG = re.compile(
    r"\b(?:make|makes|making|turn|change|rewrite|write|age|play|de-?age|have)\s+(?:her|him|them|me|the character|\w+)"
    r"\s+(?:into\s+|as\s+|be\s+)?(?:an?\s+|only\s+|just\s+|about\s+|around\s+)?"
    rf"(?:{UNDER}\b{NOT_AN_AGE}(?:[- ]years?[- ]old)?|teen(?:age|ager)?s?\b|minor\b|child\b|kid\b(?!\s+at heart)|school(?:girl|boy)"
    rf"|(?:high|middle|junior high)[- ]school\w*|{ORDINAL}[- ]grader?"
    r"|(?:freshman|sophomore)\s+(?:in|at)\s+(?!(?:\w+\s+){0,3}?(?:college|university|uni|grad)\b))"
    # "age her down to 17", "younger, like a teenager", "before she turned eighteen", "still at school".
    rf"|\b(?:age|de-?age|make|bring)\s+(?:\w+\s+){{0,2}}(?:down|back|younger)\s+(?:to\s+)?{UNDER}\b{NOT_AN_AGE}"
    rf"|\byounger\b[^.?!]{{0,20}}\b(?:teen\w*|minor|kid|child|{UNDER}\b{NOT_AN_AGE})"
    r"|\bbefore (?:she|he|they) turned (?:eighteen|18)\b|\bstill (?:at|in) school\b|\b(?:bus|walk|ride) to school\b",
    re.IGNORECASE)
SAYS_YOUNG = re.compile(rf"\b(?:age|aged)\b[^.!?]{{0,40}}?\b(?:to|is now|now)\s+{UNDER}\b{NOT_AN_AGE}",
                        re.IGNORECASE)
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


def young_text(text: str) -> str:
    """The words in the user's own text that make the character younger than 18 now, or ''. Someone else's age (her
    son is 12), their past (when she was a junior at Lincoln High) and work with young people are left alone."""
    for sentence in re.split(r'(?<=[.!?;])\s+|\n+', text or ''):
        for found in [*YOUNG_TEXT.finditer(sentence), *NAMED_AGE.finditer(sentence)]:
            if not theirs(sentence, found):
                continue
            return found[0].strip(' ,;:()')
    return ''


def theirs(sentence: str, found: re.Match) -> bool:
    """Whether an age or school year in a sentence is the character's, now."""
    before = sentence[:found.start()]
    if NOT_NOW.search(before) or POSSESSED.search(before):
        return False
    relatives = list(RELATIVE.finditer(before))
    if relatives and not SUBJECT.search(before[relatives[-1].end():] + found[0]):
        return False
    after = sentence[found.end():]
    if found.re is NAMED_AGE and NAMED_RELATIVE.match(after):
        return False
    return not (found[0].lower().endswith('old') and SOMEONE_ELSE.match(after))


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


def adult_request(*texts: str) -> None:
    """Refuses a request to the model (a message to the assistant, a Help me write ask) that would make them a minor,
    before the model runs: a model asked for it may comply in everything but the age."""
    for text in texts:
        found = ASKS_YOUNG.search(text or '')
        found = found[0] if found else young_text(text)
        if found:
            raise DomainError(f'{ADULTS_ONLY} ("{found.strip()}")', 422, 'under_18')


def says_young(text: str) -> str:
    """The words in a model's reply that make them younger than 18 now, or ''."""
    if found := young_text(text):
        return found
    found = SAYS_YOUNG.search(text or '')
    return found[0] if found else ''

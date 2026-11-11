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

"""Asking the user's model for one JSON object, and the first shaping of what comes back: every model call in
Dramatis that wants a structured answer goes through `ask` (dramatis/ai.py does the calling). A reply that cannot be
used is asked for once more with the problem named (prompts/repair.md), and refused after that. Text is trimmed to
its field's limit at a sentence or a word, never mid-word."""
import json
import re
from pathlib import Path

from dramatis import ai, calls
from dramatis.formats.companion.errors import DomainError

PROMPTS = Path(__file__).parent / 'prompts'


# A height's inch mark straight after feet and inches (5'10" or 5' 10"), when it is not the string's own end: what
# follows the end of a string is a colon, a closing bracket, or a comma before the next string or the end.
HEIGHT = re.compile(r"""(\d['’]\s?\d{1,2})"(?!\s*(?:[:}\]]|,\s*["{\[\]}]|$))""")
# The dashes the AI-slop audit holds against a draft (data/ai-slop.json, em_dash), and a range of numbers between them.
DASH = re.compile(r'\s*(?:—|–|(?<=\w)--(?=\w)|\s--\s|\s-\s)\s*')
RANGE = re.compile(r'(?<=\d)\s*[–—]\s*(?=\d)')


class Unusable(Exception):
    """The model's reply could not become a character; the message says why, for the one retry."""


def template(name: str) -> str:
    return (PROMPTS / name).read_text(encoding='utf-8')


def fill(text: str, **values: str) -> str:
    for key, value in values.items():
        text = text.replace('{{' + key + '}}', value)
    return text


def parse_object(text: str) -> dict:
    """The JSON object in a reply, ignoring a reasoning block, a Markdown fence or a sentence around it."""
    text = re.sub(r'<think>.*?</think>', '', text or '', flags=re.DOTALL)
    start, end = text.find('{'), text.rfind('}')
    if start < 0 or end < start:
        raise Unusable('it did not contain a JSON object.')
    found = text[start:end + 1]
    try:
        # Not strict: a line break inside a string, which some models send, is kept rather than refused.
        data = json.loads(found, strict=False)
    except json.JSONDecodeError as error:
        # A height in feet and inches (5'10") whose inch mark ends the string early: escaped, then read once more.
        try:
            data = json.loads(HEIGHT.sub(r'\1\\"', found), strict=False)
        except json.JSONDecodeError:
            raise Unusable(f'the JSON was malformed ({error.msg}).') from error
    if not isinstance(data, dict):
        raise Unusable('it was not a JSON object.')
    return undashed(data)


def undashed(value):
    """Every text in a reply with its dashes made plain punctuation: a range takes a hyphen, an aside commas. The
    audit holds a dash against a draft, and swapping them here saves sending most replies back."""
    if isinstance(value, dict):
        return {key: undashed(item) for key, item in value.items()}
    if isinstance(value, list):
        return [undashed(item) for item in value]
    if not isinstance(value, str) or not DASH.search(value):
        return value
    text = RANGE.sub('-', value)
    text = DASH.sub(', ', text)
    text = re.sub(r',\s*([,.;:!?)])', r'\1', text)
    text = re.sub(r'([(\n]|^),\s*', r'\1', text)
    return text.rstrip(', ')


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

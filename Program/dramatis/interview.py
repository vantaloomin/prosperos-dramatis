"""The in-voice interview: the character answers about 14 questions as themselves (prompts/interview.md), and what
they said can become proposals for their fields (prompts/from-interview.md). Both are routes of their own here.

- `interview` returns the transcript and one sample line of their speech, for the form to show under How they talk.
  They know their own secret and keep it: they may steer around it, but never say it.
- `proposals` reads the transcript back and suggests new values for a few fields (PROPOSABLE), each with a reason.
  Nothing changes until the user applies one on the form. `sound` is never proposed: it is the physical voice, which a
  written interview cannot show.
- Both go through `drafting.ask` like any draft: a reply that cannot be used is asked for once more, and hard hits
  from the AI-slop audit are sent back once. Nothing is saved.
"""
import json
import re

from fastapi import APIRouter
from pydantic import BaseModel, Field

from dramatis import drafting, slop
from dramatis.drafting import Unusable, ask, fill, template, text_value
from dramatis.formats.companion.errors import require

LIMIT = 16000
SAMPLE = 120
PROPOSABLE = ('voice', 'appearance', 'seen_as', 'sees_self', 'flaws', 'interests')
# A line of quoted speech short enough to be the sample.
QUOTE = re.compile(r'["“]([^"“”\n]{8,%d})["”]' % SAMPLE)


def trimmed(text: str) -> str:
    """The transcript within its limit, cut at the last paragraph that fits rather than mid-sentence, and without a
    question left hanging at the end."""
    if len(text) <= LIMIT:
        return text
    cut = text[:LIMIT]
    end = cut.rfind('\n\n')
    paragraphs = (cut[:end] if end > LIMIT // 2 else cut).rstrip().split('\n\n')
    if len(paragraphs) > 1 and paragraphs[-1].startswith('**') and paragraphs[-1].endswith('**'):
        paragraphs.pop()
    return '\n\n'.join(paragraphs).rstrip()


def sample_of(transcript: str, offered) -> str:
    """The model's sample line when it is really in the transcript and short enough; else the first quoted line that
    is."""
    line = text_value(offered, 400).strip('"“” ') if isinstance(offered, str) else ''
    if line and len(line) <= SAMPLE and line in transcript:
        return line
    found = QUOTE.search(transcript)
    return found[1].strip() if found else ''


def interview(character: dict) -> dict:
    """Their interview and a sample line, for the form to show; nothing is saved."""
    require(bool(str(character.get('about') or '').strip() or str(character.get('personality') or '').strip()),
            'Write About them or their personality first, so they have something to talk from.', 422)
    sliders = character.get('personality_sliders') or {}
    system = fill(template('interview.md'), rules=template('rules.md'),
                  personality=drafting.personality_brief(sliders) if sliders else '',
                  character=json.dumps(drafting.for_model(character), ensure_ascii=False, indent=1))
    allowed = json.dumps(character, ensure_ascii=False)

    def shape(raw: dict, final: bool) -> dict:
        transcript = trimmed(text_value(raw.get('interview'), LIMIT * 2))
        if not transcript:
            raise Unusable('"interview" was empty.')
        hits = slop.audit({'interview': transcript}, allowed)
        if slop.hard(hits) and not final:
            raise Unusable(slop.problem(slop.hard(hits)))
        return {'interview': transcript, 'sample': sample_of(transcript, raw.get('sample')), 'audit': hits}

    return ask(system, shape)


def proposal_value(field: str, value):
    if field in drafting.LIST_LIMITS:
        return drafting.list_value(value, *drafting.LIST_LIMITS[field])
    return text_value(value, drafting.TEXT_LIMITS[field])


def unchanged(character: dict, field: str, value) -> bool:
    current = character.get(field)
    if isinstance(value, list):
        return [item.strip() for item in current or [] if isinstance(item, str) and item.strip()] == value
    return (current or '').strip() == value


def proposals(character: dict) -> dict:
    """What the interview suggests for their fields, as proposals the user applies or dismisses; nothing changes
    here."""
    require(bool(str(character.get('interview') or '').strip()), 'Hear them talk first: there is no interview yet.',
            422)
    guides = drafting.field_guides()
    fields = '\n'.join(f"- {field} ({guides[field]['shape']}): {guides[field]['guide']}" for field in PROPOSABLE)
    system = fill(template('from-interview.md'), rules=template('rules.md'), fields=fields,
                  character=json.dumps(drafting.for_model(character, interview=True), ensure_ascii=False, indent=1))
    allowed = json.dumps(character, ensure_ascii=False)

    def shape(raw: dict, final: bool) -> dict:
        items = raw.get('proposals')
        if not isinstance(items, list):
            raise Unusable('it had no "proposals" list.')
        found = {}
        for item in items:
            field = item.get('field') if isinstance(item, dict) else None
            if field not in PROPOSABLE or field in found:
                continue
            value = proposal_value(field, item.get('value'))
            if value and not unchanged(character, field, value):
                found[field] = {'field': field, 'value': value, 'reason': text_value(item.get('reason'), 300)}
        hits = slop.audit({field: item['value'] for field, item in found.items()}, allowed)
        if slop.hard(hits) and not final:
            raise Unusable(slop.problem(slop.hard(hits)))
        return {'proposals': list(found.values()), 'audit': hits}

    return ask(system, shape)


# Routes -----------------------------------------------------------------------------------------------------------

class CharacterBody(BaseModel):
    model_config = {'extra': 'forbid'}
    character: dict = Field(default_factory=dict)


router = APIRouter(prefix='/api/draft')


@router.post('/interview')
def interview_route(body: CharacterBody):
    return interview(body.character)


@router.post('/from-interview')
def proposals_route(body: CharacterBody):
    return proposals(body.character)

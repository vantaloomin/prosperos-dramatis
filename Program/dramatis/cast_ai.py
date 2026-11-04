"""AI help on the Cast board (the Cast-layer spec's package D): Suggest corners, Check my square, Find the turn and
Suggest a relationship, each a route under /api/cast-ai.

- Every call reads the board as it stands, saved or not, and returns proposals. Nothing here writes to disk: the board
  changes only when the author applies a proposal, and the cast file only when they save it.
- Each goes through `drafting.ask` like any draft: the reply's JSON is read leniently, a reply that cannot be used is
  asked for once more with the problem named, and hard hits from the AI-slop audit are sent back once. What is left
  of the audit comes back as `audit`, each hit's `field` saying where it sits (`proposals.0.stance`, `turn`,
  `proposal.dynamic`).
- The board goes to the model as JSON (`board`), with the characters in its corners by name. The people a turn or a
  relationship is about also go with a brief of their own form (`brief`), their secret included, since a secret
  travels with the character and is often what a turn or a hidden tension turns on.
- Suggested tags are matched to the tag bank where they can be (`bank_tag`) and kept as typed where they can't; a
  suggestion whose stance reads as the wrong kind is still returned, for Check my square to flag.
- Check my square's flags are soft, like the computed checks: they sit beside them and block nothing.
"""
import json
import re

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from dramatis import casts, drafting, library, slop
from dramatis.casts import Cast, Corner, Square, name_of
from dramatis.drafting import Unusable, ask, fill, template, text_value
from dramatis.formats.companion.errors import require

FEWEST, MOST = 2, 4
TURN = 400  # the link's note, where Apply puts the turn
READS_AS = ('value', 'method', 'secret')
# The four-corner web's judgement calls, which the computed checks only remind about (casts.REMINDERS).
JUDGEMENTS = ('challenger-has-flaw', 'comforter-not-villain', 'warning-sympathetic')
# What a brief of a character keeps: who they are, what they want and fear, how they fall short, how they're seen,
# and what they hide.
BRIEF = ('name', 'kind', 'age', 'about', 'personality', 'wants', 'fears', 'flaws', 'seen_as', 'sees_self', 'arc',
         'psyche', 'secret')
# Endings dropped before a tag is compared with the bank, longest first; 'ation' keeps its t (negotiating, negotiation).
SUFFIXES = {'ation': 'at', 'ing': '', 'ion': '', 'ed': '', 'es': '', 's': '', 'y': '', 'e': ''}


# ---- The board as the model reads it ------------------------------------------------------------------------------

def axis_text(square: Square) -> str:
    """What a square's corners disagree about: the bank's name and help, and the author's words when there are any."""
    found = next((item for item in casts.bank('axes') if item['kind'] == square.axis.kind), {})
    text = f"{found.get('label', square.axis.kind)} ({found.get('help', '')})".replace(' ()', '')
    return f'{text}, in the author\'s words: "{square.axis.label}"' if square.axis.label else text


def corner_view(corner: Corner, names: dict[str, str]) -> dict:
    view = {'id': corner.id, 'label': corner.label, 'stance': corner.stance, 'tags': corner.tags, 'role': corner.role,
            'fields': corner.fields, 'note': corner.note}
    if corner.character_id:
        view['character'] = names.get(corner.character_id, 'someone no longer in the library')
    return {key: value for key, value in view.items() if value or key == 'stance'}


def board(cast: Cast, names: dict[str, str]) -> str:
    """The cast as the prompts show it: its question, template, squares and confirmed links, without library ids."""
    genre, group = casts.genre(cast.genre), next((item for item in casts.bank('groups') if item['id'] == cast.group),
                                                 None)
    sides = []
    for side in cast.outer.corners:
        view = corner_view(side, names)
        if side.inner:
            view['split'] = {'they_disagree_about': axis_text(side.inner), 'question': side.inner.question,
                             'corners': [corner_view(corner, names) for corner in side.inner.corners]}
        sides.append(view)
    links = [{'between': [link.a, link.b], 'both_work_by': link.on, 'role': link.role, 'note': link.note}
             for link in cast.resonance if link.status == 'confirmed']
    found = {'title': cast.title, 'question_the_story_asks': cast.theme,
             'template': f"{genre['name']}: {genre['help']}" if genre else '',
             'group': f"{group['name']}, who share {group['shares'][:1].lower()}{group['shares'][1:]}" if group else '',
             'outer_square': {'they_disagree_about': axis_text(cast.outer), 'question': cast.outer.question,
                              'sides': sides},
             'confirmed_links': links}
    return json.dumps({key: value for key, value in found.items() if value}, ensure_ascii=False, indent=1)


def brief(character_id: str) -> dict:
    """A character the call is about, as much of their form as it needs; library.get refuses one that is gone."""
    shown = drafting.for_model(library.get(character_id)['character'])
    if isinstance(shown.get('secret'), dict):
        shown['secret'] = {key: value for key, value in shown['secret'].items() if value}
    return {key: shown[key] for key in BRIEF if shown.get(key) not in (None, '', [], {})}


def written(cast: Cast, *more) -> str:
    """Everything the author wrote that a call reads, so the audit leaves their own words alone."""
    return json.dumps([casts.dumped(cast), *more], ensure_ascii=False)


def audited(texts: list[tuple[str, str, str]], allowed: str, final: bool) -> list[dict]:
    """The audit of what the model wrote: hard hits send the reply back once; after that they are shown."""
    hits = slop.audit_texts([item for item in texts if item[2].strip()], allowed)
    if slop.hard(hits) and not final:
        raise Unusable(slop.problem(slop.hard(hits)))
    return hits


def cut(text: str, limit: int) -> str:
    """A text within its limit, at the last full sentence that fits when there is one."""
    if len(text) <= limit:
        return text
    kept = text[:limit]
    end = max(kept.rfind('. '), kept.rfind('! '), kept.rfind('? '))
    return kept[:end + 1] if end > limit // 2 else kept.rstrip()


# ---- Suggest corners ----------------------------------------------------------------------------------------------

def slug(text: str, limit: int = 30) -> str:
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')[:limit].strip('-')


def stem(word: str) -> str:
    for suffix, kept in SUFFIXES.items():
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[:-len(suffix)] + kept
    return word


def bank_tag(text) -> str:
    """A suggested tag as the bank has it ("Negotiating" is negotiation), else as typed, in the tag shape."""
    if not isinstance(text, str):
        return ''
    found = slug(text)
    for item in casts.bank('tags'):
        if found in (item['id'], slug(item['label'])) or stem(found) == stem(item['id']):
            return item['id']
    return found


def tags_value(value) -> list[str]:
    found = [bank_tag(item) for item in (value if isinstance(value, list) else [value])]
    return list(dict.fromkeys(item for item in found if item))[:6]


def target_of(cast: Cast, target: str) -> tuple[Square, Corner | None]:
    """The square a suggestion is for: the outer one, or the inner square under one side."""
    if target == 'outer':
        return cast.outer, None
    side = next((found for found in cast.outer.corners if found.id == target), None)
    require(side is not None, 'That side is not on the board any more.', 404)
    require(side.inner is not None, f'Split {name_of(side)} first, so its people have something to disagree about.',
            422)
    return side.inner, side


def role_fields(cast: Cast, side: Corner | None) -> dict[str, list[str]]:
    """The roles a template gives the outer square, each with the texts it asks for (the four-corner web's)."""
    if side is not None:
        return {}
    genre = casts.genre(cast.genre) or {}
    return {pick['role']: pick.get('fields', []) for pick in genre.get('outer', []) if pick.get('role')}


def ask_target(cast: Cast, square: Square, side: Corner | None) -> str:
    if side is None and square.axis.kind == 'dilemma':
        return ('Suggest the sides of the outer square. It is a dilemma with no clean answer'
                + (f': "{square.axis.label}"' if square.axis.label else '') + '. Each side is a way of living with '
                'it, and its stance says that way in one sentence, from the inside, the way someone who lives it '
                'would defend it.')
    if side is None:
        return (f'Suggest the sides of the outer square. They disagree about {axis_text(square)}. Each stance is the '
                'side\'s why: what it wants the world to be, in a way a reasonable person could hold. The sides '
                'answer the story\'s question differently, and none of them is a cartoon.')
    wants = f' (who want {side.stance})' if side.stance else ''
    question = f' The question they fight over: {square.question}' if square.question else ''
    if square.axis.kind == 'secret':
        how = (f'Each stance says how this person goes after what {name_of(side)} wants, and what they hide from the '
               'rest of the side. No two of them hide the same thing.')
    else:
        how = (f'Each stance is a how: the way this person goes after what {name_of(side)} wants, never a different '
               'why. No two of them go about it the same way.')
    return (f'Suggest the people inside {name_of(side)}{wants}. They share that why and disagree about '
            f'{axis_text(square)}.{question} {how}')


def ask_roles(cast: Cast, side: Corner | None) -> str:
    roles = role_fields(cast, side)
    if roles:
        listed = '\n'.join(f'- {role}: fields {", ".join(fields)}' if fields else f'- {role}'
                           for role, fields in roles.items())
        return ('Each side has one of these roles, and fills the fields its role lists, one plain sentence each, at most '
                '300 characters. A corner already on the board keeps its role.\n' + listed)
    group = next((item for item in casts.bank('groups') if item['id'] == cast.group), None)
    if side is not None and group:
        return (f'People in a {group["name"].lower()} often fill these roles: {", ".join(group["roles"])}. Give each '
                'corner one of them as its role where it fits, else "". Leave "fields" as {}.')
    return 'Leave "role" as "" and "fields" as {}.'


def ask_slots(square: Square) -> tuple[str, int]:
    """Which corners a suggestion can fill, and how many to ask for."""
    empty = [corner for corner in square.corners if not corner.stance]
    room = MOST - len(square.corners)
    count = max(FEWEST, min(MOST, len(empty) + room))
    parts = []
    if empty:
        named = ', '.join(f'{corner.id} ({corner.label})' if corner.label else corner.id for corner in empty)
        parts.append(f'These corners have no stance yet: {named}. Fill them first, giving each one\'s id as '
                     '"corner_id" and keeping a label it already has unless it is only a placeholder.')
    if room:
        parts.append(f'There is room for {room} more corner{"s" if room > 1 else ""}; give those "corner_id": null.')
    if not empty and not room:
        parts.append('Every corner already has a stance. Suggest other ways the square could go, each with '
                     '"corner_id": null; the author chooses which corner each would replace.')
    return ' '.join(parts), count


def proposal_value(item, square: Square, roles: dict[str, list[str]]) -> dict | None:
    if not isinstance(item, dict):
        return None
    label, stance = text_value(item.get('label'), 80), text_value(item.get('stance'), 200)
    if not (label and stance):
        return None
    corner_id = item.get('corner_id')
    role = slug(text_value(item.get('role'), 60))
    raw_fields = item.get('fields') if isinstance(item.get('fields'), dict) else {}
    fields = {key: text_value(raw_fields.get(key), 300) for key in roles.get(role, [])}
    found = {'corner_id': corner_id if corner_id in {corner.id for corner in square.corners} else None,
             'label': label, 'stance': stance, 'tags': tags_value(item.get('tags')), 'role': role}
    return found | ({'fields': fields} if fields else {})


def placed(proposals: list[dict], square: Square) -> list[dict]:
    """Each corner filled by one suggestion at most, and suggestions with no corner given the empty ones in order."""
    taken, empty = set(), [corner.id for corner in square.corners if not corner.stance]
    for found in proposals:
        if found['corner_id'] in taken:
            found['corner_id'] = None
        if found['corner_id']:
            taken.add(found['corner_id'])
    for found in proposals:
        spare = next((corner_id for corner_id in empty if corner_id not in taken), None)
        if found['corner_id'] is None and spare:
            found['corner_id'] = spare
            taken.add(spare)
    return proposals  # the rest are new corners, or, in a full square, replace the corner the author picks


def suggest(cast: Cast, target: str) -> dict:
    """Two to four corners for the outer square or one side's inner square, as proposals; nothing changes here."""
    square, side = target_of(cast, target)
    roles = role_fields(cast, side)
    slots, count = ask_slots(square)
    tags = ', '.join(item['id'] for item in casts.bank('tags'))
    system = fill(template('cast-suggest.md'), rules=template('rules.md'), board=board(cast, casts.known_names(cast)),
                  target=ask_target(cast, square, side), roles=ask_roles(cast, side), tags=tags, slots=slots,
                  count=f'{count}' if count == MOST else f'{count} to {MOST}')
    allowed = written(cast)

    def shape(raw: dict, final: bool) -> dict:
        items = raw.get('proposals', raw.get('corners'))
        if not isinstance(items, list):
            raise Unusable('it had no "proposals" list.')
        found = [value for value in (proposal_value(item, square, roles) for item in items) if value][:MOST]
        if len(found) < (1 if final else FEWEST):
            raise Unusable(f'it needs {FEWEST} to {MOST} proposals, each with a "label" and a "stance".')
        found = placed(found, square)
        texts = [(f'proposals.{index}.{key}', label, value) for index, item in enumerate(found)
                 for key, label, value in [('label', 'Name', item['label']), ('stance', 'Stance', item['stance']),
                                           *((f'fields.{name}', name.replace('_', ' ').capitalize(), text)
                                             for name, text in item.get('fields', {}).items())]]
        return {'proposals': found, 'audit': audited(texts, allowed, final)}

    return ask(system, shape)


# ---- Check my square ----------------------------------------------------------------------------------------------

def expected(cast: Cast) -> dict[str, tuple[Corner, str, str]]:
    """Each corner with a stance: what that stance should read as, and which square it is in."""
    found = {}
    for side in cast.outer.corners:
        if side.stance:
            found[side.id] = (side, 'value', 'the outer square')
        for corner in side.inner.corners if side.inner else []:
            if corner.stance:
                kind = 'secret' if side.inner.axis.kind == 'secret' else 'method'
                found[corner.id] = (corner, kind, f"{name_of(side)}'s split")
    return found


SHOULD = {'value': 'a why (a value)', 'method': 'a how (a method)', 'secret': 'a how, with what they hide'}


def ask_judgements(cast: Cast) -> list[tuple[str, Corner, str]]:
    """The web template's judgement calls that apply: each code, the corner it is about, and what should hold."""
    template_checks = (casts.genre(cast.genre) or {}).get('checks', [])
    found = []
    for code in JUDGEMENTS:
        role, message, _ = casts.REMINDERS[code]
        named = casts.by_role(cast, role)
        if code in template_checks and named:
            found.append((code, named[0], message.format(name_of(named[0]))))
    return found


def check(cast: Cast) -> dict:
    """Where a corner's stance reads as the wrong kind (a why inside a split, a how on the outer square), and the web
    template's judgement calls; every flag is soft, and nothing changes here."""
    corners = expected(cast)
    require(bool(corners), 'Write a stance on a corner first; there is nothing to check yet.', 422)
    listed = '\n'.join(f'- {corner_id} ({name_of(corner)}, in {where}): should read as {SHOULD[kind]}'
                       for corner_id, (corner, kind, where) in corners.items())
    lenient = [f'In {name_of(side)}\'s split the corners disagree about what winning means, so a stance there that '
               'names an end can still be a how. Read those leniently, and flag one only when it is a different why '
               f'from {name_of(side)}\'s.' for side in cast.outer.corners
               if side.inner and side.inner.axis.kind == 'goal-definition']
    judgements = ask_judgements(cast)
    judged = ('This board uses the four-corner web. Also judge each of these, with "holds" true or false and one plain '
              'sentence on why:\n' + '\n'.join(f'- {code}: {text}' for code, _, text in judgements)
              if judgements else 'Leave "judgements" as [].')
    system = fill(template('cast-check.md'), rules=template('rules.md'), board=board(cast, casts.known_names(cast)),
                  corners=listed, lenient='\n\n'.join(lenient), judgements=judged)
    allowed = written(cast)
    about = {code: corner for code, corner, _ in judgements}

    def shape(raw: dict, final: bool) -> dict:
        items, judged_items = raw.get('flags'), raw.get('judgements', [])
        if not isinstance(items, list) or not isinstance(judged_items, list):
            raise Unusable('it needs a "flags" list and a "judgements" list.')
        flags = {}
        for item in items:
            corner_id = item.get('corner_id') if isinstance(item, dict) else None
            if corner_id not in corners or corner_id in flags:
                continue
            reads_as, message = item.get('reads_as'), text_value(item.get('message'), 300)
            if reads_as in READS_AS and reads_as != corners[corner_id][1] and message:
                flags[corner_id] = {'corner_id': corner_id, 'reads_as': reads_as, 'message': message}
        found = {}
        for item in judged_items:
            code = item.get('code') if isinstance(item, dict) else None
            message = text_value(item.get('message'), 300) if code in about else ''
            if message and code not in found and isinstance(item.get('holds'), bool):
                found[code] = {'code': code, 'corner_id': about[code].id, 'holds': item['holds'], 'message': message}
        texts = [*((f'flags.{index}', 'Flag', item['message']) for index, item in enumerate(flags.values())),
                 *((f'judgements.{index}', 'Judgement', item['message']) for index, item in enumerate(found.values()))]
        return {'flags': list(flags.values()), 'judgements': list(found.values()),
                'audit': audited(texts, allowed, final)}

    return ask(system, shape)


# ---- Find the turn ------------------------------------------------------------------------------------------------

def person(corner: Corner, side: Corner, names: dict[str, str]) -> dict:
    """One end of a link: the corner, the side it is on, and its character's brief when it has one."""
    found = {'corner': corner_view(corner, names)}
    if side.id != corner.id:
        found['side'] = {'label': side.label, 'stance': side.stance}
    if corner.character_id and corner.character_id in names:
        found['character'] = brief(corner.character_id)
    return found


def turn(cast: Cast, a: str, b: str) -> dict:
    """Who moves across a confirmed link, when, and what it costs, as text for the link's note; nothing changes
    here."""
    links = [link for link in cast.resonance if link.status == 'confirmed' and {link.a, link.b} == {a, b}]
    require(bool(links), 'Confirm the link first; Find the turn works on a confirmed link.', 422)
    names, sides = casts.known_names(cast), casts.side_of(cast)
    by_id = {corner.id: corner for corner in casts.corners(cast)}
    one, other = by_id[a], by_id[b]
    people = {name_of(corner): person(corner, by_id[sides[corner.id]], names) for corner in (one, other)}
    link = {'between': [name_of(one), name_of(other)], 'both_work_by': [found.on for found in links],
            'role': next((found.role for found in links if found.role), ''),
            'note': next((found.note for found in links if found.note), '')}
    system = fill(template('cast-turn.md'), rules=template('rules.md'), board=board(cast, names),
                  link=json.dumps({key: value for key, value in link.items() if value}, ensure_ascii=False),
                  people=json.dumps(people, ensure_ascii=False, indent=1), limit=str(TURN))
    allowed = written(cast, people)

    def shape(raw: dict, final: bool) -> dict:
        text = text_value(raw.get('turn'), 4000)
        if not text:
            raise Unusable('"turn" was empty.')
        if len(text) > TURN and not final:
            raise Unusable(f'"turn" was {len(text)} characters; keep it within {TURN}.')
        text = cut(text, TURN)
        return {'turn': text, 'audit': audited([('turn', 'The turn', text)], allowed, final)}

    return ask(system, shape)


# ---- Suggest a relationship ---------------------------------------------------------------------------------------

def standing(cast: Cast, character_id: str, names: dict[str, str]) -> list[dict]:
    """Where a character stands on the board: each corner they are linked to, with its side."""
    sides = casts.side_of(cast)
    by_id = {corner.id: corner for corner in casts.corners(cast)}
    return [{'corner': corner.label, 'stance': corner.stance,
             **({'side': by_id[sides[corner.id]].label} if sides[corner.id] != corner.id else {})}
            for corner in casts.corners(cast) if corner.character_id == character_id]


def trust_value(value) -> int:
    found = drafting.age_value(value)
    return min(10, max(1, found)) if found is not None else 5


def relationship(cast: Cast, from_id: str, to_id: str) -> dict:
    """How `from` sees `to`: a dynamic, the hidden tension read from `from`'s wants against `to`'s flaws, and a trust
    level, as a proposal for their row; nothing changes here."""
    require(from_id != to_id, 'A relationship is between two different characters.', 422)
    names = casts.known_names(cast)
    seer, seen = brief(from_id), brief(to_id)
    who, whom = seer.get('name') or 'the first character', seen.get('name') or 'the second character'
    back = next((row for row in cast.relationships if row.from_id == to_id and row.to_id == from_id), None)
    where = {who: standing(cast, from_id, names), whom: standing(cast, to_id, names)}
    sides = casts.side_of(cast)
    their = {corner.id for corner in casts.corners(cast) if corner.character_id in (from_id, to_id)}
    links = [{'both_work_by': link.on, 'role': link.role, 'note': link.note} for link in cast.resonance
             if link.status == 'confirmed' and {link.a, link.b} <= their and sides[link.a] != sides[link.b]]
    context = {'where_they_stand': where, 'links_between_them': links,
               f'how {whom} sees {who}': ({'dynamic': back.dynamic, 'hidden_tension': back.hidden_tension,
                                           'trust': back.trust} if back else None)}
    system = fill(template('cast-relationship.md'), rules=template('rules.md'), board=board(cast, names),
                  who=who, whom=whom, seer=json.dumps(seer, ensure_ascii=False, indent=1),
                  seen=json.dumps(seen, ensure_ascii=False, indent=1),
                  context=json.dumps({key: value for key, value in context.items() if value}, ensure_ascii=False,
                                     indent=1))
    allowed = written(cast, seer, seen)

    def shape(raw: dict, final: bool) -> dict:
        found = {'dynamic': text_value(raw.get('dynamic'), 300), 'hidden_tension': text_value(raw.get('hidden_tension'),
                                                                                                300),
                 'trust': trust_value(raw.get('trust'))}
        if not (found['dynamic'] or found['hidden_tension']):
            raise Unusable('"dynamic" and "hidden_tension" were both empty.')
        texts = [('proposal.dynamic', 'Dynamic', found['dynamic']),
                 ('proposal.hidden_tension', 'Hidden tension', found['hidden_tension'])]
        return {'proposal': found, 'audit': audited(texts, allowed, final)}

    return ask(system, shape)


# ---- Routes -------------------------------------------------------------------------------------------------------

class CastBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    cast: dict  # checked by casts.checked, so a broken rule comes back as one plain sentence


class SuggestBody(CastBody):
    target: str = Field(min_length=1, max_length=24)  # 'outer', or the id of the side whose inner square it is


class TurnBody(CastBody):
    a: str = Field(min_length=1, max_length=24)
    b: str = Field(min_length=1, max_length=24)


class RelationshipBody(CastBody):
    model_config = ConfigDict(extra='forbid', populate_by_name=True)
    from_id: str = Field(alias='from', min_length=1, max_length=40)
    to_id: str = Field(alias='to', min_length=1, max_length=40)


router = APIRouter(prefix='/api/cast-ai')


@router.post('/suggest')
def suggest_route(body: SuggestBody):
    return suggest(casts.checked(body.cast), body.target)


@router.post('/check')
def check_route(body: CastBody):
    return check(casts.checked(body.cast))


@router.post('/turn')
def turn_route(body: TurnBody):
    return turn(casts.checked(body.cast), body.a, body.b)


@router.post('/relationship')
def relationship_route(body: RelationshipBody):
    return relationship(casts.checked(body.cast), body.from_id, body.to_id)

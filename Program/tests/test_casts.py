import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from dramatis import casts, library
from dramatis.character import Character
from dramatis.main import create_app


def client() -> TestClient:
    return TestClient(create_app())


def corner(id, label='', stance='', tags=(), **more) -> dict:
    return {'id': id, 'label': label or id.upper(), 'stance': stance or f'stance of {id}', 'tags': list(tags)} | more


def board(**changes) -> dict:
    """The Salt Crown: the Order split four ways on means, the Free split in two, two single sides."""
    order = corner('a', 'The Order', 'stability', depth='full', inner={
        'axis': {'kind': 'means', 'label': 'How to keep order'}, 'question': 'What may order cost its own?',
        'corners': [corner('a1', 'Zealot', 'by purity', ['purity']),
                    corner('a2', 'Pragmatist', 'by compromise', ['negotiation', 'charm']),
                    corner('a3', 'Reformer', 'from within', ['law'])]})
    free = corner('b', 'The Free', 'liberty', depth='partial', inner={
        'axis': {'kind': 'means'}, 'question': 'How free is free enough?',
        'corners': [corner('b1', 'Negotiator', 'by treaty', ['negotiation', 'charm']),
                    corner('b2', 'Militant', 'by force', ['force'])]})
    found = {'title': 'The Salt Crown', 'theme': 'Is order worth what it costs?', 'genre': 'political-fantasy',
             'group': 'movement',
             'outer': {'axis': {'kind': 'value', 'label': 'What the world should be'},
                       'corners': [order, free, corner('c', 'The Faithful', 'divine will', ['faith']),
                                   corner('d', 'The Crown', 'power itself', ['force'])]}}
    return found | changes


def codes(raw: dict) -> list[str]:
    return [found['code'] for found in casts.computed(casts.checked(raw))['checks']]


def made(name: str) -> str:
    return library.save(Character(name=name, about=f'{name}, for the test.'))['id']


# ---- The store ----------------------------------------------------------------------------------------------------

def test_a_cast_is_saved_listed_changed_and_deleted():
    api = client()
    ida = made('Ida Brandt')
    raw = board()
    raw['outer']['corners'][0]['inner']['corners'][0]['character_id'] = ida
    first = api.post('/api/casts', json={'cast': raw}).json()
    assert len(first['id']) == 12 and first['cast'] == casts.dumped(casts.checked(raw))
    assert first['computed']['names'] == {ida: 'Ida Brandt'}
    assert api.get('/api/casts').json() == [{'id': first['id'], 'title': 'The Salt Crown',
                                             'theme': 'Is order worth what it costs?', 'updated': first['updated'],
                                             'characters': 1}]
    changed = api.put(f"/api/casts/{first['id']}", json={'cast': raw | {'title': 'Salt'}}).json()
    assert changed['id'] == first['id'] and changed['created'] == first['created']
    assert api.get(f"/api/casts/{first['id']}").json()['cast']['title'] == 'Salt'
    assert api.delete(f"/api/casts/{first['id']}").json() == {'ok': True}
    assert api.get(f"/api/casts/{first['id']}").status_code == 404
    assert api.get('/api/casts/..%2Fsettings').status_code == 404


def test_relationships_keep_from_and_to_on_disk():
    one, two = made('Ida'), made('Tomas')
    row = {'from': one, 'to': two, 'dynamic': 'Thinks he is soft.', 'trust': 3}
    record = casts.save(casts.checked(board(relationships=[row])))
    assert record['cast']['relationships'][0] == row | {'hidden_tension': '', 'notes': ''}


def test_a_bad_board_comes_back_as_one_plain_sentence():
    raw = board()
    raw['outer']['corners'][2]['id'] = 'a1'
    found = client().post('/api/casts/check', json={'cast': raw})
    assert found.status_code == 422
    assert found.json() == {'error': 'Two corners share the id a1; each corner needs its own.', 'code': 'invalid_cast'}


# ---- Structural rules ---------------------------------------------------------------------------------------------

def broken(change) -> str:
    raw = board()
    change(raw)
    with pytest.raises(Exception) as error:
        casts.checked(raw)
    return error.value.message


def test_each_structural_rule_rejects_bad_input():
    order = lambda raw: raw['outer']['corners'][0]  # noqa: E731
    assert 'needs its own' in broken(lambda raw: order(raw)['inner']['corners'][1].update(id='b2'))
    nested = {'depth': 'partial', 'inner': {'axis': {'kind': 'cost'}, 'corners': [corner('x1'), corner('x2')]}}
    assert 'cannot be split again' in broken(lambda raw: order(raw)['inner']['corners'][0].update(nested))
    assert 'needs no inner square' in broken(lambda raw: order(raw).update(depth='single'))
    assert 'needs an inner square of 2' in broken(lambda raw: order(raw).update(depth='partial'))
    assert 'needs an inner square of 3 or 4' in broken(lambda raw: raw['outer']['corners'][1].update(depth='full'))
    assert 'same thing as the outer square' in broken(lambda raw: order(raw)['inner']['axis'].update(kind='value'))
    assert 'Only the outer square' in broken(lambda raw: order(raw)['inner']['axis'].update(kind='dilemma'))
    assert 'two different characters' in broken(lambda raw: raw.update(relationships=[{'from': 'x1', 'to': 'x1'}]))
    twice = [{'from': 'x1', 'to': 'x2'}, {'from': 'x1', 'to': 'x2', 'trust': 2}]
    assert 'keep one' in broken(lambda raw: raw.update(relationships=twice))
    same_side = [{'a': 'a1', 'b': 'a2', 'on': 'charm', 'status': 'confirmed'}]
    assert 'two different sides' in broken(lambda raw: raw.update(resonance=same_side))
    nowhere = [{'a': 'a1', 'b': 'zz', 'on': 'charm', 'status': 'confirmed'}]
    assert 'not a corner on this board' in broken(lambda raw: raw.update(resonance=nowhere))
    assert 'pattern' in broken(lambda raw: raw['outer']['corners'][2].update(id='Not An Id'))
    assert 'at least 2' in broken(lambda raw: raw['outer'].update(corners=raw['outer']['corners'][:1]))


def test_both_directions_of_a_pair_are_fine():
    rows = [{'from': 'x1', 'to': 'x2'}, {'from': 'x2', 'to': 'x1'}]
    assert len(casts.checked(board(relationships=rows)).relationships) == 2


def test_a_dilemma_outer_square_is_fine():
    raw = board()
    raw['outer']['axis'] = {'kind': 'dilemma', 'label': 'Stay or go?'}
    assert casts.checked(raw).outer.axis.kind == 'dilemma'


# ---- Resonance candidates -----------------------------------------------------------------------------------------

def test_candidates_pair_people_on_different_sides_once_per_tag():
    found = casts.computed(casts.checked(board()))['candidates']
    assert found == [{'a': 'a2', 'b': 'b1', 'on': 'charm'}, {'a': 'a2', 'b': 'b1', 'on': 'negotiation'},
                     {'a': 'b2', 'b': 'd', 'on': 'force'}]


def test_a_side_never_resonates_with_itself_or_its_own_split():
    raw = board()
    raw['outer']['corners'][0]['tags'] = ['purity']  # the Order itself shares a tag with its own Zealot
    raw['outer']['corners'][0]['inner']['corners'][2]['tags'] = ['purity']
    assert all(pair['on'] != 'purity' for pair in casts.computed(casts.checked(raw))['candidates'])


def test_decided_pairs_are_left_out_and_confirmed_links_kept():
    links = [{'a': 'b1', 'b': 'a2', 'on': 'negotiation', 'role': 'defector', 'status': 'confirmed'},
             {'a': 'b2', 'b': 'd', 'on': 'force', 'status': 'dismissed'}]
    cast = casts.checked(board(resonance=links))
    assert casts.computed(cast)['candidates'] == []
    assert casts.dumped(cast)['resonance'][0] == links[0] | {'note': ''}


# ---- Checks -------------------------------------------------------------------------------------------------------

def test_a_finished_board_has_only_reminders():
    raw = board()
    for side in raw['outer']['corners']:
        for found in [side, *(side.get('inner') or {}).get('corners', [])]:
            found['character_id'] = made(found['label'])
    assert codes(raw) == []


def test_no_theme_and_no_theme_tie():
    raw = board(theme='')
    raw['outer']['corners'][1]['inner']['question'] = ''
    checks = casts.computed(casts.checked(raw))['checks']
    assert [found['code'] for found in checks][:2] == ['no-theme', 'no-theme-tie']
    assert checks[1]['corners'] == ['b']
    assert checks[1]['message'] == "The Free's split doesn't say how it asks the theme."


def test_blank_stances_are_named_together():
    raw = board()
    raw['outer']['corners'][2]['stance'] = raw['outer']['corners'][3]['stance'] = ''
    found = next(check for check in casts.computed(casts.checked(raw))['checks'] if check['code'] == 'blank-stance')
    assert found['corners'] == ['c', 'd'] and found['message'] == 'The Faithful and The Crown have no stance yet.'


def test_duplicate_how_by_tags_or_by_words():
    raw = board()
    inner = raw['outer']['corners'][0]['inner']['corners']
    inner[2]['tags'] = ['charm', 'negotiation']
    found = [check for check in casts.computed(casts.checked(raw))['checks'] if check['code'] == 'duplicate-how']
    assert [check['corners'] for check in found] == [['a2', 'a3']]
    assert found[0]['message'] == 'Pragmatist and Reformer fight the same way.'
    inner[2]['tags'], inner[2]['stance'] = ['law'], 'Through Purity!'
    found = [check for check in casts.computed(casts.checked(raw))['checks'] if check['code'] == 'duplicate-how']
    assert [check['corners'] for check in found] == [['a1', 'a3']]


def test_outer_sides_with_one_why_are_flagged_but_shared_tags_are_not():
    raw = board()
    raw['outer']['corners'][3]['stance'] = 'Divine will.'
    assert 'duplicate-why' in codes(raw)
    raw['outer']['corners'][3] |= {'stance': 'power itself', 'tags': ['faith']}
    assert 'duplicate-why' not in codes(raw) and 'duplicate-how' not in codes(raw)


def test_cast_bloat_by_splits_and_by_characters():
    raw = board()
    assert 'cast-bloat' not in codes(raw)
    for side in raw['outer']['corners'][1:3]:
        side |= {'depth': 'full', 'inner': {'axis': {'kind': 'means'}, 'question': 'q',
                                             'corners': [corner(f"{side['id']}{n}") for n in range(1, 4)]}}
    bloat = [found for found in casts.computed(casts.checked(raw))['checks'] if found['code'] == 'cast-bloat']
    assert [found['corners'] for found in bloat] == [['a', 'b', 'c']]

    raw = board()
    people = [found for side in raw['outer']['corners']
              for found in [side, *(side.get('inner') or {}).get('corners', [])]]
    for found in people:
        found['character_id'] = made(found['label'])
    assert len(people) == 9 and 'cast-bloat' not in codes(raw)
    extra = [{'from': people[0]['character_id'], 'to': made(f'P{n}')} for n in range(4)]
    assert 'cast-bloat' not in codes(raw | {'relationships': extra})  # only characters on corners count
    for side in raw['outer']['corners'][2:]:
        pair = [corner(f"{side['id']}{n}", character_id=made(f"{side['label']} {n}")) for n in (1, 2)]
        side |= {'depth': 'partial', 'inner': {'axis': {'kind': 'means'}, 'question': 'q', 'corners': pair}}
    assert len(casts.linked(casts.checked(raw))) == 13
    bloat = [found for found in casts.computed(casts.checked(raw))['checks'] if found['code'] == 'cast-bloat']
    assert len(bloat) == 1 and bloat[0]['message'].startswith('13 characters are linked')


def test_missing_characters_on_corners_and_relationships():
    gone, here = made('Gone'), made('Here')
    raw = board(relationships=[{'from': here, 'to': gone}])
    raw['outer']['corners'][2]['character_id'] = gone
    library.delete(gone)
    found = [check for check in casts.computed(casts.checked(raw))['checks'] if check['code'] == 'missing-character']
    assert [check['corners'] for check in found] == [['c'], []]
    assert found[0]['message'] == "The Faithful's character is no longer in the library."
    assert casts.computed(casts.checked(raw))['names'] == {here: 'Here'}


def test_unlinked_names_people_but_not_split_sides():
    found = next(check for check in casts.computed(casts.checked(board()))['checks'] if check['code'] == 'unlinked')
    assert found['severity'] == 'info' and found['corners'] == ['a1', 'a2', 'a3', 'b1', 'b2', 'c', 'd']


def test_mystery_reminds_that_secrets_should_differ():
    raw = board(genre='mystery')
    raw['outer']['corners'][1]['inner']['axis']['kind'] = 'secret'
    found = next(check for check in casts.computed(casts.checked(raw))['checks'] if check['code'] == 'secret-differs')
    assert found['corners'] == ['b'] and found['severity'] == 'info'
    assert 'secret-differs' not in codes(board())


# ---- The banks and the web template -------------------------------------------------------------------------------

def from_genre(template: dict) -> dict:
    """A board as a genre starts it: its outer labels and roles, and its split side split with its group's roles."""
    groups = {group['id']: group for group in casts.bank('groups')}
    sides = []
    for index, side in enumerate(template['outer']):
        found = {'id': 'abcd'[index], 'label': side['label'], 'role': side.get('role', ''),
                 'fields': {field: 'Something real.' for field in side.get('fields', [])}}
        if index == template['split']:
            roles = groups[template['group']]['roles']
            found |= {'depth': 'full', 'inner': {'axis': {'kind': template['axis']}, 'corners': [
                {'id': f'{found["id"]}{n}', 'label': role.capitalize(), 'role': role} for n, role in enumerate(roles)]}}
        sides.append(found)
    return {'genre': template['id'], 'group': template['group'],
            'outer': {'axis': {'kind': template['outer_axis'], 'label': 'Stay or go?'}, 'corners': sides}}


def test_every_genre_starts_a_valid_board_and_names_a_real_group():
    banks = client().get('/api/cast-templates').json()
    assert set(banks) == {'axes', 'genres', 'groups', 'tags'}
    kinds = {axis['kind'] for axis in banks['axes']}
    assert kinds == set(casts.AxisKind.__args__) and len(banks['groups']) == 6 and len(banks['tags']) >= 40
    assert len(banks['genres']) == 18 and len({genre['id'] for genre in banks['genres']}) == 18
    groups = {group['id'] for group in banks['groups']}
    for genre in banks['genres']:
        assert genre['axis'] in kinds and (genre['group'] in groups or genre['id'] == 'four-corner-web')
        assert all(code in casts.REMINDERS or code == 'role-fields' for code in genre['checks'])
        assert casts.checked(from_genre(genre)).genre == genre['id']


def test_the_web_template_validates_and_asks_for_its_fields():
    web = casts.genre('four-corner-web')
    raw = from_genre(web)
    cast = casts.checked(raw)
    assert cast.outer.axis.kind == 'dilemma' and [side.role for side in cast.outer.corners] == [
        'main', 'challenger', 'comforter', 'warning']
    checks = casts.computed(cast)['checks']
    reminders = [found['code'] for found in checks if found['severity'] == 'info' and found['code'] != 'unlinked']
    assert reminders == ['challenger-has-flaw', 'comforter-not-villain', 'warning-sympathetic']
    raw['outer']['corners'][0]['fields']['what_it_costs'] = ''
    found = next(check for check in casts.computed(casts.checked(raw))['checks'] if check['code'] == 'role-fields')
    assert found['corners'] == ['a'] and found['message'] == 'Main has nothing yet for what it costs.'


# ---- Exports ------------------------------------------------------------------------------------------------------

def test_the_export_bundle_skips_a_deleted_character():
    api = client()
    kept, gone = made('Ida Brandt'), made('Gone')
    raw = board(relationships=[{'from': kept, 'to': gone}], focus_id=kept)
    raw['outer']['corners'][2]['character_id'] = kept
    record = api.post('/api/casts', json={'cast': raw}).json()
    library.delete(gone)
    found = api.get(f"/api/casts/{record['id']}/cast.json")
    assert found.headers['content-disposition'] == 'attachment; filename="The Salt Crown.json"'
    bundle = found.json()
    assert bundle['format'] == 'prospero-cast' and bundle['version'] == 1
    assert bundle['cast'] == record['cast'] and list(bundle['characters']) == [kept]
    assert bundle['characters'][kept]['name'] == 'Ida Brandt'


def test_each_character_exports_as_their_own_card():
    api = client()
    first, second, gone = made('Ida Brandt'), made('Ida Brandt'), made('Gone')
    raw = board()
    for found, character_id in zip(raw['outer']['corners'][1]['inner']['corners'] + raw['outer']['corners'][2:],
                                   (first, second, gone)):
        found['character_id'] = character_id
    record = api.post('/api/casts', json={'cast': raw}).json()
    library.delete(gone)

    found = api.get(f"/api/casts/{record['id']}/cards.zip", params={'for': 'chat', 'kind': 'json'})
    assert found.headers['content-disposition'] == 'attachment; filename="The Salt Crown cards.zip"'
    archive = zipfile.ZipFile(io.BytesIO(found.content))
    assert archive.namelist() == ['Ida Brandt.json', 'Ida Brandt 2.json']
    card = json.loads(archive.read('Ida Brandt.json'))
    assert card['spec'] == 'chara_card_v3' and card['data']['extensions'] == {}

    pngs = zipfile.ZipFile(io.BytesIO(api.get(f"/api/casts/{record['id']}/cards.zip").content))
    assert pngs.namelist() == ['Ida Brandt.png', 'Ida Brandt 2.png']
    assert pngs.read('Ida Brandt.png').startswith(b'\x89PNG')

    empty = api.post('/api/casts', json={'cast': board()}).json()
    missing = api.get(f"/api/casts/{empty['id']}/cards.zip")
    assert missing.status_code == 404 and missing.json()['error'] == 'No character in this cast is in the library yet.'

"""Writes the screen's copy of the character: its TypeScript types from the Pydantic models (dramatis/character.py) to
src/generated/character.ts, and the field registry (dramatis/fields.py) to src/generated/fields.ts. Run it after
changing either, from Program/:

    python scripts/screen_types.py

`--check` writes nothing and fails when a file is out of date; tests/test_screen_types.py runs it, so CI does too.
"""
import json
import sys
import types
import typing
from pathlib import Path

from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dramatis import character, fields  # noqa: E402
from dramatis.formats.companion import models as companion  # noqa: E402

OUT = ROOT / 'src' / 'generated'
HEAD = '// Written by scripts/screen_types.py from {source}. Do not edit: change {source} and run it again.\n'
# Named unions, so the screen can use them by name.
NAMED = {character.App: 'App', character.Gender: 'Gender', character.Trait: 'Trait',
         character.Relationship: 'Relationship', character.LooksField: 'LooksField', companion.BlockKind: 'BlockKind'}
RENAMED = {companion.RoutineBlock: 'Block'}
# A field the model keeps looser than it checks it: the week is checked block by block with Companion's RoutineBlock.
SIMPLE = {str: 'string', int: 'number', float: 'number', bool: 'boolean', type(None): 'null', typing.Any: 'unknown'}
OVERRIDES = {('CompanionLife', 'schedule'): (companion.RoutineBlock, 'Block[]')}


def quote(value) -> str:
    """A value as the screen writes it: single quotes, unless the text has one."""
    text = json.dumps(value, ensure_ascii=False)
    if isinstance(value, str) and "'" not in value:
        return "'" + text[1:-1].replace('\\"', '"') + "'"
    return text


def model_name(model: type[BaseModel]) -> str:
    return RENAMED.get(model, model.__name__)


class Writer:
    def __init__(self):
        self.models: list[type[BaseModel]] = []

    def model(self, model: type[BaseModel]) -> str:
        if model not in self.models:
            self.models.append(model)
        return model_name(model)

    def ts(self, annotation) -> str:
        for named, name in NAMED.items():
            if annotation == named:
                return name
        origin, args = typing.get_origin(annotation), typing.get_args(annotation)
        if origin is typing.Literal:
            return ' | '.join(quote(arg) for arg in args)
        if origin in (typing.Annotated, typing.Union, types.UnionType, list):
            return self.compound(origin, args)
        if origin is dict or annotation is dict:
            return self.record(args)
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            return self.model(annotation)
        if annotation in SIMPLE:
            return SIMPLE[annotation]
        raise TypeError(f'No TypeScript for {annotation!r}.')

    def compound(self, origin, args) -> str:
        if origin is typing.Annotated:
            return self.ts(args[0])
        if origin is list:
            inner = self.ts(args[0])
            return f'({inner})[]' if ' | ' in inner else f'{inner}[]'
        return ' | '.join(self.ts(arg) for arg in args)

    def record(self, args) -> str:
        if not args:
            return 'Record<string, unknown>'
        key, value = self.ts(args[0]), self.ts(args[1])
        return f'Partial<Record<{key}, {value}>>' if key != 'string' else f'Record<string, {value}>'

    def interface(self, model: type[BaseModel]) -> str:
        lines = []
        doc = model.__dict__.get('__doc__')
        if doc:
            lines.append('/** ' + ' '.join(doc.split()) + ' */')
        lines.append(f'export interface {model_name(model)} {{')
        for name, info in model.model_fields.items():
            override = OVERRIDES.get((model.__name__, name))
            if override:
                self.model(override[0])
                kind = override[1]
            else:
                kind = self.ts(info.annotation)
            lines.append(f'  {info.alias or name}: {kind}')
        lines.append('}')
        return '\n'.join(lines)

    def module(self, root: type[BaseModel]) -> str:
        self.model(root)
        written, done = [], 0
        while done < len(self.models):
            written.append(self.interface(self.models[done]))
            done += 1
        unions = [f'export type {name} = {" | ".join(quote(arg) for arg in typing.get_args(named))}'
                  for named, name in NAMED.items()]
        return HEAD.format(source='dramatis/character.py') + '\n' + '\n'.join(unions) + '\n\n' + \
            '\n\n'.join(written) + '\n'


def fields_module() -> str:
    table = fields.table()
    keys = ' | '.join(quote(key) for key in table)
    rows = ',\n'.join(f'  {quote(key)}: {{ ' + ', '.join(f'{name}: {quote(value)}' for name, value in spec.items()) + ' }'
                      for key, spec in table.items())
    return (HEAD.format(source='dramatis/fields.py') + '\n'
            '/** One field of the form: what the form calls it, its section, its limits (`limit` for a text or each item '
            'of a list,\n * `count` for a list) and the words its Help me write bolt and Add box use. */\n'
            'export interface FieldSpec { label: string; section: string; limit?: number; count?: number; write?: string;'
            ' add?: string }\n'
            f'export type FieldKey = {keys}\n\n'
            f'export const FIELDS: Record<FieldKey, FieldSpec> = {{\n{rows},\n}}\n')


def files() -> dict[Path, str]:
    return {OUT / 'character.ts': Writer().module(character.Character), OUT / 'fields.ts': fields_module()}


def main(argv: list[str]) -> int:
    stale = [path for path, text in files().items()
             if not path.is_file() or path.read_text(encoding='utf-8') != text]
    if '--check' in argv:
        for path in stale:
            print(f'{path.relative_to(ROOT)} is out of date: run python scripts/screen_types.py', file=sys.stderr)
        return 1 if stale else 0
    OUT.mkdir(exist_ok=True)
    for path, text in files().items():
        path.write_text(text, encoding='utf-8', newline='\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

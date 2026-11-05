"""Copy the suite's character formats into dramatis/formats: `python scripts/sync_format.py --companion PATH
--adventure PATH --dungeon PATH` (each a checkout of that app; leave one out to keep its copy as it is).

Dramatis makes characters that Prospero's Companion, Adventure and Dungeon load unchanged, so it checks them with each
app's own request models rather than a rewrite, reads character files with Companion's own importer, rolls
personality sliders with the apps' own slider code and words, draws portraits with Companion's own image adapters
(ComfyUI, the Codex CLI and hosted image APIs), and drafts through Companion's own text model providers (hosted APIs,
local servers, Claude Code and Codex). This script copies those files from each checkout, points their imports at the
vendored copies (or at Dramatis' stand-ins for the few modules that would pull in a whole app), and stamps
formats/SOURCE.json with the commit each came from.

`--check` changes nothing and exits 1 when the vendored files differ from the checkouts' (CI runs it against each
app's latest main to catch drift).
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
TARGET = HERE / 'dramatis' / 'formats'
SOURCE_FILE = 'SOURCE.json'

# Companion's image adapters (their own import closure) and the ComfyUI workflows its families use.
IMAGE_MODULES = ('tags', 'node_packs', 'adapters/base', 'adapters/hosted', 'adapters/novelai', 'adapters/comfyui',
                 'adapters/codex')
# Companion's text model providers (its whole Settings > Models connection layer, without its profile database):
# hosted APIs, local and OpenAI-compatible servers, Kobold, and the Claude Code and Codex command lines.
PROVIDER_MODULES = ('urls', 'config', 'capabilities', 'requests', 'events', 'chat', 'claude_code', 'codex',
                    'cli_accounts', 'discovery', 'discovery_errors', 'efforts', 'balance', 'prompt_cache', 'vault')
WORKFLOWS = tuple(f'{family}{kind}' for family in ('krea2-turbo', 'qwen-image-2.1', 'z-image-turbo', 'anima',
                                                   'booru-sdxl') for kind in ('', '-reference'))
# Per app: its repository, its Python package, the files to vendor (checkout path -> vendored name), the data files
# copied as they are, and where each module it imports comes from in Dramatis.
APPS = {
    'companion': {
        'repo': 'vantaloomin/prosperos-companion',
        'files': {
            'Program/companion/errors.py': 'errors.py',
            'Program/companion/models.py': 'models.py',
            # Companion's character importer (Character Cards V1 to V3 as JSON or PNG, CHARX, Backyard Archive,
            # Marinara Engine, Pygmalion and Backyard / Faraday JSON, and the lorebooks they carry), kept at the same
            # paths under imports/ as in Companion.
            'Program/companion/imports/cards.py': 'imports/cards.py',
            'Program/companion/imports/formats.py': 'imports/formats.py',
            'Program/companion/imports/lorebooks.py': 'imports/lorebooks.py',
            'Program/companion/world/personality.py': 'personality.py',
            # Companion's looks sheet and the Matchlight looks it draws from, so the Details fields a draft rolls are
            # the ones Companion would roll for them (dramatis/looks.py).
            'Program/companion/world/looks.py': 'looks.py',
            'Program/companion/world/dating.py': 'dating.py',
            # Companion's text model providers, for every draft (dramatis/ai.py).
            **{f'Program/companion/providers/{name}.py': f'providers/{name}.py' for name in PROVIDER_MODULES},
            # Companion's image makers, for portraits (dramatis/images.py): kept at the same paths under images/,
            # so the ComfyUI adapter finds the workflows beside it as it does in Companion.
            **{f'Program/companion/images/{name}.py': f'images/{name}.py' for name in IMAGE_MODULES},
        },
        'data': {'Program/companion/world/data/personality.json': 'data/personality.json',
                 'Program/companion/world/data/looks.json': 'data/looks.json',
                 **{f'Program/companion/images/workflows/{name}.json': f'images/workflows/{name}.json'
                    for name in WORKFLOWS}},
        'modules': {
            'companion.errors': 'dramatis.formats.companion.errors',
            **{f'companion.imports.{name}': f'dramatis.formats.companion.imports.{name}'
               for name in ('cards', 'formats', 'lorebooks')},
            # personality.py reads its words through catalog.DATA and rolls with generators.unit; models.py checks
            # the adult side's own words with intimacy.allowed. Each would pull in most of Companion.
            'companion.world.catalog': 'dramatis.stand_ins.catalog',
            'companion.world.generators': 'dramatis.stand_ins.generators',
            'companion.world.intimacy': 'dramatis.stand_ins.intimacy',
            'companion.world.dating': 'dramatis.formats.companion.dating',
            # dating.py reads the world's mix of heights and builds, the town's eras and how long each kind lives;
            # Dramatis has no world, so these give Companion's built-in ones.
            'companion.world.lifespans': 'dramatis.stand_ins.lifespans',
            'companion.world.mix': 'dramatis.stand_ins.mix',
            'companion.world.townsfolk': 'dramatis.stand_ins.townsfolk',
            'companion.models': 'dramatis.formats.companion.models',
            **{f'companion.providers.{name}': f'dramatis.formats.companion.providers.{name}' for name in PROVIDER_MODULES},
            # chat.py asks the built-in model's server where it runs (Companion downloads and runs one), and the
            # key vault is named after the app: Dramatis has neither of Companion's, so these stand in.
            'companion.providers.builtin_chat': 'dramatis.stand_ins.builtin_chat',
            'companion.identity': 'dramatis.stand_ins.identity',
            **{f"companion.images.{name.replace('/', '.')}": f"dramatis.formats.companion.images.{name.replace('/', '.')}"
               for name in IMAGE_MODULES},
        },
    },
    'adventure': {
        'repo': 'vantaloomin/prosperos-adventure',
        'files': {'Program/adventure/models.py': 'models.py'},
        'data': {},
        'modules': {},
    },
    'dungeon': {
        'repo': 'vantaloomin/prosperos-dungeon',
        'files': {'Program/dungeon/models.py': 'models.py'},
        'data': {},
        'modules': {},
    },
}
IMPORT = re.compile(r'^(?P<indent>[ \t]*)from (?P<module>(?:companion|adventure|dungeon)(?:\.\w+)*) import (?P<names>.+)$',
                    re.M)
HEADER = '# Vendored from {repo} {path} by scripts/sync_format.py. Edit it there, then sync.\n'


def swap(match: re.Match, modules: dict[str, str], path: str) -> str:
    """One `from <app module> import ...` line pointed at Dramatis' copy or stand-in.

    `from companion.errors import DomainError` takes the module's own place; `from companion.world import catalog,
    dating` takes the package of each module it names, one line for each place they live in Dramatis."""
    module, names, indent = match['module'], match['names'], match['indent']
    if module in modules:
        return f'{indent}from {modules[module]} import {names}'
    wanted = [name.strip() for name in names.strip('()').split(',') if name.strip()]
    places: dict[str, list[str]] = {}
    for name in wanted:
        target = modules.get(f"{module}.{name.split(' as ')[0].strip()}", '').rpartition('.')[0]
        if not target:
            raise SystemExit(f'{path} imports {name} from {module}, which is not vendored. Add it to APPS.')
        places.setdefault(target, []).append(name)
    if len(places) == 1:
        return f'{indent}from {next(iter(places))} import {names}'
    return '\n'.join(f"{indent}from {target} import {', '.join(found)}" for target, found in places.items())


def vendored(text: str, path: str, app: dict) -> str:
    return HEADER.format(repo=app['repo'], path=path) + IMPORT.sub(lambda match: swap(match, app['modules'], path), text)


def commit_of(checkout: Path) -> str:
    try:
        return subprocess.run(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return 'unknown'


def read(checkout: Path, source: str) -> str:
    path = checkout / source
    if not path.is_file():
        raise SystemExit(f'{path} is missing. Is {checkout} the right checkout?')
    return path.read_text(encoding='utf-8')


def wanted(name: str, checkout: Path) -> dict[str, str]:
    """Each vendored file of one app as its copy should read, by its path under formats/<app>."""
    app = APPS[name]
    found = {target: vendored(read(checkout, source), source, app) for source, target in app['files'].items()}
    found |= {target: read(checkout, source) for source, target in app['data'].items()}
    return found


def differences(found: dict[str, str], folder: Path) -> list[str]:
    return [name for name, text in found.items()
            if not (folder / name).is_file() or (folder / name).read_text(encoding='utf-8') != text]


def stamp(target: Path, name: str, commit: str):
    path = target / SOURCE_FILE
    sources = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    app = APPS[name]
    sources[name] = {'repo': app['repo'], 'commit': commit, 'files': {**app['files'], **app['data']}}
    path.write_text(json.dumps(dict(sorted(sources.items())), indent=2) + '\n', encoding='utf-8')


def main(argv: list[str] | None = None, target: Path = TARGET) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for name in APPS:
        parser.add_argument(f'--{name}', type=Path, metavar='CHECKOUT', help=f'a {APPS[name]["repo"]} checkout')
    parser.add_argument('--check', action='store_true', help='report drift and change nothing')
    args = parser.parse_args(argv)
    chosen = {name: getattr(args, name) for name in APPS if getattr(args, name)}
    if not chosen:
        parser.error('Give at least one checkout.')
    drifted = []
    for name, checkout in chosen.items():
        found, folder = wanted(name, checkout), target / name
        changed = differences(found, folder)
        if args.check:
            drifted += [f'{name}/{file}' for file in changed]
            continue
        for file, text in found.items():
            (folder / file).parent.mkdir(parents=True, exist_ok=True)
            (folder / file).write_text(text, encoding='utf-8')
        (folder / '__init__.py').write_text(f'"""{APPS[name]["repo"]}\'s character format, vendored."""\n',
                                            encoding='utf-8')
        for package in {(folder / file).parent for file in found if file.endswith('.py')} - {folder}:
            (package / '__init__.py').write_text('', encoding='utf-8')
        stamp(target, name, commit_of(checkout))
        print(f'{name}: ' + (f"updated {', '.join(changed)}" if changed else 'already up to date'))
    if drifted:
        print('These vendored files differ from the apps: ' + ', '.join(drifted), file=sys.stderr)
        print('Run scripts/sync_format.py with those checkouts, then run the tests.', file=sys.stderr)
        return 1
    if args.check:
        print('The vendored formats match.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

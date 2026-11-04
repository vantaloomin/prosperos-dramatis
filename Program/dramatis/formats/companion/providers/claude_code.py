# Vendored from vantaloomin/prosperos-companion Program/companion/providers/claude_code.py by scripts/sync_format.py. Edit it there, then sync.
"""Text replies through the installed Claude Code CLI (`claude -p`) and the user's own Claude plan login.

The app runs the official, unmodified `claude` program the user installed and signed in to themselves, the
same way the Codex provider runs `codex exec`. It never reads, copies, stores, logs or forwards the login
(no credential files, tokens or sign-in flow of its own): the CLI handles all of that. If the CLI is not
signed in, Test connection says to run `claude` once in a terminal.

Each reply is one `claude -p` turn in an empty temporary folder: the system prompt from a file in that
folder, the conversation as one transcript on stdin, every tool off, no MCP servers, no skills or slash
commands, nothing saved as a session. `--bare` is never passed, because bare mode ignores the plan login.
ANTHROPIC_API_KEY is left out of the CLI's environment so a key set for the Anthropic provider never
silently takes the place of the plan.

A profile can name its own account folder, so two Claude accounts can each have a profile: the CLI keeps each
account's sign-in in its folder (CLAUDE_CONFIG_DIR). The user signs in to it once in a terminal with that
variable set; the app only passes the folder on (companion/providers/cli_accounts.py finds the folders a `claude2`
command sets). With a folder set, a sign-in token from the environment (CLAUDE_CODE_OAUTH_TOKEN) is left out,
since it would win over the folder's account.

Claude follows Anthropic's usage policy, so this profile suits the non-explicit jobs only.
"""
import asyncio
import json
import os
import shutil
import tempfile
from pathlib import Path

from dramatis.formats.companion.errors import DomainError, require
from dramatis.formats.companion.providers.events import Chunk
from dramatis.formats.companion.providers.requests import transcript

# Claude Code has no command that lists models; its aliases always point at the newest model of each family.
# A plan may not include all of them; access is checked when a message is sent.
MODELS = (('sonnet', 'Sonnet (newest)'), ('opus', 'Opus (newest)'), ('haiku', 'Haiku (newest)'),
          ('fable', 'Fable (newest)'))
EFFORTS = ('low', 'medium', 'high', 'xhigh', 'max')
LOGIN_STEP = 'Claude Code is not signed in. Run claude once in a terminal on this computer and sign in with ' \
             'your Claude account, then test again.'
# Words the CLI uses when its login is missing or expired.
AUTH_SIGNS = ('/login', 'not logged in', 'authenticat', 'oauth', 'invalid api key')
# Kept out of the CLI's environment so it uses the plan login, not an API key.
DROPPED_ENV = ('ANTHROPIC_API_KEY',)


def executable_path(config: dict) -> str:
    """The profile's CLI location, else `claude` on PATH, else the native installer's usual place."""
    if location := (config.get('cli_path') or '').strip():
        require(Path(location).is_file(), 'Claude Code was not found at the location set in this profile.', 409)
        return location
    native = Path.home() / '.local' / 'bin' / ('claude.exe' if os.name == 'nt' else 'claude')
    executable = shutil.which('claude') or (str(native) if native.is_file() else None)
    require(bool(executable), 'Claude Code was not found. Install it from claude.com/claude-code, sign in by '
            'running claude once in a terminal, or enter its full location in this profile.', 409)
    return executable


def account_dir(config: dict | None) -> str:
    return ((config or {}).get('cli_account_dir') or '').strip()


def cli_environment(config: dict | None = None) -> dict:
    """The user's own environment, less what would replace the plan login, with the profile's account folder when
    it names one."""
    environment = {name: value for name, value in os.environ.items() if name not in DROPPED_ENV}
    if folder := account_dir(config):
        environment.pop('CLAUDE_CODE_OAUTH_TOKEN', None)
        environment['CLAUDE_CONFIG_DIR'] = folder
    return environment


def login_step(config: dict | None = None) -> str:
    """How to sign in: plain `claude` for the usual account, with the folder set for a profile's own account."""
    folder = account_dir(config)
    if not folder:
        return LOGIN_STEP
    command = f'$env:CLAUDE_CONFIG_DIR="{folder}"; claude' if os.name == 'nt' else f'CLAUDE_CONFIG_DIR="{folder}" claude'
    return (f'The Claude account for this profile is not signed in. In a terminal on this computer run {command} '
            'and sign in with that account, then test again.')


def claude_arguments(executable: str, config: dict, system_file: str) -> list[str]:
    arguments = [executable, '-p', '--output-format', 'stream-json', '--verbose', '--include-partial-messages',
                 '--model', config['model'], '--system-prompt-file', system_file, '--tools', '',
                 '--strict-mcp-config', '--disable-slash-commands', '--no-session-persistence']
    if config.get('reasoning_effort'):
        arguments.extend(['--effort', config['reasoning_effort']])
    return arguments


def conversation(messages: list[dict]) -> str:
    """The turns as one transcript; the system prompt travels separately, in its own file."""
    return transcript('', messages).lstrip()


def failure(text: str, config: dict | None = None) -> DomainError:
    if any(sign in text.lower() for sign in AUTH_SIGNS):
        return DomainError(login_step(config), 409, 'provider')
    return DomainError('Claude Code could not complete the request. Check its login, the model and that your '
                       'plan includes it.', 502, 'provider')


def claude_event(data: dict, config: dict | None = None) -> Chunk:
    kind = data.get('type')
    if kind == 'stream_event':
        event = data.get('event') or {}
        delta = event.get('delta') or {}
        if event.get('type') == 'content_block_delta' and delta.get('type') == 'text_delta':
            return Chunk(delta.get('text', ''))
        return Chunk()
    if kind == 'result':
        if data.get('is_error') or data.get('subtype') != 'success':
            raise failure(str(data.get('result') or ''), config)
        return Chunk(str(data.get('result') or ''), 'stop', done=True, usage=dict(data.get('usage') or {}))
    return Chunk()


async def claude_output(process, config: dict | None = None):
    """Text streams as it is written; the closing result carries usage, and the whole reply for a CLI that
    did not stream it."""
    streamed = False
    completed = False
    async for line in process.stdout:
        if not line.strip():
            continue
        event = claude_event(json.loads(line), config)
        if event.done:
            completed = True
            yield Chunk('' if streamed else event.text, 'stop', done=True, usage=event.usage)
        elif event.text:
            streamed = True
            yield event
    require(await process.wait() == 0 and completed,
            'Claude Code exited before completing the response. Check its login and model.', 502)


async def login_state(executable: str, config: dict | None = None) -> dict:
    """`claude auth status`: only whether the CLI is signed in, how, and to which account's email when it says,
    so two profiles' accounts can be told apart. Nothing else from it is kept."""
    process = await asyncio.create_subprocess_exec(executable, 'auth', 'status', '--json',
                                                   stdout=asyncio.subprocess.PIPE,
                                                   stderr=asyncio.subprocess.DEVNULL, env=cli_environment(config))
    try:
        output, _ = await asyncio.wait_for(process.communicate(), 20)
    except TimeoutError as error:
        process.kill()
        await process.wait()
        raise DomainError('The Claude Code login check timed out.', 504) from error
    try:
        status = json.loads(output or b'{}')
    except ValueError:
        status = {}
    status = status if isinstance(status, dict) else {}
    signed_in = process.returncode == 0 and status.get('loggedIn', True) is not False
    require(signed_in, login_step(config), 409)
    return {'method': str(status.get('authMethod') or ''), 'email': str(status.get('email') or '')}


class ClaudeCodeProvider:
    async def stream(self, config: dict, _key: str | None, system: str, messages: list[dict]):
        executable = executable_path(config)
        with tempfile.TemporaryDirectory(prefix='companion-claude-') as directory:
            system_file = Path(directory) / 'system.txt'
            system_file.write_text(system, encoding='utf-8')
            process = await asyncio.create_subprocess_exec(
                *claude_arguments(executable, config, str(system_file)), stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, cwd=directory,
                env=cli_environment(config), limit=2_000_000)
            try:
                async with asyncio.timeout(config['timeout_seconds']):
                    process.stdin.write(conversation(messages).encode('utf-8'))
                    await process.stdin.drain()
                    process.stdin.close()
                    async for event in claude_output(process, config):
                        yield event
            except TimeoutError as error:
                raise DomainError('Claude Code reached the configured time limit.', 504, 'timeout') from error
            except (ValueError, KeyError, AttributeError) as error:
                raise DomainError('This Claude Code output format was not recognized.', 502) from error
            finally:
                if process.returncode is None:
                    process.kill()
                    await process.wait()

    async def check(self, config: dict, _key: str | None) -> dict:
        executable = executable_path(config)
        state = await login_state(executable, config)
        models = [{'id': model, 'name': name, 'context_tokens': None, 'max_output_tokens': None,
                   'limit_source': 'unreported', 'supported_efforts': list(EFFORTS)} for model, name in MODELS]
        account = f' as {state["email"]}' if state['email'] else ''
        note = f'Claude Code is signed in{account}. These names always use the newest model of each family; your plan ' \
               'may not include all of them.'
        if 'api' in state['method'].lower():
            note += ' Claude Code is signed in with an API key, so replies are billed to that key, not your plan.'
        return {'available': True, 'models': [model['id'] for model in models], 'model_details': models,
                'generated': False, 'note': note, 'location': executable}

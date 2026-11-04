"""Drawing portraits with the image maker the user chose, through Prospero's Companion's own image adapters (vendored
in dramatis/formats/companion/images by scripts/sync_format.py), so a maker set up in Companion works here the same
way:

- **ComfyUI** on this computer or one the user runs, with one of Companion's model families and its built-in
  workflow (Krea 2 by default; Qwen Image 2.1, Z-Image Turbo, Anima, or Booru for SDXL checkpoints). The model file can
  be named; empty means the family's own.
- **Codex**: the `codex` command line under the user's ChatGPT sign-in.
- **An image API** with the user's key: the OpenAI API, OpenRouter, Google, NanoGPT, NovelAI, or any other
  OpenAI-style one.

Off until the user sets one up. The key is kept in the system keyring, like the text model's (dramatis/ai.py), never in
the settings file. A picture comes back as the bytes the maker sent; `card_picture` turns it into the PNG a card is
made from, cropped to 2:3 and shrunk to the card's picture size. Nothing here saves.
"""
import asyncio
import io
import secrets
import tempfile
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from dramatis import ai, settings
from dramatis.cards import PLAIN_SIZE
from dramatis.formats.companion.errors import DomainError, require
from dramatis.formats.companion.images.adapters.base import AdapterError, ImageRequest, size_for
from dramatis.formats.companion.images.adapters.codex import CodexAdapter
from dramatis.formats.companion.images.adapters.comfyui import DEFAULT_FAMILY, FAMILIES, ComfyAdapter, model_file
from dramatis.formats.companion.images.adapters.hosted import HostedAdapter, api_base
from dramatis.formats.companion.providers.urls import validate_compatible_url

KINDS = ('off', 'comfyui', 'codex', 'hosted')
KEY_NAME = 'image-api'
# Companion's hosted image APIs, as its images/backends.py HOSTED_DEFAULTS has them (that module reads Companion's
# database, so it is not vendored): the usual address and the request shape the adapter uses for each.
HOSTED = {
    'openai': {'label': 'OpenAI API', 'base_url': 'https://api.openai.com/v1', 'api_style': 'images'},
    'openrouter': {'label': 'OpenRouter', 'base_url': 'https://openrouter.ai/api/v1', 'api_style': 'chat'},
    'google': {'label': 'Google', 'base_url': 'https://generativelanguage.googleapis.com/v1beta/openai',
               'api_style': 'images'},
    'nanogpt': {'label': 'NanoGPT', 'base_url': 'https://nano-gpt.com/api/v1', 'api_style': 'images'},
    'novelai': {'label': 'NovelAI', 'base_url': 'https://image.novelai.net', 'api_style': 'novelai'},
    'other': {'label': 'Another image API', 'base_url': '', 'api_style': 'images'},
}
COMFYUI_ADDRESS = 'http://127.0.0.1:8188'
# What the picture should leave out: Companion's own list, and for a local ComfyUI, which has no content rules of its
# own, anything unsafe besides. A hosted API reads the negative as "Avoid: ..." and has its own rules.
NEGATIVE = 'text, watermark, logo, blurry, distorted hands, extra limbs, duplicate person'
LOCAL_NEGATIVE = f'{NEGATIVE}, nude, nsfw, sexual, child'
STATUS = {'auth': 401, 'refused': 422, 'incompatible': 422, 'rate_limited': 429, 'timeout': 504}
# The frame is cropped a little above the middle, where a waist-up portrait's face is.
CENTRE = (0.5, 0.35)


def saved() -> dict:
    found = settings.load().get('image') or {}
    kind = found.get('kind') if found.get('kind') in KINDS else 'off'
    provider = found.get('provider') if found.get('provider') in HOSTED else 'openai'
    family = found.get('family') if found.get('family') in FAMILIES else DEFAULT_FAMILY
    return {'kind': kind, 'provider': provider, 'family': family, 'base_url': found.get('base_url') or '',
            'model': found.get('model') or ''}


def config() -> dict:
    """The image settings as the screen shows them, whether portraits can be made with them, and the choices."""
    chosen = saved()
    ready = chosen['kind'] == 'codex' or (chosen['kind'] == 'comfyui' and bool(chosen['base_url'])) or \
        (chosen['kind'] == 'hosted' and bool(chosen['base_url']) and bool(ai.api_key(KEY_NAME)))
    return chosen | {'has_key': bool(ai.api_key(KEY_NAME)), 'ready': ready,
                     'families': {key: family.label for key, family in FAMILIES.items()},
                     'providers': {key: {'label': value['label'], 'base_url': value['base_url']}
                                   for key, value in HOSTED.items()}}


def configure(kind: str, provider: str = '', base_url: str = '', model: str = '', family: str = '',
              key: str | None = None) -> dict:
    require(kind in KINDS, 'Pick ComfyUI, Codex, an image API, or no image maker.', 422)
    base_url = api_base(base_url) if kind == 'hosted' else base_url.strip().rstrip('/')
    if kind == 'hosted':
        require(provider in HOSTED, 'Pick which image API.', 422)
        base_url = base_url or HOSTED[provider]['base_url']
        require(bool(base_url), 'This image API needs its address.', 422)
        validate_compatible_url(base_url)
    if kind == 'comfyui':
        require(family in FAMILIES, 'Pick the kind of model ComfyUI draws with.', 422)
        base_url = base_url or COMFYUI_ADDRESS
        require(base_url.startswith(('http://', 'https://')), f'ComfyUI needs its address, like {COMFYUI_ADDRESS}.',
                422)
    if key is not None:
        ai.store_key(KEY_NAME, key)
    settings.save({'image': {'kind': kind, 'provider': provider if kind == 'hosted' else '',
                             'family': family if kind == 'comfyui' else '',
                             'base_url': base_url if kind in ('comfyui', 'hosted') else '', 'model': model.strip()}})
    return config()


def backend() -> tuple[dict, dict]:
    """The backend and config Companion's adapters take, from Dramatis' settings."""
    chosen = saved()
    if chosen['kind'] == 'comfyui':
        config = {'base_url': chosen['base_url'], 'family': chosen['family']}
        if chosen['model']:
            files = FAMILIES[chosen['family']].files
            config['ckpt_name' if 'ckpt_name' in files else 'unet_name'] = chosen['model']
        return {'kind': 'comfyui', 'provider': None}, config
    if chosen['kind'] == 'codex':
        return {'kind': 'codex', 'provider': None}, {}
    return ({'kind': 'hosted', 'provider': chosen['provider']},
            {'base_url': chosen['base_url'], 'model': chosen['model'],
             'api_style': HOSTED[chosen['provider']]['api_style']})


def adapter(kind: str):
    return {'comfyui': ComfyAdapter, 'codex': CodexAdapter, 'hosted': HostedAdapter}[kind]()


def failed(error: AdapterError) -> DomainError:
    return DomainError(error.message, STATUS.get(error.code, 502), f'image_{error.code}')


def generate(prompt: str) -> bytes:
    """One portrait-shaped picture from the configured image maker, as the bytes it sent."""
    require(config()['ready'], 'Set up an image maker first: Portraits, at the top, next to the model.', 409)
    found, settings_for = backend()
    width, height = size_for(found['kind'], 'portrait')
    with tempfile.TemporaryDirectory(prefix='dramatis-portrait-') as scratch:
        request = ImageRequest(job_id=secrets.token_hex(8), prompt=prompt,
                               negative=LOCAL_NEGATIVE if found['kind'] == 'comfyui' else NEGATIVE,
                               seed=secrets.randbelow(2 ** 31), width=width, height=height, backend=found,
                               config=settings_for, key=ai.api_key(KEY_NAME) or None, raw_dir=Path(scratch))
        try:
            result = asyncio.run(adapter(found['kind']).generate(request))
        except AdapterError as error:
            raise failed(error) from error
    require(bool(result.data), 'The image maker answered without a picture.', 502)
    return result.data


def check() -> dict:
    """Whether the image maker as set up can draw, without drawing anything: Companion's own check, which asks
    ComfyUI for its nodes and files, Codex for its sign-in, or an image API for its models."""
    found, settings_for = backend()
    if found['kind'] == 'off':
        return {'ok': False, 'summary': 'No image maker is set up.', 'details': [], 'install': []}
    view = asyncio.run(adapter(found['kind']).check(found, settings_for, ai.api_key(KEY_NAME) or None)).view()
    if found['kind'] == 'comfyui' and not saved()['model']:
        view['details'] = [*view['details'], f"Model file: {model_file(settings_for)} (the family's own)."]
    return view


def card_picture(data: bytes) -> bytes:
    """Any picture as the PNG a card is made from: cropped to 2:3 and shrunk to the card's picture size."""
    try:
        with Image.open(io.BytesIO(data)) as opened:
            picture = ImageOps.exif_transpose(opened).convert('RGB')
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise DomainError('The image maker sent something that is not a picture.', 502) from error
    fitted = ImageOps.fit(picture, PLAIN_SIZE, Image.Resampling.LANCZOS, centering=CENTRE)
    out = io.BytesIO()
    fitted.save(out, 'PNG', optimize=True)
    return out.getvalue()

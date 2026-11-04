"""Drawing pictures with the user's chosen image maker, for portraits: any OpenAI-compatible images API (OpenAI,
OpenRouter and most hosted services) or ComfyUI on this computer, with the text-to-image workflow in
dramatis/data/comfyui-portrait.json. Off until the user sets one up.

A picture comes back as bytes in whatever format the maker sends; `card_picture` turns it into the PNG a card is made
from, cropped to 2:3 and shrunk to the card's picture size. Nothing here saves: the form shows the picture, and the
existing portrait route saves it when the user picks it.
The API key is kept in the system keyring, like the text model's (dramatis/ai.py), never in the settings file.
"""
import base64
import io
import json
import re
import secrets
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from PIL import Image, ImageOps, UnidentifiedImageError

from dramatis import ai, settings
from dramatis.cards import PLAIN_SIZE
from dramatis.formats.companion.errors import DomainError, require

PROVIDERS = ('off', 'openai', 'comfyui')
KEY_NAME = 'image-openai'
WORKFLOW = Path(__file__).parent / 'data' / 'comfyui-portrait.json'
# A hosted API is asked for 2:3 at this size unless the user names another; ComfyUI draws at DRAW_SIZE, which SDXL
# checkpoints handle well.
DEFAULT_SIZE = '1024x1536'
DRAW_SIZE = (832, 1248)
SIZE = re.compile(r'^\d{3,4}x\d{3,4}$')
# What a ComfyUI checkpoint is told to leave out. A hosted API has its own rules and gets the prompt alone.
NEGATIVE = ('text, letters, watermark, signature, logo, frame, nude, nsfw, sexual, child, extra fingers, '
            'deformed hands, blurry, lowres')
REFUSAL_SIGNS = ('content_policy', 'content policy', 'safety', 'moderation', 'prohibited', 'blocked', 'nsfw')
TIMEOUT = 300
POLL_SECONDS = 1.0
# A finished picture is cropped to 2:3 with the frame a little above the middle, where a waist-up portrait's face is.
CENTRE = (0.5, 0.35)


def config() -> dict:
    """The image settings as the screen shows them, and whether portraits can be made with them."""
    saved = settings.load().get('image') or {}
    provider = saved.get('provider') if saved.get('provider') in PROVIDERS else 'off'
    found = {'provider': provider, 'base_url': saved.get('base_url') or '', 'model': saved.get('model') or '',
             'size': saved.get('size') or '', 'has_key': bool(ai.api_key(KEY_NAME))}
    ready = provider != 'off' and bool(found['base_url']) and (provider != 'comfyui' or bool(found['model']))
    return found | {'ready': ready}


def configure(provider: str, base_url: str = '', model: str = '', size: str = '', key: str | None = None) -> dict:
    require(provider in PROVIDERS, 'Pick an OpenAI-compatible images API, ComfyUI, or no image maker.', 422)
    base_url = api_base(base_url)
    if provider != 'off':
        example = 'http://127.0.0.1:8188 for ComfyUI' if provider == 'comfyui' else 'https://api.openai.com/v1'
        require(base_url.startswith(('http://', 'https://')), f'The image maker needs its address, like {example}.',
                422)
    if provider == 'comfyui':
        require(bool(model.strip()), 'Name the ComfyUI checkpoint to draw with, as its file is called in '
                'models/checkpoints, like sd_xl_base_1.0.safetensors.', 422)
    require(not size.strip() or bool(SIZE.match(size.strip())), 'Give the size as width x height, like 1024x1536.',
            422)
    if key is not None:
        ai.store_key(KEY_NAME, key)
    settings.save({'image': {'provider': provider, 'base_url': base_url, 'model': model.strip(),
                             'size': size.strip()}})
    return config()


def api_base(value: str) -> str:
    """The address without a request path pasted from a provider's docs, which the calls below add themselves."""
    value = value.strip().rstrip('/')
    for suffix in ('/images/generations', '/images', '/prompt'):
        if value.endswith(suffix) and urlsplit(value).path != suffix:
            return value.removesuffix(suffix).rstrip('/')
    return value


def client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT, follow_redirects=False)


def generate(prompt: str) -> bytes:
    """One picture from the configured image maker, as the bytes it sent."""
    chosen = config()
    require(chosen['ready'], 'Set up an image maker first: Portraits, at the top, next to the model.', 409)
    with client() as http:
        if chosen['provider'] == 'comfyui':
            return comfyui(http, chosen, prompt)
        return hosted(http, chosen, prompt)


# OpenAI-compatible APIs --------------------------------------------------------------------------------------------

def is_openrouter(base_url: str) -> bool:
    host = urlsplit(base_url).hostname or ''
    return host == 'openrouter.ai' or host.endswith('.openrouter.ai')


def hosted(http: httpx.Client, chosen: dict, prompt: str) -> bytes:
    """OpenAI's `POST /images/generations`, or OpenRouter's own `POST /images`, which takes an aspect ratio."""
    key = ai.api_key(KEY_NAME)
    headers = {'Authorization': f'Bearer {key}'} if key else {}
    body = {'prompt': prompt} | ({'model': chosen['model']} if chosen['model'] else {})
    if is_openrouter(chosen['base_url']):
        url, body = f"{chosen['base_url']}/images", body | {'aspect_ratio': '2:3'}
    else:
        url, body = f"{chosen['base_url']}/images/generations", body | {'n': 1, 'size': chosen['size'] or DEFAULT_SIZE}
    data = answer(send(lambda: http.post(url, json=body, headers=headers), chosen['base_url']))
    item = (data.get('data') or [{}])[0] if isinstance(data.get('data'), list) else {}
    if isinstance(item, dict) and isinstance(item.get('b64_json'), str):
        try:
            return base64.b64decode(item['b64_json'])
        except ValueError as error:
            raise DomainError('The image maker sent a picture that did not arrive whole.', 502) from error
    link = item.get('url') if isinstance(item, dict) else None
    require(isinstance(link, str) and link.startswith('https://'), 'The image maker answered without a picture.', 502)
    found = send(lambda: http.get(link), link)
    require(found.is_success, 'The finished picture could not be downloaded.', 502)
    return found.content


def send(request, where: str) -> httpx.Response:
    try:
        return request()
    except httpx.TimeoutException as error:
        raise DomainError(f'The image maker at {where} took too long.', 504) from error
    except httpx.HTTPError as error:
        raise DomainError(f'Could not reach the image maker at {where}. Check the address and that it is running.',
                          502) from error


def said(text: str) -> str:
    """The maker's own words about a failed request: `error.message`, `message` or `detail`, else short plain text."""
    try:
        data = json.loads(text)
    except ValueError:
        data = None
    words = text if data is None and '<' not in text[:50] else ''
    if isinstance(data, dict):
        error = data.get('error')
        error = error.get('message') if isinstance(error, dict) else error
        words = next((str(item) for item in (error, data.get('message'), data.get('detail')) if item), '')
    words = ' '.join(words.split())[:300]
    return f' It said: "{words}"' if words else ''


def answer(response: httpx.Response) -> dict:
    """The maker's JSON answer, or a plain message for what went wrong."""
    text = response.text[:2000]
    if response.status_code in (401, 403):
        raise DomainError(f'The image maker did not accept the API key. Set it again under Portraits.{said(text)}',
                          401)
    if response.status_code == 429:
        raise DomainError(f'The image maker is rate limiting this key; try again in a minute.{said(text)}', 429)
    if response.status_code >= 400 and any(sign in text.casefold() for sign in REFUSAL_SIGNS):
        raise DomainError(f'The image maker refused this portrait under its content rules.{said(text)}', 422)
    require(response.status_code < 400, f'The image maker answered {response.status_code}.{said(text)}', 502)
    try:
        data = response.json()
    except ValueError as error:
        raise DomainError('The image maker sent something that is not an answer.', 502) from error
    require(isinstance(data, dict), 'The image maker sent something that is not an answer.', 502)
    return data


# ComfyUI -----------------------------------------------------------------------------------------------------------

def workflow(prompt: str, checkpoint: str, seed: int) -> dict:
    """The bundled workflow with its {{placeholders}} filled in; a value that is only a placeholder takes the type it
    is given, so width and seed stay numbers."""
    values = {'prompt': prompt, 'negative': NEGATIVE, 'checkpoint': checkpoint, 'width': DRAW_SIZE[0],
              'height': DRAW_SIZE[1], 'seed': seed}

    def filled(item):
        if isinstance(item, dict):
            return {key: filled(value) for key, value in item.items()}
        if isinstance(item, list):
            return [filled(value) for value in item]
        if isinstance(item, str) and item.startswith('{{') and item.endswith('}}'):
            return values[item[2:-2]]
        return item

    return filled(json.loads(WORKFLOW.read_text(encoding='utf-8')))


def comfyui(http: httpx.Client, chosen: dict, prompt: str) -> bytes:
    """Queues the workflow, waits for it to finish, and fetches the picture it saved."""
    base = chosen['base_url']
    queued = answer(send(lambda: http.post(f'{base}/prompt', json={
        'prompt': workflow(prompt, chosen['model'], secrets.randbelow(2 ** 32)),
        'client_id': 'prosperos-dramatis'}), base))
    job = queued.get('prompt_id')
    require(isinstance(job, str) and bool(job), f'ComfyUI did not take the workflow.{said(json.dumps(queued))}', 502)
    deadline = time.monotonic() + TIMEOUT
    while time.monotonic() < deadline:
        picture = finished(answer(send(lambda: http.get(f'{base}/history/{job}'), base)).get(job))
        if picture is not None:
            found = send(lambda: http.get(f'{base}/view', params=picture), base)
            require(found.is_success, 'ComfyUI made the picture but would not hand it over.', 502)
            return found.content
        time.sleep(POLL_SECONDS)
    raise DomainError('ComfyUI took too long to draw the portrait.', 504)


def finished(entry) -> dict | None:
    """Where the job's picture is, once ComfyUI has one; an error ComfyUI reports comes back as a plain message."""
    if not isinstance(entry, dict):
        return None
    status = entry.get('status') if isinstance(entry.get('status'), dict) else {}
    if status.get('status_str') == 'error':
        messages = [item[1].get('exception_message') for item in status.get('messages') or []
                    if isinstance(item, list) and len(item) == 2 and isinstance(item[1], dict)]
        detail = next((message for message in messages if message), '')
        raise DomainError(f"ComfyUI could not draw it.{f' It said: {detail}' if detail else ''} Check the "
                          'checkpoint name under Portraits.', 502)
    for output in (entry.get('outputs') or {}).values():
        for image in (output.get('images') or []) if isinstance(output, dict) else []:
            if isinstance(image, dict) and image.get('filename'):
                return {'filename': image['filename'], 'subfolder': image.get('subfolder') or '',
                        'type': image.get('type') or 'output'}
    if status.get('completed'):
        raise DomainError('ComfyUI finished without saving a picture. Check that the workflow ends in Save Image.', 502)
    return None


# The card's picture ------------------------------------------------------------------------------------------------

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

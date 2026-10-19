"""
mesh_client.py - the ONLY file in this project that talks to an AI model.

Every agent calls chat() or generate_image() from here. Because all calls
pass through one place:
  1. Every call is guaranteed to go through Mesh API (a hackathon rule).
  2. Every call is logged (which agent, which model, how long it took).
"""
import base64
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from app import db

load_dotenv()

MESH_BASE_URL = "https://api.meshapi.ai/v1"

WRITER_MODEL = os.getenv("WRITER_MODEL", "openai/gpt-4o-mini")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "anthropic/claude-sonnet-4.5")
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "openai/gpt-image-1")

IMAGE_DIR = Path(__file__).resolve().parent.parent / "data" / "images"

_client = None


def get_client() -> OpenAI:
    """Create the OpenAI client once, pointed at Mesh instead of OpenAI."""
    global _client
    if _client is None:
        key = os.getenv("MESH_API_KEY")
        if not key:
            raise RuntimeError("MESH_API_KEY is missing. Copy .env.example to .env and add your key.")
        _client = OpenAI(base_url=MESH_BASE_URL, api_key=key)
    return _client


def _with_retries(fn, attempts: int = 3):
    """Try a call up to 3 times, waiting 2s then 4s between tries."""
    for i in range(attempts):
        try:
            return fn()
        except Exception:
            if i == attempts - 1:
                raise
            time.sleep(2 ** (i + 1))


def chat(messages, model: str = None, agent: str = "unknown",
         content_id: int = None, json_mode: bool = False,
         temperature: float = 0.7) -> str:
    """
    Send messages to a model through Mesh and return the reply text.

    json_mode=True asks the model to reply with JSON only, and returns
    the text so the caller can json.loads() it.
    """
    model = model or WRITER_MODEL
    kwargs = {"model": model, "messages": messages, "temperature": temperature}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    start = time.time()
    response = _with_retries(lambda: get_client().chat.completions.create(**kwargs))
    seconds = round(time.time() - start, 2)

    text = response.choices[0].message.content or ""
    usage = getattr(response, "usage", None)
    db.log_llm_call(
        agent=agent, model=model, kind="chat", content_id=content_id,
        prompt_tokens=getattr(usage, "prompt_tokens", None),
        completion_tokens=getattr(usage, "completion_tokens", None),
        seconds=seconds,
    )
    return text


def chat_json(messages, **kwargs) -> dict:
    """Same as chat() but parses the reply as JSON and returns a dict."""
    text = chat(messages, json_mode=True, **kwargs)
    text = text.strip()
    # Some models wrap JSON in ```json ... ``` - strip that if present.
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return json.loads(text)


def generate_image(prompt: str, agent: str = "visual", content_id: int = None,
                   size: str = "1024x1024", filename: str = None) -> str:
    """Generate an image through Mesh, save it as a PNG, and return the file path."""
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    start = time.time()
    response = _with_retries(lambda: get_client().images.generate(
        model=IMAGE_MODEL, prompt=prompt, size=size, n=1))
    seconds = round(time.time() - start, 2)

    item = response.data[0]
    filename = filename or f"image_{content_id or int(time.time())}.png"
    path = IMAGE_DIR / filename

    if getattr(item, "b64_json", None):
        path.write_bytes(base64.b64decode(item.b64_json))
    elif getattr(item, "url", None):
        # Some models return a link instead of the image bytes.
        import urllib.request
        urllib.request.urlretrieve(item.url, path)
    else:
        raise RuntimeError("Image response had neither b64_json nor url.")

    db.log_llm_call(agent=agent, model=IMAGE_MODEL, kind="image",
                    content_id=content_id, seconds=seconds)
    return str(path)


def list_models() -> list:
    """
    List models available on your Mesh account (costs no credits).

    Mesh returns a plain JSON list here, while the OpenAI library expects
    {"data": [...]}, so we call the endpoint directly and accept both shapes.
    """
    import httpx  # installed together with the openai package

    key = os.getenv("MESH_API_KEY")
    resp = httpx.get(f"{MESH_BASE_URL}/models",
                     headers={"Authorization": f"Bearer {key}"}, timeout=30)
    resp.raise_for_status()
    body = resp.json()
    items = body.get("data", body) if isinstance(body, dict) else body

    ids = []
    for item in items:
        if isinstance(item, str):
            ids.append(item)
        elif isinstance(item, dict):
            ids.append(item.get("id") or item.get("slug") or item.get("name"))
    return [i for i in ids if i]

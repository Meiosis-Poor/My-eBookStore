from __future__ import annotations

import hashlib
import json
import math
import random
from functools import lru_cache
from typing import Iterable

import httpx

try:
    from backend.config.embedding_secrets import EMBEDDING_API_KEY, EMBEDDING_API_URL, EMBEDDING_MODEL
except ImportError:
    try:
        from config.embedding_secrets import EMBEDDING_API_KEY, EMBEDDING_API_URL, EMBEDDING_MODEL
    except ImportError:
        EMBEDDING_API_URL = ""
        EMBEDDING_API_KEY = ""
        EMBEDDING_MODEL = ""


REQUEST_TIMEOUT_SECONDS = 30.0


def embed_text(text: str) -> list[float]:
    if EMBEDDING_API_URL and EMBEDDING_API_KEY and EMBEDDING_MODEL:
        return _embed_text_remote(text or "")
    return _embed_text_fallback(text or "")


@lru_cache(maxsize=2048)
def _embed_text_remote(text: str) -> list[float]:
    url = EMBEDDING_API_URL.rstrip("/")
    if not url.endswith("/embeddings"):
        url = f"{url}/embeddings"
    payload = {"model": EMBEDDING_MODEL, "input": text}
    headers = {
        "Authorization": f"Bearer {EMBEDDING_API_KEY}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

    embedding = None
    if isinstance(data, dict):
        if isinstance(data.get("data"), list) and data["data"]:
            embedding = data["data"][0].get("embedding")
        elif "embedding" in data:
            embedding = data["embedding"]
    if not isinstance(embedding, list) or not embedding:
        raise ValueError("Embedding API response does not contain a valid embedding vector")
    return [float(value) for value in embedding]


def _embed_text_fallback(text: str) -> list[float]:
    seed = int(hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16], 16)
    rng = random.Random(seed)
    values = [rng.uniform(-1, 1) for _ in range(64)]
    length = math.sqrt(sum(v * v for v in values)) or 1.0
    return [round(v / length, 8) for v in values]


def dumps(vec: Iterable[float]) -> str:
    return json.dumps([float(v) for v in vec], ensure_ascii=False)


def loads(raw: str | None) -> list[float] | None:
    if not raw:
        return None
    try:
        values = json.loads(raw)
        if isinstance(values, list):
            return [float(v) for v in values]
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return None


def cosine_distance(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 1.0
    n = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(n))
    aa = math.sqrt(sum(a[i] * a[i] for i in range(n)))
    bb = math.sqrt(sum(b[i] * b[i] for i in range(n)))
    if aa == 0 or bb == 0:
        return 1.0
    return 1 - dot / (aa * bb)

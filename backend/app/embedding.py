from __future__ import annotations

import hashlib
import json
import math
import random
from typing import Iterable


def embed_text(text: str) -> list[float]:
    """Embedding adapter.

    Replace this fallback with the real private model call after filling
    backend/config/embedding_secrets.py. The deterministic fallback keeps
    development, SQL seeding, and tests runnable without external secrets.
    """
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

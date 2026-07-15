"""OpenAI wrapper (GPT-4o, JSON) with a deterministic MOCK fallback + token cost."""

import os
import time
import json
import re

MODEL = os.getenv("MM_MODEL", "gpt-4o")
PRICE_IN = 2.50 / 1_000_000
PRICE_OUT = 10.00 / 1_000_000


def live() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def mode() -> str:
    return "openai" if live() else "mock"


_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI()
    return _client


def chat_json(system: str, user: str) -> tuple[dict, dict, int]:
    t0 = time.perf_counter()
    r = _get_client().chat.completions.create(
        model=MODEL, temperature=0.3,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    ms = int((time.perf_counter() - t0) * 1000)
    data = json.loads(r.choices[0].message.content)
    u = r.usage
    usage = {"in": u.prompt_tokens, "out": u.completion_tokens,
             "cost": round(u.prompt_tokens * PRICE_IN + u.completion_tokens * PRICE_OUT, 6)}
    return data, usage, ms

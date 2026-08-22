"""
Persistence layer for the Vera challenge bot.
"""
import os
import json
import time
import httpx

UPSTASH_URL = os.environ.get("UPSTASH_REDIS_REST_URL", "").rstrip("/")
UPSTASH_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")

_USE_REDIS = bool(UPSTASH_URL and UPSTASH_TOKEN)
_mem_store: dict = {}

if not _USE_REDIS:
    print("[storage] WARNING: Upstash not configured, using in-memory fallback (dev only).")


def _redis_get(key: str):
    r = httpx.get(f"{UPSTASH_URL}/get/{key}", headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"}, timeout=5.0)
    r.raise_for_status()
    return r.json().get("result")


def _redis_set(key: str, value: str) -> None:
    httpx.post(f"{UPSTASH_URL}/set/{key}", headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"}, content=value.encode("utf-8"), timeout=5.0).raise_for_status()


def _redis_keys(pattern: str):
    r = httpx.get(f"{UPSTASH_URL}/keys/{pattern}", headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"}, timeout=5.0)
    r.raise_for_status()
    return r.json().get("result") or []


def get_json(key: str):
    raw = _redis_get(key) if _USE_REDIS else _mem_store.get(key)
    if raw is None:
        return None
    return json.loads(raw)


def set_json(key: str, value) -> None:
    raw = json.dumps(value)
    if _USE_REDIS:
        _redis_set(key, raw)
    else:
        _mem_store[key] = raw


def count_prefix(prefix: str) -> int:
    if _USE_REDIS:
        return len(_redis_keys(f"{prefix}*"))
    return sum(1 for k in _mem_store if k.startswith(prefix))


def append_conversation(conversation_id: str, entry: dict):
    key = f"conv:{conversation_id}"
    history = get_json(key) or []
    history.append(entry)
    set_json(key, history)
    return history


def is_persistent() -> bool:
    return _USE_REDIS


START_TIME = time.time()


def uptime_seconds() -> int:
    return int(time.time() - START_TIME)

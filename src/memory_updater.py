import json
import os
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMORY_PATH = os.path.join(BASE_DIR, "memory", "memory.json")


def _merge_lists(existing: list, incoming: list) -> list:
    """Append items from incoming that are not already in existing (by equality)."""
    seen = [json.dumps(item, sort_keys=True) for item in existing]
    for item in incoming:
        key = json.dumps(item, sort_keys=True)
        if key not in seen:
            existing.append(item)
            seen.append(key)
    return existing


def _merge(base: dict, updates: dict) -> dict:
    for key, value in updates.items():
        if key == "last_updated":
            continue
        if key not in base:
            base[key] = value
        elif isinstance(base[key], list) and isinstance(value, list):
            base[key] = _merge_lists(base[key], value)
        elif isinstance(base[key], dict) and isinstance(value, dict):
            base[key] = _merge(base[key], value)
        else:
            # Scalar: overwrite with the new value
            base[key] = value
    return base


def update_memory(new_info: dict) -> None:
    """Merge new_info into memory/memory.json and update last_updated timestamp."""
    with open(MEMORY_PATH, "r", encoding="utf-8") as f:
        memory = json.load(f)

    memory = _merge(memory, new_info)
    memory["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with open(MEMORY_PATH, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2, ensure_ascii=False)

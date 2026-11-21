"""Загрузка профиля области (domains/<area>/profile.yaml) и схемы сдачи."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

DOMAINS_DIR = Path("domains")


def load_profile(area: str) -> dict:
    """Профиль области + схема сдачи (schema.json из шаблона области)."""
    path = DOMAINS_DIR / area / "profile.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Нет профиля области: {path}")
    with open(path, encoding="utf-8") as f:
        profile = yaml.safe_load(f)
    schema_path = Path(profile["schema_json"])
    profile["schema"] = json.loads(schema_path.read_text(encoding="utf-8"))
    for key, prompt_path in profile.get("prompts", {}).items():
        profile.setdefault("prompt_text", {})[key] = Path(prompt_path).read_text(encoding="utf-8")
    return profile


def area_cfg(cfg: dict, area: str) -> dict:
    """Пути данных области: data.<area>.*, для rag — плоские ключи data.*."""
    data = cfg["data"]
    if area == "rag":
        return {k: v for k, v in data.items() if not isinstance(v, dict)}
    sub = data.get(area)
    if not sub:
        raise KeyError(f"В config.yaml нет блока data.{area}")
    merged = {k: v for k, v in data.items() if not isinstance(v, dict)}
    merged.update(sub)
    return merged

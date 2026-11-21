"""Шаг A. Документ целиком: библиография, in_scope, сущности области.

Результат: cache/v2/<area>/<set>/<pid>/step_a.json
  {"publication": {...}, "entities": {"configurations": [{...с config_id}], ...}}
Идентификаторы (C1, DS1, T1, E1) назначает код, не модель.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from . import pages as pages_mod

log = logging.getLogger(__name__)

ENTITY_TABLES = ("configurations", "datasets", "tasks", "experiments")

_KEY_FIELD = {"configurations": "config_id", "datasets": "dataset_id",
              "tasks": "task_id", "experiments": "experiment_id"}


def work_dir(cfg: dict, area: str, set_name: str, pid: str) -> Path:
    path = Path(cfg["work"]["cache_dir"]) / "v2" / area / set_name / pid
    path.mkdir(parents=True, exist_ok=True)
    return path


def key_field(table: str) -> str:
    return _KEY_FIELD[table]


def assign_ids(entities: dict, profile: dict) -> dict:
    """Канонические id по порядку: C1.., DS1.., T1.., E1..."""
    for table in ENTITY_TABLES:
        prefix = profile["ids"][table]
        for i, item in enumerate(entities.get(table) or [], start=1):
            item[_KEY_FIELD[table]] = f"{prefix}{i}"
    return entities


def _entity_brief(item: dict) -> str:
    """Однострочное описание сущности для промпта шага B."""
    parts = [f"{k}={v}" for k, v in item.items()
             if v not in (None, "", []) and k != "note" and not k.endswith("_id")]
    return "; ".join(parts[:6])


def entities_listing(entities: dict) -> str:
    """Перечень сущностей с id — контекст для промпта шага B."""
    out = ["Entities of this paper (reference them by id):"]
    for table in ENTITY_TABLES:
        items = entities.get(table) or []
        if not items:
            continue
        key = _KEY_FIELD[table]
        out.append(f"{table}:")
        out.extend(f"- {it[key]}: {_entity_brief(it)}" for it in items)
        out.append("")
    return "\n".join(out)


def run_article(pid: str, cfg: dict, area: str, set_name: str, profile: dict,
                llm, pdf_dir: Path, force: bool = False) -> dict:
    """Шаг A для одной статьи (с кэшем)."""
    out_path = work_dir(cfg, area, set_name, pid) / "step_a.json"
    if out_path.exists() and not force:
        return json.loads(out_path.read_text(encoding="utf-8"))

    doc = pages_mod.load_pages(pid, cfg, area, pdf_dir)
    text = pages_mod.full_document_text(doc["pages"])
    system = profile["prompt_text"]["step_a"]
    user = f"Paper id: {pid}\n\n{text}"
    data = llm.ask_json("document", system, user, req_id=f"{pid}_A")
    if not isinstance(data, dict):
        raise TypeError(f"{pid}: шаг A не вернул JSON-объект")

    authors = data.get("authors")
    publication = {
        "publication_id": pid,
        "title": str(data.get("title") or ""),
        "year": data.get("year") or "",
        "DOI": str(data.get("doi") or ""),
        "authors": "; ".join(authors) if isinstance(authors, list) else str(authors or ""),
        "in_scope": "true" if data.get("in_scope", True) else "false",
        "exclusion_reason": str(data.get("exclusion_reason") or ""),
    }
    if publication["in_scope"] == "true":
        publication["exclusion_reason"] = ""

    entities = {t: (data.get(t) or []) if isinstance(data.get(t), list) else []
                for t in ENTITY_TABLES}
    for table in ENTITY_TABLES:  # label не уходит в CSV — только для промпта шага B
        for item in entities[table]:
            item.setdefault("label", "")
    assign_ids(entities, profile)

    result = {"publication": publication, "entities": entities}
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("%s: шаг A — in_scope=%s, конфигураций %d, наборов %d, задач %d, экспериментов %d",
             pid, publication["in_scope"], *(len(entities[t]) for t in ENTITY_TABLES))
    return result

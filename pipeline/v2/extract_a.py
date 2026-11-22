"""Шаг A. Документ целиком: библиография, in_scope, сущности области.

Результат: cache/v2/<area>/<set>/<pid>/step_a.json
  {"publication": {...}, "entities": {<таблица>: [{...с id}]}}
Состав сущностей и ключи берутся из профиля области (entity_tables + schema.keys).
Идентификаторы назначает код, не модель.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from . import pages as pages_mod

log = logging.getLogger(__name__)


def entity_tables(profile: dict) -> list[str]:
    """Таблицы сущностей области (все таблицы сдачи кроме publications/results/issues)."""
    return [t for t in profile["schema"]["tables"]
            if t not in ("publications", "results", "issues")]


def key_field(profile: dict, table: str) -> str:
    return profile["schema"]["keys"][table]


def work_dir(cfg: dict, area: str, set_name: str, pid: str) -> Path:
    path = Path(cfg["work"]["cache_dir"]) / "v2" / area / set_name / pid
    path.mkdir(parents=True, exist_ok=True)
    return path


def assign_ids(entities: dict, profile: dict) -> dict:
    """Канонические id по порядку: C1.., DS1.. / M1.., DV1.. — по профилю."""
    for table in entity_tables(profile):
        prefix = profile["ids"][table]
        key = key_field(profile, table)
        for i, item in enumerate(entities.get(table) or [], start=1):
            item[key] = f"{prefix}{i}"
    return entities


def resolve_links(entities: dict, profile: dict) -> None:
    """Ссылки между сущностями по label-полям (Solar: absorber_label -> M1 и т.п.)."""
    for table, links in (profile.get("entity_links") or {}).items():
        for field, spec in links.items():
            target_table = spec["table"]
            by = spec["by"]
            tkey = key_field(profile, target_table)
            index = {}
            for item in entities.get(target_table) or []:
                label = (item.get("label") or "").strip().lower()
                if label:
                    index[label] = item[tkey]
            for item in entities.get(table) or []:
                label = (item.pop(by, None) or "").strip().lower()
                if label and label in index:
                    item[field] = index[label]
                else:
                    item.setdefault(field, "")


def _entity_brief(item: dict) -> str:
    """Однострочное описание сущности для промпта шага B."""
    parts = [f"{k}={v}" for k, v in item.items()
             if v not in (None, "", []) and k != "note" and not k.endswith("_id")]
    return "; ".join(parts[:6])


def entities_listing(entities: dict, profile: dict) -> str:
    """Перечень сущностей с id — контекст для промпта шага B."""
    out = ["Entities of this paper (reference them by id):"]
    for table in entity_tables(profile):
        items = entities.get(table) or []
        if not items:
            continue
        key = key_field(profile, table)
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

    tables = entity_tables(profile)
    entities = {t: (data.get(t) or []) if isinstance(data.get(t), list) else []
                for t in tables}
    for table in tables:  # label не уходит в CSV — только для промпта шага B
        for item in entities[table]:
            item.setdefault("label", "")
    assign_ids(entities, profile)
    resolve_links(entities, profile)

    result = {"publication": publication, "entities": entities}
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    counts = ", ".join(f"{t}: {len(entities[t])}" for t in tables)
    log.info("%s: шаг A — in_scope=%s, %s", pid, publication["in_scope"], counts)
    return result

"""Шаг C. Верификация: цитата на странице, число в цитате, ссылки на сущности.

Нормализация цитат повторяет check_submission.py соответствующей области —
мы проверяем себя ровно так, как проверяют организаторы:
  rag:   NFKC, удаление soft hyphen, склейка переносов «слово-\\nслово»,
         схлопывание пробелов; регистр сохраняется; страница — оба парсера.
  solar: lowercase, лигатуры, тире -> '-', остаются только [a-z0-9.%];
         фрагменты «Table…/Supplementary…» не проверяются.

Не прошло -> один корректирующий запрос на страницу -> иначе отбросить
и записать в rejected.json с причиной.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from pathlib import Path

from ..textnorm import contains_number
from . import pages as pages_mod
from .extract_a import entities_listing, entity_tables, key_field, work_dir
from .extract_b import result_keys

log = logging.getLogger(__name__)


def norm_rag(text: str) -> str:
    """Как norm() в data/rag/tools/check_submission.py."""
    text = unicodedata.normalize("NFKC", text).replace("­", "")
    text = re.sub(r"(?<=\w)-\s*\r?\n\s*(?=\w)", "", text)
    return re.sub(r"\s+", " ", text).strip()


def norm_solar(text: str) -> str:
    """Как norm() в data/solar/tools/check_submission.py."""
    text = (text.replace("ﬁ", "fi").replace("ﬂ", "fl").replace("ﬀ", "ff")
            .replace("−", "-").replace("–", "-"))
    return re.sub(r"[^a-z0-9.%]+", "", text.lower())


def _quote_norm(profile: dict):
    return norm_solar if profile.get("quote_norm") == "solar" else norm_rag


def _skip_quote(profile: dict, fragment: str) -> bool:
    """Цитаты-исключения, которые чекер области не проверяет."""
    if profile.get("quote_norm") == "solar":
        return bool(re.match(r"^(Table|TABLE|Supplementary)", fragment.strip()))
    return False


class Verifier:
    """Проверка результатов одной статьи."""

    def __init__(self, cfg: dict, area: str, profile: dict, pid: str, pdf_dir: Path):
        self.profile = profile
        self.norm = _quote_norm(profile)
        self.entities: dict[str, set] = {}
        doc = pages_mod.load_pages(pid, cfg, area, pdf_dir)
        # нормализованные варианты текста каждой страницы (оба парсера)
        self.page_variants: dict[int, list[str]] = {}
        for p in doc["pages"]:
            variants = [p.get("text_pymupdf") or "", p.get("text_pypdf") or ""]
            if not any(v.strip() for v in variants):
                variants = ["\n".join(l["text"] for l in p.get("lines", []))]
            self.page_variants[p["page"]] = [self.norm(v) for v in variants if v.strip()]
        self.n_pages = len(doc["pages"])

    def set_entities(self, entities: dict) -> None:
        self.entities = {t: {it[key_field(self.profile, t)] for it in entities.get(t) or []}
                         for t in entity_tables(self.profile)}

    def problems(self, r: dict) -> list[str]:
        """Список нарушений записи (пусто — запись валидна)."""
        probs: list[str] = []
        page = r.get("source_page")
        frag = (r.get("source_fragment") or "").strip()
        if not isinstance(page, int) or not (1 <= page <= self.n_pages):
            probs.append(f"source_page {page} вне диапазона 1..{self.n_pages}")
        elif frag and not _skip_quote(self.profile, frag):
            needle = self.norm(frag)
            variants = self.page_variants.get(page, [])
            if not variants:
                probs.append(f"на странице {page} нет текстового слоя")
            elif not any(needle in v for v in variants):
                probs.append(f"цитата не найдена на странице {page}")
        raw = (r.get("raw_value") or "").strip()
        if not raw:
            probs.append("пустое raw_value")
        elif frag and not contains_number(frag, raw):
            probs.append(f"число «{raw}» не найдено в цитате")
        for table in entity_tables(self.profile):
            field = key_field(self.profile, table)
            ref = (r.get(field) or "").strip()
            if ref and self.entities.get(table) and ref not in self.entities[table]:
                probs.append(f"{field}={ref} нет среди сущностей шага A")
        return probs


def run_article(pid: str, cfg: dict, area: str, set_name: str, profile: dict,
                llm, pdf_dir: Path, step_a: dict, step_b: dict,
                force: bool = False) -> dict:
    """Шаг C: верификация + одна корректирующая попытка на страницу."""
    out_path = work_dir(cfg, area, set_name, pid) / "verified.json"
    rej_path = work_dir(cfg, area, set_name, pid) / "rejected.json"
    if out_path.exists() and not force:
        return json.loads(out_path.read_text(encoding="utf-8"))

    verifier = Verifier(cfg, area, profile, pid, pdf_dir)
    verifier.set_entities(step_a["entities"])

    valid: list[dict] = []
    rejected: list[dict] = []
    invalid: list[dict] = []
    for r in step_b.get("results", []):
        probs = verifier.problems(r)
        if probs:
            invalid.append((r, probs))
        else:
            valid.append(r)

    # Корректирующий запрос: по одному на затронутую страницу
    if invalid and llm is not None:
        bad_pages = sorted({r["source_page"] for r, _ in invalid
                            if isinstance(r.get("source_page"), int)})
        doc = pages_mod.load_pages(pid, cfg, area, pdf_dir)
        texts = {p["page"]: pages_mod.page_text(p) for p in doc["pages"]}
        listing = entities_listing(step_a["entities"], profile)
        for pno in bad_pages:
            page_invalid = [(r, p) for r, p in invalid if r["source_page"] == pno]
            errors_txt = "\n".join(
                f"- metric «{r.get('metric_name')}» value «{r.get('raw_value')}»: "
                + "; ".join(p) for r, p in page_invalid[:10])
            user = (f"{listing}\n\n=== Page {pno} ===\n{texts.get(pno, '')}\n\n"
                    f"Your previous extraction for this page had errors:\n{errors_txt}\n"
                    "Fix them: quote source_fragment EXACTLY as printed on this page, "
                    "use only entity ids from the entity list.")
            try:
                data = llm.ask_json("page", profile["prompt_text"]["step_b"],
                                    user, req_id=f"{pid}_p{pno:02d}_retry")
            except Exception as exc:  # noqa: BLE001 — бюджет/сеть: отбраковываем без повтора
                log.warning("%s p.%d: повторный запрос не удался: %s", pid, pno, exc)
                data = None
            if isinstance(data, dict) and isinstance(data.get("results"), list):
                for raw_r in data["results"]:
                    if not isinstance(raw_r, dict):
                        continue
                    r = {k: raw_r.get(k) for k in result_keys(profile)}
                    r["publication_id"] = pid
                    r["source_page"] = pno
                    probs = verifier.problems(r)
                    if probs:
                        rejected.append({"result": r, "problems": probs})
                    else:
                        valid.append(r)
            # исходные записи страницы уходят в rejected (их заменили исправленные)
            rejected.extend({"result": r, "problems": p} for r, p in page_invalid)
            invalid = [(r, p) for r, p in invalid if r["source_page"] != pno]

    # записи со страниц вне диапазона (source_page не число) — повторить не можем
    rejected.extend({"result": r, "problems": p} for r, p in invalid)

    for r in valid:
        r.setdefault("extraction_status", "extracted")
    out = {"results": valid}
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    rej_path.write_text(json.dumps(rejected, ensure_ascii=False, indent=1), encoding="utf-8")
    if rejected:
        log.warning("%s: шаг C — валидно %d, отброшено %d", pid, len(valid), len(rejected))
    else:
        log.info("%s: шаг C — валидно %d, отброшено 0", pid, len(valid))
    return out

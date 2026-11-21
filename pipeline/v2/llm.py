"""Обёртка над ApiClient для конвейера v2.

Добавляет: json_mode, модели по ролям (document/page), разбор JSON с одной
корректирующей попыткой, учёт токенов и стоимости по моделям, лимит бюджета.
"""
from __future__ import annotations

import json
import logging
import re

from ..model_client import ApiClient

log = logging.getLogger(__name__)

# USD за 1M токенов: (вход, выход)
PRICES = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
}


class BudgetExceeded(RuntimeError):
    """Превышен лимит model.budget_usd — прогон останавливается, кэш сохранён."""


def parse_json(text: str) -> dict | list | None:
    """JSON из ответа модели: чистый, в code-фенсе или с текстом вокруг."""
    text = (text or "").strip()
    if not text:
        return None
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
    if start < 0:
        return None
    end = max(text.rfind("}"), text.rfind("]"))
    if end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


class Llm:
    """Клиент с ролями моделей и учётом расхода."""

    def __init__(self, cfg: dict):
        api = cfg["model"]["api"]
        self.client = ApiClient(api)
        self.model_document = api.get("model_document", api.get("model"))
        self.model_page = api.get("model_page", api.get("model"))
        self.max_tokens = int(api.get("max_tokens", 4000))
        self.budget = float(cfg["model"].get("budget_usd") or 0)
        self.calls = 0
        self.tokens: dict[str, list[int]] = {}  # model -> [in, out]

    # -- учёт ---------------------------------------------------------------
    def _account(self) -> None:
        usage = getattr(self.client, "last_usage", {}) or {}
        model = usage.get("model", "?")
        slot = self.tokens.setdefault(model, [0, 0])
        slot[0] += usage.get("prompt_tokens", 0)
        slot[1] += usage.get("completion_tokens", 0)
        self.calls += 1
        if self.budget and self.cost_usd() > self.budget:
            raise BudgetExceeded(
                f"Бюджет исчерпан: ${self.cost_usd():.3f} > ${self.budget:.2f}")

    def cost_usd(self) -> float:
        total = 0.0
        for model, (tin, tout) in self.tokens.items():
            pin, pout = PRICES.get(model, PRICES["gpt-4o"])
            total += tin * pin / 1e6 + tout * pout / 1e6
        return total

    def stats(self) -> dict:
        return {"calls": self.calls, "cost_usd": round(self.cost_usd(), 4),
                "tokens": {m: {"in": t[0], "out": t[1]} for m, t in self.tokens.items()}}

    # -- запросы --------------------------------------------------------------
    def ask(self, role: str, system: str, user: str, req_id: str,
            max_tokens: int | None = None) -> str:
        """Один запрос; role = document | page выбирает модель."""
        model = self.model_document if role == "document" else self.model_page
        out = self.client._ask({
            "id": req_id, "system": system, "user": user,
            "model": model, "json_mode": True,
            "max_tokens": max_tokens or self.max_tokens,
        })
        self._account()
        return out

    def ask_json(self, role: str, system: str, user: str, req_id: str,
                 max_tokens: int | None = None) -> dict | list | None:
        """Запрос с разбором JSON; одна корректирующая попытка при битом JSON."""
        out = self.ask(role, system, user, req_id, max_tokens)
        data = parse_json(out)
        if data is not None:
            return data
        log.warning("%s: битый JSON, корректирующий запрос", req_id)
        fix_user = (user + "\n\nYour previous reply was not valid JSON. "
                    "Reply with ONLY the JSON object, no markdown, no text around it.")
        out = self.ask(role, system, fix_user, req_id + "_fix", max_tokens)
        data = parse_json(out)
        if data is None:
            log.error("%s: JSON не получен после коррекции", req_id)
        return data

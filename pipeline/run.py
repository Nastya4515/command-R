"""Запуск конвейера: python -m pipeline.run --set dev [--step fragments] [--only D001 D002]

Шаги: read_pdf -> fragments -> model -> assemble -> export -> check
Каждый шаг читает файлы предыдущего из cache/ — любой можно перезапустить отдельно.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

from . import assemble, export, fragments, model_client, read_pdf

STEPS = ["read_pdf", "fragments", "model", "assemble", "export", "check"]

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("run")


def load_config(path: str = "config.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _journal(cfg: dict, entry: dict) -> None:
    logs_dir = Path(cfg["work"]["logs_dir"])
    logs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d")
    with open(logs_dir / f"run_{stamp}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.now().isoformat(timespec="seconds"), **entry},
                           ensure_ascii=False) + "\n")


def run_checker(set_name: str, cfg: dict) -> int:
    """Внешняя проверка формата: tools/check_submission.py."""
    import subprocess

    checker = Path(cfg["data"]["checker"])
    out_dir = Path(cfg["work"]["out_dir"]) / set_name
    pdf_dir = Path(cfg["data"][f"{set_name}_dir"])
    report = Path(cfg["work"]["reports_dir"]) / f"check_{set_name}.json"
    cmd = [sys.executable, str(checker), str(out_dir), str(pdf_dir), "--json-report", str(report)]
    log.info("Запуск: %s", " ".join(cmd))
    result = subprocess.run(cmd, check=False)
    return result.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Конвейер извлечения данных из PDF")
    parser.add_argument("--set", dest="set_name", choices=["dev", "test", "uploads"], required=True)
    parser.add_argument("--step", choices=STEPS, help="только один шаг (по умолчанию все)")
    parser.add_argument("--only", nargs="*", help="только эти статьи, напр. D001 D002")
    args = parser.parse_args()

    cfg = load_config()
    steps = [args.step] if args.step else STEPS
    started = time.time()

    for step in steps:
        log.info("=== Шаг %s (набор %s) ===", step, args.set_name)
        try:
            if step == "read_pdf":
                read_pdf.run(args.set_name, cfg, args.only)
            elif step == "fragments":
                fragments.run(args.set_name, cfg, args.only)
            elif step == "model":
                model_client.run(args.set_name, cfg, args.only)
            elif step == "assemble":
                assemble.run(args.set_name, cfg, args.only)
            elif step == "export":
                export.run(args.set_name, cfg, args.only)
            elif step == "check":
                code = run_checker(args.set_name, cfg)
                _journal(cfg, {"step": "check", "set": args.set_name, "exit_code": code})
                if code == 1:
                    log.error("check_submission: ошибки формата, см. отчёт")
        except Exception as exc:
            _journal(cfg, {"step": step, "set": args.set_name, "error": str(exc)})
            raise
        _journal(cfg, {"step": step, "set": args.set_name, "ok": True})

    log.info("Готово за %.1f с", time.time() - started)


if __name__ == "__main__":
    main()

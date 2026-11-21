"""FastAPI-бэкенд: CSV (out/<set>) -> DuckDB -> REST API для фронтенда.

Запуск: uvicorn backend.main:app --port 8000
Документация API: /docs
"""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import duckdb
import yaml
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

ROOT = Path(__file__).resolve().parent.parent
with open(ROOT / "config.yaml", encoding="utf-8") as f:
    CFG = yaml.safe_load(f)

DATASET = "dev"  # набор данных по умолчанию; переключается при полном прогоне
OUT_DIR = ROOT / CFG["work"]["out_dir"] / DATASET
UPLOAD_DIR = ROOT / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_FILE_SIZE = 50 * 1024 * 1024

db = duckdb.connect(":memory:")
app = FastAPI(title="RAG Extraction API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

TABLES = ["publications", "configurations", "datasets", "tasks", "experiments", "results", "issues"]


def load_csvs(out_dir: Path = OUT_DIR, con=None) -> None:
    """Загрузить 7 CSV в DuckDB (все поля — строки; пустое = '').

    con — отдельный курсор для вызова из фонового потока (коннект DuckDB
    не потокобезопасен, курсоры — да).
    """
    conn = con or db
    for table in TABLES:
        path = out_dir / f"{table}.csv"
        if not path.exists():
            continue
        conn.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_csv(?, all_varchar=true)", [str(path)])


load_csvs()


def _rows(sql: str, params: list | None = None) -> list[dict]:
    cur = db.execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


@app.get("/api/stats")
def stats() -> dict:
    """Сводка для экрана «Обзор»."""
    pubs = db.execute("SELECT count(*) FROM publications").fetchone()[0]
    results = db.execute("SELECT count(*) FROM results").fetchone()[0]
    issues = db.execute("SELECT count(*) FROM issues").fetchone()[0]
    cited = db.execute(
        "SELECT count(*) FROM results WHERE result_origin='cited'").fetchone()[0]
    return {"publications": pubs, "results": results, "issues": issues,
            "cited": cited, "dataset": DATASET}


@app.get("/api/facets")
def facets() -> dict:
    """Списки значений для фильтров."""
    metrics = [r[0] for r in db.execute(
        "SELECT DISTINCT metric_name FROM results ORDER BY 1").fetchall()]
    checks = [r[0] for r in db.execute(
        "SELECT DISTINCT check_name FROM issues ORDER BY 1").fetchall()]
    pubs = [r[0] for r in db.execute(
        "SELECT publication_id FROM publications ORDER BY 1").fetchall()]
    return {"metrics": metrics, "check_names": checks, "publications": pubs,
            "origins": ["primary", "cited"]}


@app.get("/api/results")
def results(
    q: str = "", metric: str = "", origin: str = "", pid: str = "",
    with_issues: bool = False,
    min_value: float | None = None, max_value: float | None = None,
    sort: str = "result_id", direction: str = "asc",
    page: int = 1, per_page: int = 20,
) -> dict:
    """Результаты с фильтрами, сортировкой и пагинацией."""
    where, params = ["1=1"], []
    if q:
        where.append("(metric_name ILIKE ? OR source_fragment ILIKE ? OR result_id ILIKE ?)")
        params += [f"%{q}%"] * 3
    if metric:
        where.append("metric_name = ?")
        params.append(metric)
    if origin:
        where.append("result_origin = ?")
        params.append(origin)
    if pid:
        where.append("publication_id = ?")
        params.append(pid)
    if with_issues:
        where.append("""EXISTS (SELECT 1 FROM issues i
                        WHERE i.publication_id = r.publication_id
                          AND strpos(i.record_ids, r.result_id) > 0)""")
    if min_value is not None:
        where.append("TRY_CAST(metric_value AS DOUBLE) >= ?")
        params.append(min_value)
    if max_value is not None:
        where.append("TRY_CAST(metric_value AS DOUBLE) <= ?")
        params.append(max_value)
    sortable = {"result_id", "metric_name", "metric_value", "source_page", "publication_id"}
    sort_col = sort if sort in sortable else "result_id"
    order = "DESC" if direction == "desc" else "ASC"
    value_expr = "TRY_CAST(metric_value AS DOUBLE)" if sort_col == "metric_value" else sort_col
    where_sql = " AND ".join(where)

    total = db.execute(f"SELECT count(*) FROM results r WHERE {where_sql}", params).fetchone()[0]
    rows = _rows(
        f"""SELECT * FROM results r WHERE {where_sql}
            ORDER BY {value_expr} {order} NULLS LAST
            LIMIT ? OFFSET ?""",
        params + [per_page, (page - 1) * per_page])
    return {"total": total, "page": page, "per_page": per_page, "items": rows}


@app.get("/api/results/{pid}/{rid}")
def result_card(pid: str, rid: str) -> dict:
    """Карточка записи со связями и замечаниями."""
    found = _rows("SELECT * FROM results WHERE publication_id=? AND result_id=?", [pid, rid])
    if not found:
        raise HTTPException(404, "Запись не найдена")
    record = found[0]
    config = _rows("SELECT * FROM configurations WHERE publication_id=? AND config_id=?",
                   [pid, record["config_id"]]) if record["config_id"] else []
    issues = _rows("SELECT * FROM issues WHERE publication_id=? AND strpos(record_ids, ?) > 0",
                   [pid, rid])
    duplicates = _rows(
        "SELECT result_id, metric_name, raw_value FROM results WHERE publication_id=? AND duplicate_of=?",
        [pid, rid])
    return {"record": record, "configuration": config[0] if config else None,
            "issues": issues, "duplicates": duplicates}


@app.get("/api/publications")
def publications() -> list[dict]:
    return _rows("SELECT * FROM publications ORDER BY publication_id")


@app.get("/api/publications/{pid}")
def publication(pid: str) -> dict:
    found = _rows("SELECT * FROM publications WHERE publication_id=?", [pid])
    if not found:
        raise HTTPException(404, "Статья не найдена")
    return {
        "publication": found[0],
        "configurations": _rows("SELECT * FROM configurations WHERE publication_id=?", [pid]),
        "datasets": _rows("SELECT * FROM datasets WHERE publication_id=?", [pid]),
        "results_count": db.execute(
            "SELECT count(*) FROM results WHERE publication_id=?", [pid]).fetchone()[0],
    }


@app.get("/api/tables/{table}")
def table_rows(table: str, pid: str = "", page: int = 1, per_page: int = 20) -> dict:
    """Любая из 7 таблиц набора построчно (для экрана «Таблицы»)."""
    if table not in TABLES:
        raise HTTPException(404, f"Таблица должна быть одной из: {', '.join(TABLES)}")
    where, params = "1=1", []
    if pid:
        where, params = "publication_id = ?", [pid]
    total = db.execute(f"SELECT count(*) FROM {table} WHERE {where}", params).fetchone()[0]
    rows = _rows(f"SELECT * FROM {table} WHERE {where} LIMIT ? OFFSET ?",
                 params + [per_page, (page - 1) * per_page])
    return {"table": table, "total": total, "page": page, "per_page": per_page,
            "columns": list(rows[0].keys()) if rows else [], "items": rows}


@app.get("/api/issues")
def issues(check_name: str = "", pid: str = "", page: int = 1, per_page: int = 50) -> dict:
    """Замечания проверки с фильтром по правилу и статье."""
    where, params = ["1=1"], []
    if check_name:
        where.append("check_name = ?")
        params.append(check_name)
    if pid:
        where.append("publication_id = ?")
        params.append(pid)
    where_sql = " AND ".join(where)
    total = db.execute(f"SELECT count(*) FROM issues WHERE {where_sql}", params).fetchone()[0]
    rows = _rows(f"""SELECT * FROM issues WHERE {where_sql}
                     ORDER BY publication_id, issue_id LIMIT ? OFFSET ?""",
                 params + [per_page, (page - 1) * per_page])
    return {"total": total, "page": page, "items": rows}


@app.get("/api/pdf/{pid}")
def pdf(pid: str) -> FileResponse:
    """PDF-файл статьи для просмотрщика."""
    for set_dir in (CFG["data"]["dev_dir"], CFG["data"]["test_dir"], CFG["data"]["uploads_dir"]):
        path = ROOT / set_dir / f"{pid}.pdf"
        if path.exists():
            return FileResponse(path, media_type="application/pdf")
    raise HTTPException(404, "PDF не найден")


@app.get("/api/export")
def export_csv(q: str = "", metric: str = "", origin: str = "", pid: str = "") -> StreamingResponse:
    """CSV по текущим фильтрам (упрощённый набор колонок)."""
    data = results(q=q, metric=metric, origin=origin, pid=pid, per_page=100000)
    columns = ["publication_id", "result_id", "metric_name", "metric_k", "raw_value",
               "metric_value", "metric_unit", "result_origin", "source_page",
               "source_table", "source_fragment"]

    def gen():
        yield ",".join(columns) + "\n"
        for row in data["items"]:
            yield ",".join(f'"{str(row.get(c) or "").replace(chr(34), chr(34) * 2)}"' for c in columns) + "\n"

    return StreamingResponse(gen(), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=results.csv"})


# --- Фоновые задачи: загрузка PDF -> конвейер -> слияние в рабочий набор ---

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()


def _invalidate_cache(pid: str) -> None:
    """Удалить кэш статьи, чтобы повторная загрузка пересчитывалась с нуля."""
    cache = ROOT / CFG["work"]["cache_dir"]
    for sub in ("pages", "fragments", "records"):
        cached = cache / sub / f"{pid}.json"
        if cached.exists():
            cached.unlink()
    responses = cache / "model" / "responses.jsonl"
    if responses.exists():
        kept = []
        for line in responses.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            if not json.loads(line)["id"].startswith(f"{pid}_"):
                kept.append(line)
        responses.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")


def _merge_publication(pid: str) -> None:
    """Перенести строки статьи из out/uploads в out/dev (заменяя старые)."""
    src = ROOT / CFG["work"]["out_dir"] / "uploads"
    dst = OUT_DIR  # сливаем в набор, который сейчас смотрит сайт
    dst.mkdir(parents=True, exist_ok=True)
    for table in TABLES:
        src_path = src / f"{table}.csv"
        if not src_path.exists():
            continue
        with open(src_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            new_rows = [r for r in reader if r.get("publication_id") == pid]
        existing = []
        dst_path = dst / f"{table}.csv"
        if dst_path.exists():
            with open(dst_path, encoding="utf-8") as f:
                existing = [r for r in csv.DictReader(f) if r.get("publication_id") != pid]
        with open(dst_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(existing + new_rows)


def _run_pipeline_job(job_id: str, pid: str) -> None:
    """Фон: конвейер для одной статьи -> слияние в dev -> перезагрузка DuckDB."""
    job = JOBS[job_id]
    job["status"] = "running"
    try:
        _invalidate_cache(pid)
        cmd = [sys.executable, "-m", "pipeline.run", "--set", "uploads", "--only", pid]
        proc = subprocess.Popen(
            cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace")
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            with JOBS_LOCK:
                job["log"].append(line)
            step = re.search(r"=== Шаг (\w+)", line)
            if step:
                job["step"] = step.group(1)
        if proc.wait() != 0:
            job["status"] = "error"
            job["error"] = "конвейер завершился с ошибкой (см. лог)"
            return
        _merge_publication(pid)
        con = db.cursor()
        load_csvs(OUT_DIR, con=con)
        job["results_count"] = con.execute(
            "SELECT count(*) FROM results WHERE publication_id=?", [pid]).fetchone()[0]
        job["status"] = "done"
    except Exception as exc:  # noqa: BLE001 — ошибку показываем пользователю
        job["status"] = "error"
        job["error"] = str(exc)


@app.post("/api/upload", status_code=201)
async def upload(file: UploadFile) -> dict:
    """Загрузка PDF: сохранение + запуск конвейера в фоне.

    Имя статьи (publication_id) = имя файла без расширения. В mock-режиме
    разметка появится только для статей эталона (D001..D021).
    """
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Разрешены только PDF-файлы")
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, "Файл слишком большой (максимум 50 МБ)")
    stem = Path(file.filename or "file.pdf").stem
    pid = "".join(c if c.isalnum() or c in ".-_" else "_" for c in stem) or "file"
    target = UPLOAD_DIR / f"{pid}.pdf"
    target.write_bytes(content)

    for old in JOBS.values():  # не гонять два прогона одной статьи параллельно
        if old["pid"] == pid and old["status"] in ("queued", "running"):
            raise HTTPException(409, f"Статья {pid} уже обрабатывается")

    job_id = uuid.uuid4().hex[:8]
    JOBS[job_id] = {"job_id": job_id, "pid": pid, "status": "queued", "step": "",
                    "log": [], "error": "", "results_count": 0,
                    "started": time.time()}
    threading.Thread(target=_run_pipeline_job, args=(job_id, pid), daemon=True).start()
    return {"job_id": job_id, "pid": pid, "originalName": file.filename,
            "size": len(content)}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    """Статус фоновой обработки загруженной статьи."""
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Задача не найдена")
    with JOBS_LOCK:
        log_tail = job["log"][-30:]
    return {**{k: v for k, v in job.items() if k != "log"}, "log": log_tail}


@app.post("/api/reload")
def reload_data(out_dir: str = "") -> dict:
    """Перезагрузить CSV в DuckDB (после нового прогона конвейера)."""
    global OUT_DIR, DATASET
    if out_dir:
        OUT_DIR = ROOT / out_dir
        DATASET = Path(out_dir).name
    load_csvs(OUT_DIR)
    return {"reloaded": str(OUT_DIR)}

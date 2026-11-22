"""FastAPI-бэкенд v2: CSV (out/<area>/<set>) -> DuckDB -> REST API для фронтенда.

Две предметные области кейса ВИНИТИ (rag, solar), у каждой — свой набор из 7 таблиц
(схема из domains/<area>/profile.yaml). Текущие область и набор переключаются
через /api/select; все остальные эндпоинты работают с текущей парой.

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

sys.path.insert(0, str(ROOT))
from pipeline.v2.profile import load_profile  # noqa: E402

AREAS = ("rag", "solar")
PROFILES: dict[str, dict] = {}
for _a in AREAS:
    try:
        PROFILES[_a] = load_profile(_a)
    except Exception:
        pass

UPLOAD_DIR = ROOT / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_FILE_SIZE = 50 * 1024 * 1024

# Текущая просматриваемая пара (область, набор)
CURRENT = {"area": "rag", "set": "test"}

db = duckdb.connect(":memory:")
app = FastAPI(title="VINITI Extraction API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def area_tables(area: str) -> list[str]:
    return list(PROFILES[area]["schema"]["tables"])


def _available_sets(area: str) -> list[str]:
    out = ROOT / CFG["work"]["out_dir"] / area
    return sorted(p.name for p in out.iterdir() if p.is_dir()) if out.exists() else []


def load_csvs(area: str | None = None, set_name: str | None = None, con=None) -> None:
    """Загрузить CSV текущей пары (область, набор) в DuckDB.

    Отсутствующие таблицы создаются пустыми с колонками из схемы области —
    сайт стартует и без прогона. con — отдельный курсор для фонового потока.
    """
    area = area or CURRENT["area"]
    set_name = set_name or CURRENT["set"]
    out_dir = ROOT / CFG["work"]["out_dir"] / area / set_name
    conn = con or db
    for table in area_tables(area):
        cols = PROFILES[area]["schema"]["tables"][table]
        path = out_dir / f"{table}.csv"
        if path.exists():
            conn.execute(
                f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_csv(?, all_varchar=true)",
                [str(path)])
        else:
            conn.execute(f"CREATE OR REPLACE TABLE {table} ("
                         + ", ".join(f'"{c}" VARCHAR' for c in cols) + ")")


load_csvs()


def _rows(sql: str, params: list | None = None) -> list[dict]:
    cur = db.cursor().execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


@app.get("/api/areas")
def areas() -> dict:
    """Области, их таблицы и доступные наборы (для переключателя в шапке)."""
    return {
        "current": dict(CURRENT),
        "areas": [
            {"id": a, "tables": area_tables(a), "sets": _available_sets(a)}
            for a in PROFILES
        ],
    }


@app.post("/api/select")
def select(area: str, set_name: str) -> dict:
    """Переключить просматриваемую пару (область, набор) и перезагрузить данные."""
    if area not in PROFILES:
        raise HTTPException(404, f"Область должна быть одной из: {', '.join(PROFILES)}")
    CURRENT["area"] = area
    CURRENT["set"] = set_name
    load_csvs()
    return {"current": dict(CURRENT)}


@app.get("/api/stats")
def stats() -> dict:
    """Сводка для экрана «Обзор»."""
    pubs = db.cursor().execute("SELECT count(*) FROM publications").fetchone()[0]
    results = db.cursor().execute("SELECT count(*) FROM results").fetchone()[0]
    issues = db.cursor().execute("SELECT count(*) FROM issues").fetchone()[0]
    cited = db.cursor().execute(
        "SELECT count(*) FROM results WHERE result_origin='cited'").fetchone()[0]
    return {"publications": pubs, "results": results, "issues": issues,
            "cited": cited, "area": CURRENT["area"], "dataset": CURRENT["set"]}


@app.get("/api/facets")
def facets() -> dict:
    """Списки значений для фильтров."""
    metrics = [r[0] for r in db.cursor().execute(
        "SELECT DISTINCT metric_name FROM results ORDER BY 1").fetchall()]
    checks = [r[0] for r in db.cursor().execute(
        "SELECT DISTINCT check_name FROM issues ORDER BY 1").fetchall()]
    pubs = [r[0] for r in db.cursor().execute(
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

    total = db.cursor().execute(f"SELECT count(*) FROM results r WHERE {where_sql}", params).fetchone()[0]
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
    issues = _rows("SELECT * FROM issues WHERE publication_id=? AND strpos(record_ids, ?) > 0",
                   [pid, rid])
    duplicates = _rows(
        "SELECT result_id, metric_name, raw_value FROM results WHERE publication_id=? AND duplicate_of=?",
        [pid, rid])
    # связанная сущность: по config_id (rag) или device_id (solar)
    linked = None
    if record.get("config_id") and "configurations" in area_tables(CURRENT["area"]):
        rows = _rows("SELECT * FROM configurations WHERE publication_id=? AND config_id=?",
                     [pid, record["config_id"]])
        linked = rows[0] if rows else None
    elif record.get("device_id") and "devices" in area_tables(CURRENT["area"]):
        rows = _rows("SELECT * FROM devices WHERE publication_id=? AND device_id=?",
                     [pid, record["device_id"]])
        linked = rows[0] if rows else None
    return {"record": record, "linked": linked,
            "issues": issues, "duplicates": duplicates}


@app.get("/api/publications")
def publications() -> list[dict]:
    return _rows("SELECT * FROM publications ORDER BY publication_id")


@app.get("/api/publications/{pid}")
def publication(pid: str) -> dict:
    found = _rows("SELECT * FROM publications WHERE publication_id=?", [pid])
    if not found:
        raise HTTPException(404, "Статья не найдена")
    out = {
        "publication": found[0],
        "results_count": db.cursor().execute(
            "SELECT count(*) FROM results WHERE publication_id=?", [pid]).fetchone()[0],
    }
    for table in area_tables(CURRENT["area"]):
        if table in ("publications", "results", "issues"):
            continue
        out[table] = _rows(f"SELECT * FROM {table} WHERE publication_id=?", [pid])
    return out


@app.get("/api/tables/{table}")
def table_rows(table: str, pid: str = "", page: int = 1, per_page: int = 20) -> dict:
    """Любая из таблиц текущей области построчно (для экрана «Таблицы»)."""
    tables = area_tables(CURRENT["area"])
    if table not in tables:
        raise HTTPException(404, f"Таблица должна быть одной из: {', '.join(tables)}")
    where, params = "1=1", []
    if pid:
        where, params = "publication_id = ?", [pid]
    total = db.cursor().execute(f"SELECT count(*) FROM {table} WHERE {where}", params).fetchone()[0]
    rows = _rows(f"SELECT * FROM {table} WHERE {where} LIMIT ? OFFSET ?",
                 params + [per_page, (page - 1) * per_page])
    columns = PROFILES[CURRENT["area"]]["schema"]["tables"][table]
    return {"table": table, "total": total, "page": page, "per_page": per_page,
            "columns": columns, "items": rows}


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
    total = db.cursor().execute(f"SELECT count(*) FROM issues WHERE {where_sql}", params).fetchone()[0]
    rows = _rows(f"""SELECT * FROM issues WHERE {where_sql}
                     ORDER BY publication_id, issue_id LIMIT ? OFFSET ?""",
                 params + [per_page, (page - 1) * per_page])
    return {"total": total, "page": page, "items": rows}


@app.get("/api/pdf/{pid}")
def pdf(pid: str) -> FileResponse:
    """PDF-файл статьи для просмотрщика (dev/test/uploads текущей области)."""
    area = CURRENT["area"]
    data_cfg = CFG["data"] if area == "rag" else CFG["data"][area]
    for set_dir in (data_cfg.get("dev_dir"), data_cfg.get("test_dir"), CFG["data"]["uploads_dir"]):
        if not set_dir:
            continue
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


# --- Фоновые задачи: загрузка PDF -> конвейер v2 -> набор uploads ---

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()


def _run_pipeline_job(job_id: str, pid: str, area: str) -> None:
    """Фон: конвейер v2 для одной статьи -> экспорт в out/<area>/uploads."""
    job = JOBS[job_id]
    job["status"] = "running"
    try:
        cmd = [sys.executable, "-m", "pipeline.v2.run",
               "--area", area, "--set", "uploads", "--only", pid, "--step", "abcdef"]
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
            step = re.search(r"шаг ([A-F])", line)
            if step:
                job["step"] = step.group(1)
        if proc.wait() != 0:
            job["status"] = "error"
            job["error"] = "конвейер завершился с ошибкой (см. лог)"
            return
        # показываем пользователю набор uploads его области
        CURRENT["area"] = area
        CURRENT["set"] = "uploads"
        con = db.cursor()
        load_csvs(con=con)
        job["results_count"] = con.execute(
            "SELECT count(*) FROM results WHERE publication_id=?", [pid]).fetchone()[0]
        job["status"] = "done"
    except Exception as exc:  # noqa: BLE001 — ошибку показываем пользователю
        job["status"] = "error"
        job["error"] = str(exc)


@app.post("/api/upload", status_code=201)
async def upload(file: UploadFile, area: str = "rag") -> dict:
    """Загрузка PDF: сохранение + запуск конвейера v2 в фоне.

    Имя статьи (publication_id) = имя файла без расширения. Область (rag/solar)
    выбирает пользователь в интерфейсе загрузки.
    """
    if area not in PROFILES:
        raise HTTPException(400, f"Область должна быть одной из: {', '.join(PROFILES)}")
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
    JOBS[job_id] = {"job_id": job_id, "pid": pid, "area": area, "status": "queued",
                    "step": "", "log": [], "error": "", "results_count": 0,
                    "started": time.time()}
    threading.Thread(target=_run_pipeline_job, args=(job_id, pid, area), daemon=True).start()
    return {"job_id": job_id, "pid": pid, "area": area,
            "originalName": file.filename, "size": len(content)}


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
def reload_data() -> dict:
    """Перезагрузить CSV текущей пары в DuckDB (после нового прогона конвейера)."""
    load_csvs()
    return {"reloaded": f"{CURRENT['area']}/{CURRENT['set']}"}

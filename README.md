# RAG Extraction — конвейер извлечения данных из научных статей

Кейс ВИНИТИ РАН, предметная область 2 (Retrieval-Augmented Generation).

Система читает PDF научных статей, извлекает конфигурации RAG-систем и
результаты их оценки (метрика, значение, страница, дословная цитата) и
собирает 7 связанных CSV формата сдачи. Веб-интерфейс: поиск, фильтры,
карточки записей, просмотр PDF на странице источника, загрузка новых статей.

## Быстрый старт

Требования: Python 3.11+, Node.js 18+, ключ OpenAI (для разметки новых статей).

```bash
# 1. Окружение Python
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
# .venv/bin/python -m pip install -r requirements.txt          # Linux/macOS

# 2. Ключи
copy .env.example .env   # и вписать OPENAI_API_KEY

# 3. Данные (выдают организаторы) — положить в data/:
#    data/dev/*.pdf, data/test/*.pdf, data/dev_gold/*.csv
#    data/submission_template/, data/tools/check_submission.py

# 4. Бэкенд (порт 8000)
npm run server
# или: .venv/Scripts/python.exe -m uvicorn backend.main:app --port 8000

# 5. Фронтенд (порт 5173, прокси /api -> 8000)
npm install
npm run dev
```

Открыть http://localhost:5173 — сайт стартует пустым; загрузите PDF на
вкладке «Загрузка» (drag-and-drop), через несколько минут статья появится
в базе. Демо-данные dev-набора: `POST http://localhost:8000/api/reload?out_dir=out/dev`.

## Конвейер

```bash
# полный прогон набора (шаги: read_pdf -> fragments -> model -> assemble -> export -> check)
.venv/Scripts/python.exe -m pipeline.run --set test

# отдельные шаги / статьи
.venv/Scripts/python.exe -m pipeline.run --set dev --only D001 --step fragments

# оценка качества на dev (против dev_gold)
.venv/Scripts/python.exe -m pipeline.score

# проверка формата сдачи
.venv/Scripts/python.exe data/tools/check_submission.py out/test test
```

Каждый шаг кэшируется в `cache/` — повторный запуск продолжает с места сбоя,
ответы модели не тратятся повторно. Прогон test (90 статей) ≈ $1 и 4–5 часов
на gpt-4o-mini.

## Конфигурация (config.yaml)

- `model.client`: `api` (OpenAI, по умолчанию) | `mock` (ответы из dev_gold,
  разработка без нейросети) | `file` (обмен jsonl с командой ИИ) | `local` (LoRA).
- `model.api`: модель, параллелизм (8), таймауты, повторы.
- `pdf.ocr_backend: vision` — сканы и PDF с битой кодировкой шрифтов
  автоматически уходят в vision-OCR (gpt-4o-mini), Tesseract не нужен.

## Проверки перед коммитом

```bash
.venv/Scripts/python.exe -m pytest tests/ -q     # 16 тестов
.venv/Scripts/python.exe -m ruff check pipeline backend tests
npx eslint src/App.jsx
npx vite build
```

## Структура

```
pipeline/   read_pdf, fragments, model_client (api/mock/file/local),
            assemble, checks, export, score, vision_ocr, dataset, train_sft
backend/    FastAPI + DuckDB: 8 эндпоинтов + /api/upload (фоновая разметка)
src/        React + Vite + Tailwind: Обзор/Данные/Замечания/Публикации/Загрузка
data/       dev/ test/ (PDF, не в git), dev_gold/, submission_template/, tools/
docs/       TZ_MVP.md — ТЗ на доработку MVP
tests/      pytest (16 шт.)
```

Не в git: `.env` (ключи), `data/dev`, `data/test` (PDF организаторов),
`cache/`, `out/`, `logs/`, `models/`, `uploads/`.

## Траблшутинг

| Симптом | Решение |
|---|---|
| «Бекенд недоступен» | `npm run server` не запущен или порт 8000 занят |
| PDF открывается в браузере при дропе | старая страница — Ctrl+F5 |
| Статья дала 0–5 результатов | проверьте, не обзорная ли она; сканы уходят в vision-OCR автоматически |
| Сбой посреди прогона | просто перезапустите команду — кэш продолжит с места |
| fontTools warnings | безобидны; `pip install fonttools` убирает |

## Дообучение своей модели (опционально)

`requirements-ml.txt` + `pipeline/dataset.py` (SFT-датасет из dev_gold) +
`pipeline/train_sft.py` (QLoRA на Qwen2.5-3B, ~8 ГБ VRAM) +
`model.client: local`. Подробности — в `docs/TZ_MVP.md`.

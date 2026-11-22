# ВИНИТИ — конвейер извлечения данных из научных статей

Кейс 5 ВИНИТИ РАН (хакатон «Глубокая генерация»): извлечение и структурирование
данных из научных публикаций. Две предметные области:

- **rag** — Retrieval-Augmented Generation (таблицы: publications, configurations,
  datasets, tasks, experiments, results, issues);
- **solar** — тонкоплёночные солнечные элементы (таблицы: publications, materials,
  devices, layers, measurements, results, issues).

Система читает PDF, извлекает сущности и численные результаты (метрика, значение,
страница, дословная цитата), проверяет их встроенными правилами и собирает 7 CSV
эталонного формата. Веб-интерфейс: переключение области и набора, все 7 таблиц,
поиск и фильтры по результатам, карточки записей, PDF на странице источника,
загрузка новых статей.

## Быстрый старт

Требования: Python 3.11+, Node.js 18+, ключ OpenAI-совместимого API.

```bash
# 1. Окружение Python
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
# .venv/bin/python -m pip install -r requirements.txt          # Linux/macOS

# 2. Ключи
copy .env.example .env   # и вписать OPENAI_API_KEY

# 3. Данные организаторов — в data/<area>/:
#    data/rag/{dev,test,dev_gold,submission_template,tools}/
#    data/solar/{dev,test,dev_gold,submission_template,tools}/

# 4. Бэкенд (порт 8000)
.venv/Scripts/python.exe -m uvicorn backend.main:app --port 8000

# 5. Фронтенд (порт 5173, прокси /api -> 8000)
npm install
npm run dev
```

Открыть http://localhost:5173. Переключатель области и набора — в шапке.
Загрузка своей статьи: вкладка «Загрузка», выбор области, drag-and-drop PDF;
статья появляется в наборе `uploads` соответствующей области.

## Конвейер v2

```bash
# полный прогон набора области (шаги A–F)
.venv/Scripts/python.exe -m pipeline.v2.run --area rag --set test

# отдельные статьи / шаги (a — документ, b — страницы, c — сверка цитат,
# d — нормализация, e — проверки, f — экспорт + чекер организаторов)
.venv/Scripts/python.exe -m pipeline.v2.run --area solar --set dev --only D001 --step bcde

# оценка качества на dev (против dev_gold)
.venv/Scripts/python.exe -m pipeline.v2.score --area rag --only D001 D004 D005
```

Шаги конвейера:

- **A. Документ** — библиография, in_scope, сущности области (конфигурации RAG /
  материалы-устройства-слои-измерения Solar), один запрос на статью.
- **B. Страницы** — результаты с дословными цитатами; плотные таблицы
  разбираются построчно (строка + заголовок таблицы отдельным запросом).
- **C. Сверка** — цитата ищется в тексте PDF нормой чекера организаторов
  (NFKC, склейка переносов), значение — в цитате; не прошло — один
  корректирующий запрос, затем отклонение в rejected.json.
- **D. Нормализация** — единицы и пересчёты по профилю, канонизация имён
  метрик по словарю dev-эталона, metric_direction, metric_k, duplicate_of.
- **E. Проверки** — общие (metric_scale, unit_inconsistency, contradiction,
  percentage_vs_percentage_point) + предметные Solar (jv_consistency,
  voc_limit, диапазоны, eqe_consistency, champion_vs_mean).
- **F. Экспорт** — 7 CSV строго по schema.json области + запуск чекера
  организаторов (data/<area>/tools/check_submission.py).

Предметная специфика — только в `domains/<area>/` (profile.yaml, промпты);
ядро `pipeline/v2/` от области не зависит.

## Оценка качества (dev, против эталона организаторов)

Замер на трёх статьях RAG (сопоставление: статья + страница + значение
с допуском округления + нормализованное имя метрики):

| Статья | Precision | Recall | F1 |
|---|---|---|---|
| D001 | 72,0% | 44,4% | 54,9% |
| D004 | 23,7% | 15,9% | 19,1% |
| D005 | 29,6% | 15,3% | 20,2% |

Solar (D001–D004): precision 47,1%, recall 23,5%, F1 31,4%; in_scope 4/4.

Значения, читаемые только с графиков (source_figure), конвейер не
оцифровывает — это главный ограничитель recall (у Solar 81% эталона).
Отчёты: `reports/`, паспорта наборов: `docs/passport_*.md`.

## Итоговые прогоны test (по 90 статей на область)

- **RAG**: 20 312 результатов, чекер организаторов — 0 ошибок (код 2,
  только предупреждения); цитаты совпали 18 547/23 245.
- **Solar**: 5 171 результат, чекер — 0 ошибок (код 0); цитаты 5 977/6 705.

## Структура

```
backend/main.py       FastAPI: CSV -> DuckDB -> REST (области, таблицы, загрузка)
pipeline/v2/          ядро конвейера (profile, llm, pages, extract_a/b, verify,
                      normalize, checks, checks_solar, export, score, run)
domains/<area>/       профили областей: profile.yaml + промпты
data/<area>/          данные организаторов (dev/test/dev_gold/шаблон/чекер)
out/<area>/<set>/     результат прогона: 7 CSV
cache/                кэш страниц и ответов модели
src/                  React-интерфейс
docs/                 ТЗ (TZ_v2.md), паспорта наборов
```

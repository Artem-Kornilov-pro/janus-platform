# Инструкция по установке и запуску

Это руководство описывает запуск Janus Platform локально на Windows
(PowerShell), с примечаниями для macOS/Linux там, где есть отличия.

## Требования

- **Python 3.12+**
- **Docker Desktop** (для Neo4j)
- **Tesseract OCR** (для поддержки сканированных PDF в Document Brain) — на
  Windows установите с https://github.com/UB-Mannheim/tesseract/wiki и
  убедитесь, что `tesseract.exe` доступен в `PATH`. На Linux:
  `apt-get install tesseract-ocr tesseract-ocr-rus`.
- Аккаунт **Yandex Cloud** с ID каталога (folder) и API-ключом (для LLM).

## 1. Клонирование и создание виртуального окружения

```powershell
git clone https://github.com/Artem-Kornilov-pro/janus-platform.git
cd janus-platform
python -m venv .venv
.venv\Scripts\Activate.ps1
```

## 2. Установка зависимостей

```powershell
pip install -r requirements.txt
```

Сюда входят основные библиотеки, PyQt6 (фронтенд) и инструменты для
разработки/тестов (`pytest`, `pytest-asyncio`). Альтернативно, через
`pyproject.toml`:

```powershell
pip install -e ".[frontend,dev]"
```

## 3. Настройка переменных окружения

Скопируйте файл-пример и заполните своими реквизитами:

```powershell
copy .env.example .env
```

Отредактируйте `.env`:

```dotenv
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=janustest123

YANDEX_CLOUD_FOLDER=<ваш folder id>
YANDEX_CLOUD_API_KEY=<ваш api key>
YANDEX_CLOUD_MODEL=deepseek-v4-flash/latest

MCP_TRANSPORT=sse
MCP_HOST=127.0.0.1
MCP_PORT=8000

MCP_SERVER_URL=http://localhost:8000/sse
```

> `.env` находится в `.gitignore` — никогда не коммитьте реальные реквизиты.

Процессы Python ниже читают `.env` через переменные окружения вашей
оболочки. В PowerShell загрузить их можно так:

```powershell
Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([^#=]+)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim())
    }
}
```

(или используйте `direnv` / `python-dotenv`, если предпочитаете.)

## 4. Запуск Neo4j

```powershell
docker compose up -d
```

Запускается только сервис `neo4j` (контейнер `janus-neo4j`), с портами:
- `7474` — Neo4j Browser (http://localhost:7474)
- `7687` — протокол Bolt

Дождитесь, пока `docker ps` покажет статус `healthy`.

## 5. Запуск сервера MCP Fabric

Запускайте **локально** (не в Docker), чтобы сервер видел те же пути
файловой системы, что и диалог выбора папки во фронтенде:

```powershell
python -m core.mcp_fabric.server
```

Должно появиться `Uvicorn running on http://127.0.0.1:8000`. Оставьте это
в отдельном терминале.

> Существует опциональный контейнеризированный вариант:
> `docker compose --profile docker up -d`. Используйте его только если вам
> не нужна функция «загрузка папки», либо адаптируйте монтирование томов
> под расположение ваших документов.

## 6. Запуск фронтенда

В новом терминале (с теми же переменными из `.env`):

```powershell
cd frontend
python app.py
```

Откроется окно PyQt6 с четырьмя вкладками: **Чат**, **Документы**,
**Сущности**, **Learning Brain**.

## 7. (Опционально) Загрузка документов из командной строки

```powershell
python janus_ingest.py --folder fixtures/ingestion --recursive
python janus_ingest.py --status <job_id>
```

## 8. (Опционально) Интерактивная разметка извлечений

```powershell
python feedback_cli.py
```

## Запуск тестов

```powershell
pytest -q
```

Все 25+ тестов должны проходить без доступа к Docker/LLM (используются
фикстуры и моки); скрипты в `demo/*.py` — это «живые» smoke-тесты,
требующие Neo4j и реквизитов Yandex Cloud.

## Использование Makefile

Если у вас есть `make` (Git Bash, WSL, macOS, Linux), см.
[Makefile](../../Makefile) для быстрых команд:

```bash
make install      # pip install -r requirements.txt
make up           # docker compose up -d (Neo4j)
make down         # docker compose down
make server       # запустить сервер MCP Fabric локально
make frontend     # запустить фронтенд PyQt6
make test         # запустить pytest
make ingest FOLDER=fixtures/ingestion  # загрузить папку через CLI
```

## Решение проблем

- **`Couldn't connect to localhost:7687`** — контейнер Neo4j не запущен; выполните `docker start janus-neo4j` или `docker compose up -d`.
- **`Could not reach MCP server at http://localhost:8000/sse`** — MCP-сервер не запущен; запустите `python -m core.mcp_fabric.server`.
- **`Error executing tool ingest_folder: ... Couldn't connect to ...:7687`** — то же самое, Neo4j не работает.
- **`'OpenAI' object has no attribute 'responses'` / `Client.__init__() got an unexpected keyword argument 'proxies'`** — версии `openai`/`httpx` не синхронизированы; переустановите через `pip install -r requirements.txt`.
- **Загрузка папки через фронтенд ничего не делает / падает при MCP-сервере в Docker** — запускайте MCP-сервер локально, а не в Docker (см. шаг 5).

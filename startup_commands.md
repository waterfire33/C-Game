# Startup Commands

## Backend local startup
cd "/Users/macbook/workspace/VSCODE CPP/foundation-skeleton/backend"
uvicorn app.main:app --reload

## Backend production-style startup
cd "/Users/macbook/workspace/VSCODE CPP/foundation-skeleton/backend"
uvicorn app.main:app --host 0.0.0.0 --port 8000

## Worker startup
cd "/Users/macbook/workspace/VSCODE CPP/foundation-skeleton/backend"
python -m app.worker.runner

## Backend test command
cd "/Users/macbook/workspace/VSCODE CPP"
ENABLE_TELEMETRY=false DATABASE_URL=sqlite+aiosqlite:///:memory: REDIS_URL=redis://localhost:6379/0 PYTHONPATH=./foundation-skeleton/backend ./.venv/bin/python -m pytest -c pytest.ini foundation-skeleton/backend/tests -v

## Notes
- verify the worker command matches the actual runner entrypoint before production use
- verify uvicorn is the intended production app server or replace with the final server choice
- production deployment should supply environment variables explicitly

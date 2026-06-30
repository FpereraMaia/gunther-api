api: PYTHONPATH=src uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir src
worker: PYTHONPATH=src uv run arq app.worker.WorkerSettings

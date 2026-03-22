.PHONY: dev test lint backtest api

dev:
	docker compose up -d db
	uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000

api:
	uvicorn src.api.app:app --host 0.0.0.0 --port 8000

backtest:
	python -m src.cli.main backtest $(ARGS)

test:
	pytest tests/ -v

lint:
	ruff check src/ tests/
	mypy src/

migrate:
	alembic upgrade head

seed:
	python scripts/seed_data.py

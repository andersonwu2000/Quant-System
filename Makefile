.PHONY: dev test lint backtest api web mobile install-apps start

# === Backend ===

dev:
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

# === Frontend ===

install-apps:
	cd apps && bun install

web:
	cd apps/web && bun run dev

mobile:
	cd apps/mobile && bun start

web-build:
	cd apps/web && bun run build

web-typecheck:
	cd apps/web && bun run typecheck

mobile-typecheck:
	cd apps/mobile && bun run typecheck

# === Full stack ===

start:
	$(MAKE) dev &
	$(MAKE) web

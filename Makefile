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

android:
	cd apps/android && ./gradlew.bat assembleDebug

web-build:
	cd apps/web && bun run build

web-typecheck:
	cd apps/web && bun run typecheck

web-test:
	cd apps/web && bun run test

android-lint:
	cd apps/android && ./gradlew.bat lintDebug

# === Full stack ===

start:
	$(MAKE) dev &
	$(MAKE) web

# === Git Hooks ===

setup-hooks:
	git config core.hooksPath .githooks
	chmod +x .githooks/pre-push
	@echo "✔ Git hooks 已啟用（.githooks/pre-push）"

# 本地執行與 CI 相同的完整檢查
pre-push:
	@bash .githooks/pre-push

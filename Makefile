.PHONY: help backend frontend local docker clean

help:
	@echo "WATCHOUT ISEQL -- three-condition ablation study"
	@echo ""
	@echo "  make backend           - Install Python deps via Pipenv"
	@echo "  make frontend          - Install JS deps via pnpm"
	@echo "  make local             - Run backend + frontend locally (no Docker)"
	@echo "  make docker            - Build and run both services via docker-compose"
	@echo "  make clean             - Remove build artifacts, .db, node_modules, .venv"

backend:
	cd backend && pipenv install --dev

frontend:
	cd frontend && pnpm install

local:
	bash scripts/dev.sh

docker:
	docker compose up --build

clean:
	rm -rf data/analysis.db
	rm -rf frontend/node_modules frontend/.svelte-kit

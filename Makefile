.PHONY: help engine backend frontend local docker clean

help:
	@echo "WATCHOUT ISEQL -- three-condition ablation study"
	@echo ""
	@echo "  make engine            - Build the C++ interval engine (Linux)"
	@echo "  make backend           - Install Python deps via Pipenv"
	@echo "  make frontend          - Install JS deps via pnpm"
	@echo "  make local             - Run backend + frontend locally (no Docker)"
	@echo "  make docker            - Build and run both services via docker-compose"
	@echo "  make clean             - Remove build artifacts, .db, node_modules, .venv"

engine:
	cd interval_engine && ./build.sh

backend:
	cd backend && pipenv install --dev

frontend:
	cd frontend && pnpm install

local: engine
	bash scripts/dev.sh

docker: engine
	docker compose up --build

clean:
	rm -rf interval_engine/build data/analysis.db
	rm -rf frontend/node_modules frontend/.svelte-kit

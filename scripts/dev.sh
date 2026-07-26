#!/usr/bin/env bash
# scripts/dev.sh
# Runs the FastAPI backend (uvicorn) and the SvelteKit frontend (vite dev)
# in parallel, in the same terminal. Ctrl-C stops both.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

cleanup() {
  trap - INT TERM EXIT
  if [[ -n "${BACK_PID:-}" ]] && kill -0 "$BACK_PID" 2>/dev/null; then
    kill "$BACK_PID" 2>/dev/null || true
  fi
  if [[ -n "${FRONT_PID:-}" ]] && kill -0 "$FRONT_PID" 2>/dev/null; then
    kill "$FRONT_PID" 2>/dev/null || true
  fi
  wait 2>/dev/null || true
  echo ""
  echo ">> WATCHOUT ISEQL stopped."
}
trap cleanup INT TERM EXIT

echo ">> Starting WATCHOUT ISEQL in development mode"
echo "   Backend  -> http://localhost:8000  (FastAPI + /docs)"
echo "   Frontend -> http://localhost:5173  (SvelteKit + Vite)"
echo ""

cd "$ROOT/backend"
echo ">> [backend] installing deps if needed..."
pipenv install --dev --quiet 2>/dev/null || true

CUDA_PYTHON="/home/ghiffaryr/anaconda3/envs/py310/bin/python"
export LD_LIBRARY_PATH="/home/ghiffaryr/anaconda3/envs/py310/lib:${LD_LIBRARY_PATH:-}"

if [ -x "$CUDA_PYTHON" ] && LD_LIBRARY_PATH="$LD_LIBRARY_PATH" "$CUDA_PYTHON" -c "import torch; exit(0 if torch.cuda.is_available() else 1)" 2>/dev/null; then
  echo ">> [backend] using conda py310 (CUDA)"
  PYTHON="$CUDA_PYTHON"
  PYPATH="src"
else
  PYTHON="pipenv"
  PYPATH="src"
fi

echo ">> [backend] loading .env and starting uvicorn..."
if [ -f "$ROOT/backend/.env" ]; then
  set -a; source "$ROOT/backend/.env"; set +a
fi
if [ "$PYTHON" = "pipenv" ]; then
  PYTHONPATH="$PYPATH" pipenv run uvicorn start_application:StartApplication \
    --host 0.0.0.0 --port 8000 --reload &
else
  PYTHONPATH="$PYPATH" "$PYTHON" -m uvicorn start_application:StartApplication \
    --host 0.0.0.0 --port 8000 --reload &
fi
BACK_PID=$!

cd "$ROOT/frontend"
echo ">> [frontend] starting vite dev..."
pnpm dev --host 0.0.0.0 --port 5173 &
FRONT_PID=$!

echo ""
echo ">> Both services running. Press Ctrl-C to stop."
wait

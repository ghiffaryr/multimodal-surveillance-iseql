#!/usr/bin/env bash
# scripts/start.sh - unified runner (PROFILE=local|hpc|docker)
# local: auto-detects conda (anaconda3/miniconda3, or installs Miniconda3),
#        ensures conda py310 + ffmpeg, runs backend via pipenv.
# hpc:   backend on the GPU node (SSH tunnel), frontend on the login node.
# Usage: make {local,hpc} or PROFILE=local bash scripts/start.sh backend
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

PROFILE="${PROFILE:-}"
case "$PROFILE" in
  local|hpc|docker|mac) ;;
  "") echo "ERROR: PROFILE not set (use local|hpc|docker|mac)" >&2; exit 2 ;;
  *) echo "ERROR: invalid PROFILE='$PROFILE' (use local|hpc|docker|mac)" >&2; exit 2 ;;
esac

MODE="${1:-all}"
case "$MODE" in
  all|backend|frontend) ;;
  *) echo "ERROR: invalid mode='$MODE' (use all|backend|frontend)" >&2; exit 2 ;;
esac

REMOTE_GPU="${BACKEND_HOST:-}"
if [[ "$PROFILE" == "hpc" && -z "$REMOTE_GPU" ]]; then
  echo "ERROR: BACKEND_HOST is required for PROFILE=hpc (e.g. BACKEND_HOST=compute-0-3)" >&2
  exit 2
fi

# ---- conda bootstrap -------------------------------------------------------
CONDA_BASE=""

find_conda() {
  local candidates=(
    "$HOME/miniconda3" "$HOME/anaconda3" "$HOME/miniconda" "$HOME/anaconda"
    "${CONDA_EXE%/bin/*}" "${CONDA_PREFIX%/envs/*}"
  )
  for c in "${candidates[@]}"; do
    if [ -n "$c" ] && [ -x "$c/bin/conda" ]; then CONDA_BASE="$c"; return; fi
  done
  local cbin
  cbin="$(command -v conda 2>/dev/null || true)"
  if [ -n "$cbin" ]; then CONDA_BASE="$(dirname "$(dirname "$cbin")")"; fi
}

ensure_conda() {
  if [ -z "$CONDA_BASE" ]; then find_conda; fi
  if [ -z "$CONDA_BASE" ]; then
    echo ">> no conda found; installing Miniconda3 to $HOME/miniconda3"
    local url="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
    local inst="$HOME/miniconda3.sh"
    curl -fsSLo "$inst" "$url"
    bash "$inst" -b -p "$HOME/miniconda3"
    rm -f "$inst"
    CONDA_BASE="$HOME/miniconda3"
  fi
  echo ">> conda: $CONDA_BASE"
}

# conda env dir for the pipenv base python + ffmpeg libs
py310_env() { echo "$CONDA_BASE/envs/py310"; }

ensure_ffmpeg() {
  ensure_conda
  local env_dir py
  env_dir="$(py310_env)"
  py="$env_dir/bin/python"
  if [ ! -x "$py" ]; then
    echo ">> [backend] creating conda env $env_dir (python 3.10)..."
    "$CONDA_BASE/bin/conda" create -p "$env_dir" python=3.10 -y
  fi
  # torchaudio/torio needs FFmpeg 6 ABI (libavutil.so.58). conda-forge's
  # latest ffmpeg is 8.x (libavutil.so.60) which torio cannot load, so pin 6.
  if ! "$env_dir/bin/ffmpeg" -version 2>/dev/null | grep -q "^ffmpeg version 6"; then
    echo ">> [backend] installing ffmpeg 6.0.0 into $env_dir..."
    "$CONDA_BASE/bin/conda" install -p "$env_dir" -c conda-forge "ffmpeg=6.0.0" -y
  fi
  export PATH="$env_dir/bin:$PATH"
  export LD_LIBRARY_PATH="$env_dir/lib:${LD_LIBRARY_PATH:-}"
}

# macOS: ffmpeg via Homebrew (no conda/CUDA), matching the Pipfile.mac CPU deps.
ensure_ffmpeg_mac() {
  if command -v ffmpeg >/dev/null 2>&1; then
    echo ">> [backend] ffmpeg found: $(command -v ffmpeg)"
    return
  fi
  if command -v brew >/dev/null 2>&1; then
    echo ">> [backend] installing ffmpeg via Homebrew..."
    brew install ffmpeg
  else
    echo "ERROR: ffmpeg not found and Homebrew not available. Install ffmpeg (e.g. 'brew install ffmpeg')." >&2
    exit 2
  fi
}

cleanup() {
  trap - INT TERM EXIT
  if [[ "$PROFILE" == "hpc" ]]; then
    [[ -n "${TUNNEL_PID:-}" ]] && kill -0 "$TUNNEL_PID" 2>/dev/null && kill "$TUNNEL_PID" 2>/dev/null || true
    ssh -o BatchMode=yes "$REMOTE_GPU" "pkill -f 'uvicorn.*8000' 2>/dev/null || true" 2>/dev/null || true
  else
    [[ -n "${BACK_PID:-}" ]] && kill -0 "$BACK_PID" 2>/dev/null && kill "$BACK_PID" 2>/dev/null || true
  fi
  [[ -n "${FRONT_PID:-}" ]] && kill -0 "$FRONT_PID" 2>/dev/null && kill "$FRONT_PID" 2>/dev/null || true
  wait 2>/dev/null || true
  echo ""; echo ">> WATCHOUT ISEQL ($PROFILE) stopped."
}
trap cleanup INT TERM EXIT

run_backend() {
  case "$PROFILE" in
    hpc)
      ensure_ffmpeg
      cd "$ROOT/backend"
      echo ">> [backend] installing deps if needed..."
      pipenv install --dev --quiet 2>/dev/null || true
      echo ">> [backend] starting on $REMOTE_GPU..."
      # clear any stale tunnel + remote backend left by a previous run (ssh -f
      # double-forks and can survive Ctrl-C), otherwise :8000 is held or points
      # at a dead backend -> ECONNRESET from the vite proxy.
      pkill -f "ssh.*-L 8000:localhost:8000.*$REMOTE_GPU" 2>/dev/null || true
      ssh -o BatchMode=yes "$REMOTE_GPU" "pkill -f 'uvicorn.*8000' 2>/dev/null; sleep 1" 2>/dev/null || true
      sleep 1
      ssh -o BatchMode=yes -f -N -L 8000:localhost:8000 "$REMOTE_GPU" 2>/dev/null || true
      TUNNEL_PID=$(pgrep -f "ssh.*-L 8000:localhost:8000.*$REMOTE_GPU" | tail -1 || true)
      REMOTE_ENV="$CONDA_BASE/envs/py310"
      ssh -o BatchMode=yes "$REMOTE_GPU" "cd $ROOT/backend && PATH=$REMOTE_ENV/bin:\$PATH LD_LIBRARY_PATH=$REMOTE_ENV/lib:\${LD_LIBRARY_PATH:-} PROFILE=hpc PYTHONPATH=src pipenv run uvicorn start_application:StartApplication --host 0.0.0.0 --port 8000 --reload" &
      sleep 3
      curl -s --max-time 5 http://127.0.0.1:8000/api/health >/dev/null 2>&1 && echo ">> [backend] remote ready" || echo ">> [backend] remote starting..."
      ;;
    local)
      ensure_ffmpeg
      cd "$ROOT/backend"
      echo ">> [backend] installing deps if needed..."
      pipenv --python "$(py310_env)/bin/python" install --dev --quiet 2>/dev/null || true
      if [ -f "$ROOT/backend/.env" ]; then set -a; source "$ROOT/backend/.env"; set +a; fi
      echo ">> [backend] starting uvicorn (pipenv)..."
      # idempotent: clear a stray backend from a previous run so :8000 is free
      pkill -f "uvicorn.*8000" 2>/dev/null || true
      sleep 1
      PYTHONPATH=src pipenv run uvicorn start_application:StartApplication --host 0.0.0.0 --port 8000 --reload &
      BACK_PID=$!
      ;;
    mac)
      ensure_ffmpeg_mac
      cd "$ROOT/backend"
      echo ">> [backend] installing deps if needed (Pipfile.mac, CPU)..."
      export PIPENV_PIPFILE=Pipfile.mac
      pipenv install --dev --quiet 2>/dev/null || true
      if [ -f "$ROOT/backend/.env" ]; then set -a; source "$ROOT/backend/.env"; set +a; fi
      echo ">> [backend] starting uvicorn (pipenv, macOS)..."
      pkill -f "uvicorn.*8000" 2>/dev/null || true
      sleep 1
      PYTHONPATH=src pipenv run uvicorn start_application:StartApplication --host 0.0.0.0 --port 8000 --reload &
      BACK_PID=$!
      ;;
  esac
}

run_frontend() {
  cd "$ROOT/frontend"
  echo ">> [frontend] starting vite dev..."
  # idempotent: clear a stray vite from a previous run so :5173 is free
  pkill -f "vite.*5173" 2>/dev/null || true
  sleep 1
  pnpm dev --host 0.0.0.0 --port 5173 &
  FRONT_PID=$!
}

case "$MODE" in
  backend)
    run_backend
    echo ">> Backend http://localhost:8000 [$PROFILE]"
    wait
    ;;
  frontend)
    run_frontend
    echo ">> Frontend http://localhost:5173 [$PROFILE]"
    wait
    ;;
  *)
    if [[ "$PROFILE" == "hpc" ]]; then
      echo ">> Starting WATCHOUT ISEQL (hpc)"; echo "   Backend  -> http://localhost:8000 (via $REMOTE_GPU:8000)"; echo "   Frontend -> http://localhost:5173"
    else
      echo ">> Starting WATCHOUT ISEQL (local)"; echo "   Backend  -> http://localhost:8000 (conda py310 + pipenv)"; echo "   Frontend -> http://localhost:5173"
    fi
    run_backend; run_frontend
    echo ">> Both running. Ctrl-C to stop."
    wait
    ;;
esac

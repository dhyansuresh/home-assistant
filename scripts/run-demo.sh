#!/usr/bin/env bash
# Start the whole HomePilot demo locally: Ollama (LLM), vision service, API and web app.
#
#   scripts/run-demo.sh            # web app in dev mode
#   scripts/run-demo.sh --prod     # build the web app first, then serve the production build
#
# Ctrl+C stops everything this script started. Logs go to $TMPDIR/homepilot-demo/.
# Overrides: VISION_GALLERY, VISION_UNKNOWN_THRESHOLD, OLLAMA_MODEL, PYTHON.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
GALLERY="${VISION_GALLERY:-$ROOT/models/galleries/demo}"
MODEL="${OLLAMA_MODEL:-qwen3:8b}"
LOGS="${TMPDIR:-/tmp}/homepilot-demo"
mkdir -p "$LOGS"
PIDS=()

say() { printf '\033[1;34m[demo]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[demo] %s\033[0m\n' "$*"; exit 1; }

cleanup() {
  say "Stopping…"
  for pid in "${PIDS[@]:-}"; do [ -n "$pid" ] && kill "$pid" 2>/dev/null; done
  wait 2>/dev/null
}
trap cleanup EXIT INT TERM

wait_for() {  # url, name, seconds
  for _ in $(seq 1 "$3"); do curl -fs "$1" >/dev/null 2>&1 && return 0; sleep 1; done
  fail "$2 did not start in $3 s. See $LOGS/"
}

# --- Checks -----------------------------------------------------------------
[ -x "$PYTHON" ] || fail "Python not found at $PYTHON (create .venv or set PYTHON)."
command -v ollama >/dev/null || fail "Ollama is not installed (brew install ollama)."
command -v npm >/dev/null || fail "npm is not installed."
[ -f "$GALLERY/gallery.json" ] || fail "No vision gallery at $GALLERY (build one with services/vision/register_gallery.py)."
for port in 8000 8001; do
  lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1 && fail "Port $port is already in use. Stop that process first."
done
WEB_RUNNING=0
lsof -nP -iTCP:3000 -sTCP:LISTEN >/dev/null 2>&1 && WEB_RUNNING=1
grep -q '^ELEVENLABS_API_KEY=.' "$ROOT/apps/web/.env.local" 2>/dev/null \
  || say "Warning: no ELEVENLABS_API_KEY in apps/web/.env.local; voice will not work (typing and photos still do)."
THRESHOLD="${VISION_UNKNOWN_THRESHOLD:-$("$PYTHON" -c "import json,sys; t=json.load(open(sys.argv[1])).get('suggested_unknown_threshold') or {}; print(t.get('value',''))" "$GALLERY/gallery.json")}"
[ -n "$THRESHOLD" ] || fail "Set VISION_UNKNOWN_THRESHOLD (the gallery has no suggested value)."

# --- Ollama -------------------------------------------------------------------
if ! curl -fs http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  say "Starting Ollama…"
  ollama serve >"$LOGS/ollama.log" 2>&1 & PIDS+=($!)
  wait_for http://127.0.0.1:11434/api/tags "Ollama" 30
fi
ollama list | awk '{print $1}' | grep -qx "$MODEL" || fail "Model $MODEL is missing. Run: ollama pull $MODEL"
say "Warming up $MODEL…"
curl -fs http://127.0.0.1:11434/api/chat \
  -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"stream\":false,\"think\":false,\"keep_alive\":\"30m\"}" \
  >/dev/null || fail "Ollama could not run $MODEL. See $LOGS/ollama.log"

# --- Vision service (8001) ----------------------------------------------------
say "Starting vision service (gallery $(basename "$GALLERY"), threshold $THRESHOLD)…"
(cd "$ROOT/services/vision" && HF_HUB_OFFLINE=1 VISION_GALLERY="$GALLERY" VISION_UNKNOWN_THRESHOLD="$THRESHOLD" \
  exec "$PYTHON" -m uvicorn app.main:app --port 8001) >"$LOGS/vision.log" 2>&1 & PIDS+=($!)
wait_for http://127.0.0.1:8001/health "Vision service" 120
curl -fs http://127.0.0.1:8001/health | grep -q '"ready":true' || fail "Vision service is not ready: $(curl -s http://127.0.0.1:8001/health)"

# --- API (8000) ---------------------------------------------------------------
say "Starting API…"
(cd "$ROOT/services/api" && LLM_PROVIDER=ollama OLLAMA_MODEL="$MODEL" VISION_SERVICE_URL=http://127.0.0.1:8001 \
  exec "$PYTHON" -m uvicorn app.main:app --port 8000) >"$LOGS/api.log" 2>&1 & PIDS+=($!)
wait_for http://127.0.0.1:8000/health "API" 60

# --- Web app (3000) -----------------------------------------------------------
cd "$ROOT/apps/web"
if [ "$WEB_RUNNING" = 1 ]; then
  say "Port 3000 is already serving a web app; reusing it (stop it and rerun to let this script start the web app)."
  wait_for http://127.0.0.1:3000 "Web app" 10
  say "HomePilot backend is running for http://localhost:3000   Logs: $LOGS   Press Ctrl+C to stop what this script started."
  wait
  exit 0
fi
[ -d node_modules ] || { say "Installing web dependencies…"; npm ci --no-audit --no-fund >"$LOGS/npm-install.log" 2>&1 || fail "npm ci failed. See $LOGS/npm-install.log"; }
if [ "${1:-}" = "--prod" ]; then
  say "Building web app…"
  npm run build >"$LOGS/web-build.log" 2>&1 || fail "Web build failed. See $LOGS/web-build.log"
  npm run start -- --hostname 127.0.0.1 --port 3000 >"$LOGS/web.log" 2>&1 & PIDS+=($!)
else
  npm run dev -- --hostname 127.0.0.1 --port 3000 >"$LOGS/web.log" 2>&1 & PIDS+=($!)
fi
wait_for http://127.0.0.1:3000 "Web app" 120

say "HomePilot is running: http://localhost:3000   (demo mode without the backend: http://localhost:3000/?demo=1)"
say "Logs: $LOGS   Press Ctrl+C to stop everything."
wait

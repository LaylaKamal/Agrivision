#!/bin/bash
# Run Flask (UI + /ml) from backend/python; creates .venv on first run.
set -e
cd "$(dirname "$0")/backend/python"

if [[ ! -f .venv/bin/activate ]]; then
  echo "Creating Python venv..."
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
else
  source .venv/bin/activate
fi

export ML_PORT="${ML_PORT:-5001}"
LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)

echo ""
echo "=== Agrivision ==="
echo "  Local:     http://127.0.0.1:${ML_PORT}/"
if [[ -n "$LAN_IP" ]]; then
  echo "  Same Wi-Fi: http://${LAN_IP}:${ML_PORT}/"
fi
echo "  Ctrl+C to stop."
echo ""

exec python app.py

#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ -f .env ]]; then
  set -a
  # shellcheck source=/dev/null
  source .env
  set +a
fi
if [[ -n "${LEXFLOW_PYTHON:-}" ]]; then
  lexflow_python="$LEXFLOW_PYTHON"
elif command -v python3.12 >/dev/null 2>&1; then
  lexflow_python="python3.12"
else
  lexflow_python="python3"
fi
if [[ "$("$lexflow_python" -c 'import sys; print("%s.%s" % sys.version_info[:2])')" != "3.12" ]]; then
  echo "[LexFlow] Use Python 3.12 for this demo. Set LEXFLOW_PYTHON to its executable path." >&2
  exit 1
fi
lexflow_env_dir="${LEXFLOW_VENV_DIR:-.venv-demo}"
if [[ ! -x "$lexflow_env_dir/bin/python" ]]; then
  echo "[LexFlow] Creating virtual environment..."
  "$lexflow_python" -m venv "$lexflow_env_dir"
fi
if [[ "$("$lexflow_env_dir/bin/python" -c 'import sys; print("%s.%s" % sys.version_info[:2])')" != "3.12" ]]; then
  echo "[LexFlow] $lexflow_env_dir uses another Python version. Set LEXFLOW_VENV_DIR to a new directory." >&2
  exit 1
fi
lexflow_fingerprint="$("$lexflow_python" -c 'import hashlib,pathlib; print(hashlib.sha256(b"".join(pathlib.Path(p).read_bytes() for p in ("requirements.txt","constraints.txt"))).hexdigest())')"
lexflow_installed=""
if [[ -f "$lexflow_env_dir/.requirements-hash" ]]; then
  lexflow_installed="$(cat "$lexflow_env_dir/.requirements-hash")"
fi
if [[ "$lexflow_installed" != "$lexflow_fingerprint" ]]; then
  "$lexflow_env_dir/bin/python" -m pip install --disable-pip-version-check -r requirements.txt
  printf '%s' "$lexflow_fingerprint" > "$lexflow_env_dir/.requirements-hash"
fi
lexflow_port="${LEXFLOW_PORT:-8000}"
echo "[LexFlow] Visit http://127.0.0.1:$lexflow_port — demo documents only."
exec "$lexflow_env_dir/bin/python" -m uvicorn lexflow.main:app --host 127.0.0.1 --port "$lexflow_port"

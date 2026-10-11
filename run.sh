#!/usr/bin/env bash
# One command to install and play (Linux, macOS):  ./run.sh [wordle-bot arguments]
# The first run creates .venv and installs torch, Laya and Selenium; later runs start straight away.
set -euo pipefail
cd "$(dirname "$0")"

VENV_PY=.venv/bin/python
MARKER=.venv/.installed

find_python() {
  for py in "${PYTHON:-}" python3.14 python3.13 python3.12 python3.11 python3.10 python3 python; do
    if [ -n "$py" ] && command -v "$py" >/dev/null 2>&1 &&
       "$py" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
      echo "$py"
      return 0
    fi
  done
  return 1
}

if [ ! -x "$VENV_PY" ]; then
  PY=$(find_python) || { echo "error: Python 3.10 or newer is required (or set PYTHON=/path/to/python)." >&2; exit 1; }
  echo "Creating .venv with $("$PY" --version 2>&1)..."
  "$PY" -m venv .venv || { echo "error: could not create .venv (on Debian/Ubuntu: sudo apt install python3-venv)." >&2; exit 1; }
fi

if [ ! -f "$MARKER" ] || [ pyproject.toml -nt "$MARKER" ]; then
  echo "Installing dependencies (first run only; torch and Laya are large)..."
  "$VENV_PY" -m pip install --quiet --upgrade pip
  if [ "$(uname -s)" = Linux ] && ! command -v nvidia-smi >/dev/null 2>&1; then
    # No NVIDIA GPU: the CPU-only torch build is ~0.2 GB instead of ~3 GB.
    "$VENV_PY" -m pip install torch --index-url https://download.pytorch.org/whl/cpu
  fi
  "$VENV_PY" -m pip install -e .
  touch "$MARKER"
fi

# ${1+"$@"}: macOS bash 3.2 treats an empty "$@" as unbound under `set -u`.
exec "$VENV_PY" -m wordle_bot ${1+"$@"}

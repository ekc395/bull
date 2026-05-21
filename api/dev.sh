#!/usr/bin/env bash
# Backend dev launcher.
#
# Why this exists: uv marks the entire .venv with the macOS UF_HIDDEN flag, and
# CPython 3.13 skips hidden .pth files, which breaks the editable install of
# bull_api. We sidestep that by exporting PYTHONPATH directly, so site.py never
# needs to read the .pth file.

set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
  echo "error: .venv not found. Run 'uv venv && uv pip install -e .' first." >&2
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate
export PYTHONPATH="$PWD/src"

exec uvicorn bull_api.main:app --reload "$@"

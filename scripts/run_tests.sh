#!/usr/bin/env bash
# One command, no API keys: unit + integration + e2e tests. (Integration
# Standard point 1.) The test suite boots the bundled mock platform server
# itself, so this works standalone without docker compose too:
#   ./scripts/run_tests.sh
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt
pip install -q -r mocks/platform_mock/requirements.txt

mkdir -p data
python -m pytest -v "$@"

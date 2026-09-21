#!/bin/zsh
# Mac tier: every 2 min, zero GitHub minutes, residential IP.
cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/bin:$PATH"
export GCHAT_WEBHOOK="$(cat .webhook 2>/dev/null)"
export DRY_RUNS=10 RADIUS_KM=6 STATE_FILE=state.local.json
exec uv run --quiet --python 3.12 --with curl_cffi python alert.py >> watch.log 2>&1

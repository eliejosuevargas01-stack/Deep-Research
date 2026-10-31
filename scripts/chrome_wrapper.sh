#!/usr/bin/env bash
exec /opt/hermes/tools/chromium-1208/chrome-linux64/chrome --no-sandbox --disable-dev-shm-usage "$@"

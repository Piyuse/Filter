#!/bin/sh
set -eu

: "${RENDER_EXTERNAL_HOSTNAME:?Render hostname is missing}"

export TRUSTED_HOSTS="${RENDER_EXTERNAL_HOSTNAME},localhost,127.0.0.1,[::1]"

exec waitress-serve \
  --host=0.0.0.0 \
  --port="${PORT:-5000}" \
  --url-scheme=https \
  --threads=2 \
  --inbuf-overflow=12582912 \
  --max-request-body-size=11534336 \
  --channel-timeout=60 \
  --ident=Filter \
  --call app.main:create_app
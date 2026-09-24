#!/usr/bin/env bash
# Invocado por el crontab del host de la Raspberry Pi. Levanta un contenedor
# efímero de scraprop por pasada (run/digest) y lo borra al terminar.
# La data persiste en ./data (bind-mount), no se pierde entre corridas.
#
# flock evita que dos pasadas se solapen (si una tarda más que el intervalo).
# Al terminar, hace push a Uptime Kuma (heartbeat) si existe ./.kuma_push
# (define KUMA_PUSH_BASE=http://127.0.0.1:3001/api/push/<token>). Gitignored.
set -uo pipefail
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$REPO_DIR/cron.log"

exec >>"$LOG" 2>&1
echo "===== $(date '+%Y-%m-%d %H:%M:%S %z') scraprop $* ====="

flock -n "$REPO_DIR/.run.lock" \
  sudo docker compose -f "$REPO_DIR/docker-compose.rpi.yml" run --rm scraprop \
    python -m scraprop "$@"
rc=$?
[ $rc -ne 0 ] && echo "[warn] scraprop salió con código $rc (otra pasada en curso o error)"

# Heartbeat a Uptime Kuma (opcional).
if [ -f "$REPO_DIR/.kuma_push" ]; then
  # shellcheck disable=SC1090
  . "$REPO_DIR/.kuma_push"
  if [ -n "${KUMA_PUSH_BASE:-}" ]; then
    if [ $rc -eq 0 ]; then
      curl -fsS -m 10 "${KUMA_PUSH_BASE}?status=up&msg=OK" >/dev/null 2>&1 || true
    else
      curl -fsS -m 10 "${KUMA_PUSH_BASE}?status=down&msg=exit${rc}" >/dev/null 2>&1 || true
    fi
  fi
fi
exit $rc

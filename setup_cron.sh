#!/bin/bash
# setup_cron.sh — corre el monitor cada 30 minutos en esta PC.
# Uso: bash setup_cron.sh

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
# Preferir el venv del repo (tiene las dependencias); si no, el python del sistema.
if [ -x "$REPO_DIR/.venv/bin/python" ]; then
  PYTHON_PATH="$REPO_DIR/.venv/bin/python"
else
  PYTHON_PATH="$(command -v python3 || command -v python)"
fi
LOG_DIR="$REPO_DIR/outputs/logs"
LOG_FILE="$LOG_DIR/scraprop-cron.log"

mkdir -p "$LOG_DIR"

# Quitar entradas previas de scraprop para no duplicar
crontab -l 2>/dev/null | grep -v "scraprop" | crontab -

# Monitoreo cada 30 min (NO entre 2am y 9am) + digest diario top-5 a las 9:00.
(crontab -l 2>/dev/null; \
 echo "*/30 0,1,9-23 * * * cd $REPO_DIR && $PYTHON_PATH -m scraprop >> $LOG_FILE 2>&1"; \
 echo "0 9 * * * cd $REPO_DIR && $PYTHON_PATH -m scraprop digest >> $LOG_FILE 2>&1") | crontab -

echo "✅ Cron configurado. Monitoreo c/30min (excepto 2-9am) + digest top-5 (9:00)."
echo "   Python:  $PYTHON_PATH"
echo "   Repo:    $REPO_DIR"
echo "   Log:     $LOG_FILE"
echo ""
echo "Ver cron:  crontab -l"
echo "Ver logs:  tail -f $LOG_FILE"

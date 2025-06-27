#!/bin/bash
# setup_cron.sh: Set up a cron job to run the property scraper at 8:30 AM and 6:30 PM daily
# Usage: bash setup_cron.sh

# Get absolute paths
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_PATH="$(which python)"
SCRIPT_PATH="$REPO_DIR/src/scraprop.py"
LOG_DIR="$REPO_DIR/outputs/logs"
LOG_FILE="$LOG_DIR/scraprop-cron.log"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Cron job line: 8:30 AM and 6:30 PM
CRON_LINE="30 8,18 * * * $PYTHON_PATH $SCRIPT_PATH >> $LOG_FILE 2>&1"

# Check if cron job already exists
(crontab -l 2>/dev/null | grep -F "$SCRIPT_PATH") && FOUND=1 || FOUND=0

if [ $FOUND -eq 1 ]; then
  echo "Cron job already exists."
else
  (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
  echo "Cron job added: $CRON_LINE"
fi 
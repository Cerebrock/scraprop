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

# Remove any existing cron job for this script
crontab -l 2>/dev/null | grep -v -F "$SCRIPT_PATH" | crontab -

# Cron job line: every 30 minutes
CRON_LINE="*/30 * * * * $PYTHON_PATH $SCRIPT_PATH >> $LOG_FILE 2>&1"

# Add the new cron job
(crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
echo "Cron job set to: $CRON_LINE" 
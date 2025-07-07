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

# Remove existing cron jobs for scraprop to avoid duplicates
crontab -l 2>/dev/null | grep -v "scraprop.py" | crontab -

# Add new cron job - runs every 30 minutes
(crontab -l 2>/dev/null; echo "*/30 * * * * cd /Users/mg/scraprop && /Users/mg/anaconda3/bin/python /Users/mg/scraprop/src/scraprop.py >> /Users/mg/scraprop/outputs/logs/scraprop-cron.log 2>&1") | crontab -

echo "Cron job set up successfully!"
echo "The scraper will run every 30 minutes."
echo "Logs will be saved to: /Users/mg/scraprop/outputs/logs/scraprop-cron.log"
echo ""
echo "To view current cron jobs: crontab -l"
echo "To view logs: tail -f /Users/mg/scraprop/outputs/logs/scraprop-cron.log" 
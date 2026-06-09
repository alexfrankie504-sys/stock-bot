"""
scheduler.py — Run the bot automatically every morning
=======================================================
Runs paper_trader.py every weekday at 9:00am automatically.
Sends a full weekly report every Sunday at 8:00am.
Leave this running in the background.

Usage:
    python3 scheduler.py
"""

import schedule
import time
import subprocess
import logging
from datetime import datetime
from weekly_report import send_weekly_report

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)


def run_bot():
    """Run the paper trader and log the output."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log.info("Running bot at %s ...", now)

    result = subprocess.run(
        ["python3", "paper_trader.py"],
        capture_output=True,
        text=True
    )

    print(result.stdout)
    if result.returncode != 0:
        log.error("Bot error: %s", result.stderr)
    else:
        log.info("Bot completed successfully.")


def is_weekday() -> bool:
    """Returns True if today is Monday–Friday."""
    return datetime.now().weekday() < 5


def scheduled_run():
    """Only run on weekdays — markets are closed on weekends."""
    if is_weekday():
        run_bot()
    else:
        log.info("Weekend — skipping daily run.")


def scheduled_weekly_report():
    """Send the weekly report every Sunday at 8am."""
    log.info("Sending weekly report...")
    send_weekly_report()
    log.info("Weekly report sent.")


# ── Schedule ──────────────────────────────────────────────────────────────────

schedule.every().day.at("09:00").do(scheduled_run)
schedule.every().sunday.at("08:00").do(scheduled_weekly_report)

log.info("Scheduler started.")
log.info("  → Daily bot    : every weekday at 9:00am")
log.info("  → Weekly report: every Sunday at 8:00am")
log.info("Leave this running in the background. Press Ctrl+C to stop.")
log.info("Next run: %s", schedule.next_run())

# Run bot immediately on startup
log.info("Running bot now for initial test...")
run_bot()

# Send weekly report immediately for testing
log.info("Sending weekly report now for initial test...")
send_weekly_report()

# Keep running
while True:
    schedule.run_pending()
    time.sleep(60)
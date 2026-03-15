"""
scheduler.py
────────────
Sets up the monthly cron job to run the pipeline automatically.

Usage:
    python scheduler.py             # Print the cron line to add manually
    python scheduler.py --install   # Auto-install the cron entry
    python scheduler.py --remove    # Remove the cron entry
    python scheduler.py --status    # Show current cron entries for this project

The cron runs on the 1st of every month at 08:00.
Logs are written to .tmp/pipeline.log.
"""

import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.resolve()
PYTHON = sys.executable
LOG_FILE = PROJECT_DIR / ".tmp" / "pipeline.log"

CRON_MARKER = f"# linkedin-automation:{PROJECT_DIR}"
CRON_LINE = (
    f"0 8 1 * * cd {PROJECT_DIR} && {PYTHON} orchestrator.py >> {LOG_FILE} 2>&1"
    f"  {CRON_MARKER}"
)


def get_current_crontab() -> str:
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout
    # returncode 1 means empty crontab — that's fine
    return ""


def set_crontab(content: str) -> bool:
    proc = subprocess.run(["crontab", "-"], input=content, text=True, capture_output=True)
    return proc.returncode == 0


def print_instructions() -> None:
    print()
    print("=" * 65)
    print("  Monthly Cron Setup — LinkedIn Job Hunt Automation")
    print("=" * 65)
    print()
    print("Add this line to your crontab (run: crontab -e):")
    print()
    print(f"  {CRON_LINE}")
    print()
    print("This will run the pipeline on the 1st of every month at 08:00.")
    print(f"Logs will be saved to: {LOG_FILE}")
    print()
    print("Or run:  python scheduler.py --install  to add it automatically.")
    print()


def install_cron() -> None:
    existing = get_current_crontab()
    if CRON_MARKER in existing:
        print("Cron job is already installed.")
        print()
        print("Current entry:")
        for line in existing.splitlines():
            if CRON_MARKER in line:
                print(f"  {line.replace(CRON_MARKER, '').strip()}")
        return

    new_crontab = existing.rstrip("\n") + "\n" + CRON_LINE + "\n"
    if set_crontab(new_crontab):
        print("Cron job installed successfully.")
        print(f"Pipeline will run on the 1st of every month at 08:00.")
        print(f"Logs: {LOG_FILE}")
    else:
        print("Failed to install cron job automatically.")
        print("Please add the following line manually with: crontab -e")
        print()
        print(f"  {CRON_LINE}")


def remove_cron() -> None:
    existing = get_current_crontab()
    if CRON_MARKER not in existing:
        print("No LinkedIn automation cron entry found.")
        return

    new_lines = [l for l in existing.splitlines() if CRON_MARKER not in l]
    new_crontab = "\n".join(new_lines) + "\n"
    if set_crontab(new_crontab):
        print("Cron job removed successfully.")
    else:
        print("Failed to remove cron job. Remove it manually with: crontab -e")


def show_status() -> None:
    existing = get_current_crontab()
    entries = [l for l in existing.splitlines() if CRON_MARKER in l]
    if entries:
        print("LinkedIn automation cron is INSTALLED:")
        for e in entries:
            print(f"  {e.replace(CRON_MARKER, '').strip()}")
    else:
        print("LinkedIn automation cron is NOT installed.")
        print("Run: python scheduler.py --install")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Manage monthly cron job for the pipeline")
    parser.add_argument("--install", action="store_true", help="Install the cron entry")
    parser.add_argument("--remove", action="store_true", help="Remove the cron entry")
    parser.add_argument("--status", action="store_true", help="Show current status")
    args = parser.parse_args()

    if args.install:
        install_cron()
    elif args.remove:
        remove_cron()
    elif args.status:
        show_status()
    else:
        print_instructions()

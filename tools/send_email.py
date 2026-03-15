"""
send_email.py
─────────────
Sends the PDF job report as an email attachment via SendGrid API.

Requires a free SendGrid account and API key:
  https://sendgrid.com → Settings → API Keys → Create API Key (Mail Send)

Usage:
    python tools/send_email.py --pdf-path .tmp/job_report_2026-03.pdf
"""

import argparse
import base64
import json
import logging
import os
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
SENDER = os.getenv("GMAIL_SENDER_ADDRESS", "")
RECIPIENT = os.getenv("GMAIL_RECIPIENT_ADDRESS", "")

SENDGRID_URL = "https://api.sendgrid.com/v3/mail/send"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("send_email")


class EmailDeliveryError(Exception):
    pass


def build_body(top_job: dict | None, run_date: str) -> str:
    if top_job:
        top_line = (
            f"Top match: {top_job.get('title', 'N/A')} at "
            f"{top_job.get('company', 'N/A')} "
            f"({top_job.get('score', 'N/A')}/100 fit score)"
        )
    else:
        top_line = "See the attached PDF for all matched opportunities."

    return (
        f"Hi,\n\n"
        f"Your monthly LinkedIn Job Match Report for {run_date} is attached.\n\n"
        f"{top_line}\n\n"
        f"The report includes job descriptions, fit scores, matched skills, "
        f"missing skills, apply links, and contact emails where available.\n\n"
        f"Good luck!\n\n"
        f"— LinkedIn Job Hunt Automation\n"
    )


def send_email(
    pdf_path: str,
    sender: str = SENDER,
    recipient: str = RECIPIENT,
    api_key: str = SENDGRID_API_KEY,
    top_job: dict | None = None,
) -> bool:
    if not api_key:
        raise EmailDeliveryError(
            "SENDGRID_API_KEY is not set in .env\n"
            "Get a free key at: sendgrid.com → Settings → API Keys"
        )
    if not sender:
        raise EmailDeliveryError("GMAIL_SENDER_ADDRESS is not set in .env")
    if not recipient:
        raise EmailDeliveryError("GMAIL_RECIPIENT_ADDRESS is not set in .env")

    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise EmailDeliveryError(f"PDF file not found: {pdf_path}")

    run_date = datetime.now().strftime("%B %Y")
    subject = f"LinkedIn Job Match Report — {run_date}"

    with open(pdf_file, "rb") as f:
        pdf_b64 = base64.b64encode(f.read()).decode()

    payload = {
        "personalizations": [{"to": [{"email": recipient}]}],
        "from": {"email": sender},
        "subject": subject,
        "content": [{"type": "text/plain", "value": build_body(top_job, run_date)}],
        "attachments": [
            {
                "content": pdf_b64,
                "type": "application/pdf",
                "filename": pdf_file.name,
                "disposition": "attachment",
            }
        ],
    }

    log.info("Sending report to %s via SendGrid...", recipient)
    response = requests.post(
        SENDGRID_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        data=json.dumps(payload),
        timeout=30,
    )

    if response.status_code in (200, 202):
        log.info("Email sent successfully to %s", recipient)
        return True
    elif response.status_code == 401:
        raise EmailDeliveryError(
            "SendGrid API key is invalid or expired.\n"
            "Regenerate at: sendgrid.com → Settings → API Keys"
        )
    elif response.status_code == 403:
        raise EmailDeliveryError(
            "SendGrid API key lacks 'Mail Send' permission.\n"
            "Create a new key with: Restricted Access → Mail Send → Full Access"
        )
    else:
        raise EmailDeliveryError(
            f"SendGrid returned {response.status_code}: {response.text}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf-path", required=False, help="Path to the PDF report")
    args = parser.parse_args()

    pdf_path = args.pdf_path
    if not pdf_path:
        reports = sorted(Path(".tmp").glob("job_report_*.pdf"), reverse=True)
        if not reports:
            print("No report found in .tmp/. Run generate_report.py first.")
            exit(1)
        pdf_path = str(reports[0])
        log.info("Auto-detected report: %s", pdf_path)

    top_job = None
    scored_path = Path(".tmp/scored_jobs.json")
    if scored_path.exists():
        with open(scored_path) as f:
            jobs = json.load(f)
        top_job = jobs[0] if jobs else None

    send_email(pdf_path=pdf_path, top_job=top_job)

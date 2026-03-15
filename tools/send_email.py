"""
send_email.py
─────────────
Sends the PDF job report as an email attachment via Gmail SMTP.

Requires a Gmail App Password (NOT your account password):
  Google Account → Security → 2-Step Verification → App Passwords

Usage:
    python tools/send_email.py --pdf-path .tmp/job_report_2026-03.pdf
"""

import argparse
import email.encoders
import json
import logging
import os
import smtplib
from datetime import datetime
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

GMAIL_SENDER = os.getenv("GMAIL_SENDER_ADDRESS", "")
GMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "")  # strip spaces
GMAIL_RECIPIENT = os.getenv("GMAIL_RECIPIENT_ADDRESS", "")

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
    sender: str = GMAIL_SENDER,
    app_password: str = GMAIL_PASSWORD,
    recipient: str = GMAIL_RECIPIENT,
    top_job: dict | None = None,
) -> bool:
    # Validate inputs
    if not sender:
        raise EmailDeliveryError("GMAIL_SENDER_ADDRESS is not set in .env")
    if not app_password:
        raise EmailDeliveryError(
            "GMAIL_APP_PASSWORD is not set in .env\n"
            "Get it at: Google Account → Security → 2-Step Verification → App Passwords"
        )
    if not recipient:
        raise EmailDeliveryError("GMAIL_RECIPIENT_ADDRESS is not set in .env")

    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise EmailDeliveryError(f"PDF file not found: {pdf_path}")

    run_date = datetime.now().strftime("%B %Y")
    subject = f"LinkedIn Job Match Report — {run_date}"

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject

    body_text = build_body(top_job, run_date)
    msg.attach(MIMEText(body_text, "plain"))

    # Attach PDF
    with open(pdf_file, "rb") as f:
        attachment = MIMEBase("application", "pdf")
        attachment.set_payload(f.read())
    email.encoders.encode_base64(attachment)
    attachment.add_header(
        "Content-Disposition",
        f'attachment; filename="{pdf_file.name}"',
    )
    msg.attach(attachment)

    log.info("Sending report to %s via Gmail SMTP...", recipient)
    conn = None
    try:
        conn = smtplib.SMTP("smtp.gmail.com", 587, timeout=30)
        conn.ehlo()
        conn.starttls()
        conn.login(sender, app_password)
        conn.sendmail(sender, recipient, msg.as_string())
        log.info("Email sent successfully to %s", recipient)
        return True
    except smtplib.SMTPAuthenticationError:
        raise EmailDeliveryError(
            "Gmail authentication failed.\n"
            "Make sure you're using an App Password (16 chars), not your account password.\n"
            "Instructions: Google Account → Security → 2-Step Verification → App Passwords"
        )
    except smtplib.SMTPException as e:
        raise EmailDeliveryError(f"SMTP error: {e}")
    finally:
        if conn:
            try:
                conn.quit()
            except Exception:
                pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf-path", required=False, help="Path to the PDF report")
    args = parser.parse_args()

    # Auto-detect latest report if not specified
    pdf_path = args.pdf_path
    if not pdf_path:
        reports = sorted(Path(".tmp").glob("job_report_*.pdf"), reverse=True)
        if not reports:
            print("No report found in .tmp/. Run generate_report.py first.")
            exit(1)
        pdf_path = str(reports[0])
        log.info("Auto-detected report: %s", pdf_path)

    # Load top job for email body
    top_job = None
    scored_path = Path(".tmp/scored_jobs.json")
    if scored_path.exists():
        with open(scored_path) as f:
            jobs = json.load(f)
        top_job = jobs[0] if jobs else None

    send_email(pdf_path=pdf_path, top_job=top_job)

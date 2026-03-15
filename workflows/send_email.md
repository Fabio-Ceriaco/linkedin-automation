# Send Email Report

## Objective
Send the generated PDF report as an email attachment via Gmail SMTP.

## Required Inputs
- PDF file in `.tmp/` (from `generate_report.py`)
- `GMAIL_SENDER_ADDRESS` in `.env`
- `GMAIL_APP_PASSWORD` in `.env` — see setup below
- `GMAIL_RECIPIENT_ADDRESS` in `.env`

## Gmail App Password Setup (one-time)
1. Go to your Google Account: https://myaccount.google.com/
2. Click **Security** in the left sidebar
3. Under "How you sign in to Google", click **2-Step Verification** (must be enabled)
4. Scroll to the bottom and click **App passwords**
5. Choose app: **Mail**, device: **Other** → type "LinkedIn Automation"
6. Click **Generate** — you'll get a 16-character password
7. Copy it to `.env` as `GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx` (spaces are stripped automatically)

## Run
```bash
python tools/send_email.py                            # auto-detects latest report
python tools/send_email.py --pdf-path .tmp/job_report_2026-03.pdf
```

## Output
Email delivered to `GMAIL_RECIPIENT_ADDRESS` with:
- Subject: "LinkedIn Job Match Report — [Month] [Year]"
- Body: brief summary with top job name + score
- Attachment: the PDF report

## Known Constraints
- Must use an **App Password**, NOT your Gmail account password
- STARTTLS on port 587 is required — plain SMTP port 25 will not work
- Gmail has a daily send limit (~500 emails/day) — well within our usage

## Troubleshooting
| Problem | Solution |
|---|---|
| `SMTPAuthenticationError` | App Password is wrong. Re-generate at Google Account → App Passwords |
| "Less secure apps" error | Not applicable — App Passwords bypass this requirement |
| Email not received | Check spam folder; verify `GMAIL_RECIPIENT_ADDRESS` is correct |
| `PDF file not found` | Run `generate_report.py` first |
| Connection timeout | Check internet connectivity and firewall rules for port 587 |

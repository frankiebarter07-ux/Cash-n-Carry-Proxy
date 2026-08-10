#!/usr/bin/env python3
"""
Email the daily price report to people who do not use GitHub.

GitHub already emails everyone *watching* the repository when the report is posted.
This exists for the recipients who will never have a GitHub account -- a buyer, a
procurement manager -- who still need to know when a supplier moved a price.

Deliberately written with the standard library (`smtplib`) rather than a third-party
Action: the credential handled here is a company mailbox password, and the fewer
external moving parts sitting in that path, the better. Any SMTP provider works.

Configuration, all from the environment (set these as repository secrets):

    SMTP_HOST       e.g. smtp.office365.com, smtp.gmail.com, smtp.resend.com
    SMTP_PORT       587 for STARTTLS (default), 465 for implicit TLS
    SMTP_USER       the mailbox / API username
    SMTP_PASSWORD   an app password or API key -- never a person's login password
    REPORT_FROM     address to send from (defaults to SMTP_USER)
    REPORT_TO       comma-separated recipients

    python3 scripts/send_report.py --html report.html --text report.md \
        --subject "Cooking oil prices moved"

Exits 0 and does nothing if SMTP is not configured, so the workflow stays green for
anyone who never sets it up. Exits non-zero only if sending was attempted and failed
-- a report that silently fails to send is worse than no report at all.
"""

import argparse
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage


def main():
    ap = argparse.ArgumentParser(description="Email the daily price report.")
    ap.add_argument("--html", required=True, help="HTML body")
    ap.add_argument("--text", required=True, help="plain-text fallback body")
    ap.add_argument("--subject", default="Cooking oil price report")
    ap.add_argument("--dry-run", action="store_true",
                    help="check config and print what would be sent, send nothing")
    args = ap.parse_args()

    host = os.environ.get("SMTP_HOST", "").strip()
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "").strip()
    to = [a.strip() for a in os.environ.get("REPORT_TO", "").split(",") if a.strip()]
    sender = os.environ.get("REPORT_FROM", "").strip() or user
    port = int(os.environ.get("SMTP_PORT", "587") or 587)

    if not (host and user and password and to):
        missing = [n for n, v in (("SMTP_HOST", host), ("SMTP_USER", user),
                                  ("SMTP_PASSWORD", password), ("REPORT_TO", to)) if not v]
        print(f"Email not configured (missing: {', '.join(missing)}) -- skipping. "
              f"GitHub notifications are unaffected.")
        return 0

    for path in (args.html, args.text):
        if not os.path.exists(path):
            print(f"No report to send ({path} does not exist) -- nothing moved today.")
            return 0

    msg = EmailMessage()
    msg["Subject"] = args.subject
    msg["From"] = sender
    msg["To"] = ", ".join(to)
    with open(args.text, encoding="utf-8") as fh:
        msg.set_content(fh.read())
    with open(args.html, encoding="utf-8") as fh:
        msg.add_alternative(fh.read(), subtype="html")

    if args.dry_run:
        print(f"DRY RUN -- would send {msg['Subject']!r}\n"
              f"  from {sender}\n  to   {', '.join(to)}\n"
              f"  via  {host}:{port}\n  size {len(msg.as_bytes())} bytes")
        return 0

    ctx = ssl.create_default_context()
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as s:
                s.login(user, password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as s:
                s.starttls(context=ctx)
                s.login(user, password)
                s.send_message(msg)
    except Exception as e:
        # Loud, but without echoing anything that could contain the credential.
        print(f"EMAIL FAILED: {type(e).__name__}: {e}", file=sys.stderr)
        print("Check SMTP_HOST/PORT/USER/PASSWORD. Many providers require an app "
              "password rather than the account password, and some require the "
              "From address to match the authenticated mailbox.", file=sys.stderr)
        return 1

    print(f"Emailed {len(to)} recipient(s): {', '.join(to)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

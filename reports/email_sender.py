"""
reports/email_sender.py — §25
Gmail SMTP email sender. Returns bool. Never raises.

Uses smtplib from the Python standard library — no additional package required.
Credentials loaded from environment variables (set in GitHub Actions secrets).

DISCLAIMER: This system does NOT perform trading, does NOT give investment advice,
and does NOT make price predictions. It is a research data aggregation and scoring
tool only.
"""

import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pytz

from config import GMAIL_EMAIL, GMAIL_APP_PASSWORD, EMAIL_MAX_COMPANIES, GITHUB_PAGES_URL
from utils.logger import get_logger
from reports.email_builder import build_email_html
from reports.sentence_templates import confidence_label

log = get_logger('email_sender')

TIMEZONE  = 'America/New_York'
SMTP_HOST = 'smtp.gmail.com'
SMTP_PORT = 587

DISCLAIMER = (
    'DISCLAIMER: This system does NOT perform trading, does NOT give investment advice, '
    'and does NOT make price predictions. It is a research data aggregation and scoring tool only.'
)


def _build_subject(slot: str, n_companies: int) -> str:
    """Builds email subject line per §23.1 spec."""
    word = 'opportunity' if n_companies == 1 else 'opportunities'
    return f'■ Stock Research — {slot} Update — {n_companies} {word} found'


def _build_closing_subject(date_str: str, n_total: int) -> str:
    """Builds closing email subject line per §23.2 spec."""
    word = 'opportunity' if n_total == 1 else 'opportunities'
    return f'■ Daily Summary — {date_str} — {n_total} total {word}'


def _load_html(html_path: str) -> str | None:
    """Loads HTML file content. Returns None on failure."""
    try:
        with open(html_path, encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        log.error(f'Cannot read HTML file {html_path}: {e}')
        return None


def _send_via_smtp(to_addr: str, subject: str, html_body: str) -> bool:
    """
    Sends a single HTML email via Gmail SMTP.
    Returns True on success, False on any failure.
    Never raises.
    """
    if not GMAIL_EMAIL or not GMAIL_APP_PASSWORD:
        log.warning('Gmail credentials not configured — email not sent')
        return False

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = GMAIL_EMAIL
        msg['To']      = to_addr

        # Plain text fallback (stripped version)
        plain = (
            f'{subject}\n\n'
            f'This email requires an HTML-capable email client.\n\n'
            f'{DISCLAIMER}'
        )
        msg.attach(MIMEText(plain, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_EMAIL, to_addr, msg.as_string())

        log.info(f'Email sent to {to_addr}: {subject}')
        return True

    except smtplib.SMTPAuthenticationError as e:
        log.error(f'Gmail SMTP authentication failed: {e}')
        return False
    except smtplib.SMTPException as e:
        log.error(f'Gmail SMTP error: {e}')
        return False
    except Exception as e:
        log.error(f'Email send failed (non-SMTP): {e}')
        return False


def send_email(
    companies: list,
    slot:      str,
    indices:   dict,
    html_path: str | None,
) -> bool:
    """
    Sends intraday report email.
    Called by main.py step 29.

    Parameters:
      companies — full ranked candidate list (all companies, not just top 7)
      slot      — run slot string e.g. '10:30'
      indices   — dict from market_collector.get_index_snapshot()
      html_path — path to the pre-built email HTML file from report_builder

    Returns:
      True  — email sent successfully
      False — failed (report still committed to repo by main.py)

    Never raises.
    """
    if not GMAIL_EMAIL:
        log.warning('GMAIL_EMAIL not set — skipping email send')
        return False

    try:
        n_total  = len(companies)
        subject  = _build_subject(slot, n_total)

        # Attempt to load pre-built HTML from report_builder
        html_body = None
        if html_path and os.path.exists(html_path):
            html_body = _load_html(html_path)
            log.info(f'Using pre-built HTML: {html_path}')

        # If HTML not available, build it now using email_builder
        if not html_body:
            log.info('Pre-built HTML unavailable — building email HTML inline')
            try:
                html_body = _build_inline_email(companies, slot, indices, subject)
            except Exception as e:
                log.error(f'Inline email build failed: {e}')
                return False

        return _send_via_smtp(GMAIL_EMAIL, subject, html_body)

    except Exception as e:
        log.error(f'send_email crashed (non-fatal): {e}')
        return False


def send_closing_email(html_path: str | None, n_total: int) -> bool:
    """
    Sends closing summary email.
    Called by summary_builder indirectly (main.py step 30 calls build_closing_report
    which can call this if needed — optional integration point).

    Returns:
      True on success, False on failure. Never raises.
    """
    if not GMAIL_EMAIL:
        log.warning('GMAIL_EMAIL not set — skipping closing email')
        return False

    try:
        now_et   = datetime.now(pytz.timezone(TIMEZONE))
        date_str = now_et.strftime('%Y-%m-%d')
        subject  = _build_closing_subject(date_str, n_total)

        html_body = None
        if html_path and os.path.exists(html_path):
            html_body = _load_html(html_path)

        if not html_body:
            log.warning('Closing HTML not available — sending plain text fallback')
            html_body = (
                f'<html><body style="font-family:monospace">'
                f'<h2>{subject}</h2>'
                f'<p>View the full report on GitHub Pages: '
                f'<a href="{GITHUB_PAGES_URL}">{GITHUB_PAGES_URL}</a></p>'
                f'<p><em>{DISCLAIMER}</em></p>'
                f'</body></html>'
            )

        return _send_via_smtp(GMAIL_EMAIL, subject, html_body)

    except Exception as e:
        log.error(f'send_closing_email crashed (non-fatal): {e}')
        return False


def _build_inline_email(companies: list, slot: str, indices: dict, subject: str) -> str:
    """
    Builds email HTML inline when pre-built file is unavailable.
    Applies EMAIL_MAX_COMPANIES cap and overflow count.
    """
    from reports.report_builder import _build_market_pulse, _build_story_sentences, _enrich_company_for_template
    from reports.sentence_templates import risk_section

    pulse_lines     = _build_market_pulse(indices)
    story_sentences = ['Market conditions were monitored today. See company list.']

    enriched        = [_enrich_company_for_template(c) for c in companies]
    email_companies = enriched[:EMAIL_MAX_COMPANIES]
    overflow_count  = max(0, len(enriched) - EMAIL_MAX_COMPANIES)

    low_risk      = [c for c in email_companies if c['section'] == 'LOW RISK']
    moderate_risk = [c for c in email_companies if c['section'] == 'MODERATE RISK']

    from datetime import datetime
    import pytz
    now_et   = datetime.now(pytz.timezone(TIMEZONE))
    date_str = now_et.strftime('%Y-%m-%d')
    slot_str = slot

    full_url = GITHUB_PAGES_URL + '/reports/output/'

    return build_email_html(
        slot             = slot_str,
        date_str         = date_str,
        subject          = subject,
        pulse_lines      = pulse_lines,
        story_sentences  = story_sentences,
        low_risk         = low_risk,
        moderate_risk    = moderate_risk,
        overflow_count   = overflow_count,
        full_report_url  = full_url,
        regime_label     = 'Normal market',
    )

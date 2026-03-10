"""
reports/email_builder.py — §23 File 3
Phone and smartwatch optimised email HTML builder.
Produces a self-contained HTML string suitable for embedding directly in an email body
(no external CSS, no JavaScript, maximum width 600px, monospace font fallback).

DISCLAIMER: This system does NOT perform trading, does NOT give investment advice,
and does NOT make price predictions. It is a research data aggregation and scoring
tool only.
"""

from utils.logger import get_logger

log = get_logger('email_builder')

DISCLAIMER = (
    'DISCLAIMER: This system does NOT perform trading, does NOT give investment advice, '
    'and does NOT make price predictions. It is a research data aggregation and scoring tool only.'
)

# ── Colour palette ────────────────────────────────────────────────────────────
COLOUR_BG         = '#0d1117'   # near-black background
COLOUR_CARD_BG    = '#161b22'   # card/row background
COLOUR_TEXT       = '#e6edf3'   # primary text
COLOUR_MUTED      = '#8b949e'   # secondary / label text
COLOUR_GREEN      = '#3fb950'   # low risk / positive
COLOUR_AMBER      = '#d29922'   # moderate risk / warning
COLOUR_RED        = '#f85149'   # negative change
COLOUR_BLUE       = '#58a6ff'   # accent / link
COLOUR_BORDER     = '#30363d'   # separator border
COLOUR_PULSE_BG   = '#1c2128'   # market pulse block
COLOUR_WARNING_BG = '#272210'   # earnings/divergence warning row


def _css() -> str:
    """Inline CSS block. Kept minimal for email client compatibility."""
    return """
    <style>
      body{background:#0d1117;color:#e6edf3;font-family:'Courier New',Courier,monospace;
           font-size:14px;line-height:1.6;margin:0;padding:0}
      .wrap{max-width:600px;margin:0 auto;padding:16px}
      .header{background:#161b22;border:1px solid #30363d;border-radius:6px;
              padding:12px 16px;margin-bottom:12px}
      .header h1{margin:0;font-size:16px;color:#58a6ff;font-weight:bold}
      .header .sub{color:#8b949e;font-size:12px;margin-top:4px}
      .pulse{background:#1c2128;border:1px solid #30363d;border-radius:6px;
             padding:12px 16px;margin-bottom:12px;font-size:13px}
      .pulse h2{margin:0 0 8px;font-size:13px;color:#8b949e;text-transform:uppercase;
                letter-spacing:0.05em}
      .pulse-line{font-family:'Courier New',Courier,monospace;white-space:pre;
                  padding:2px 0;color:#e6edf3}
      .story{background:#161b22;border:1px solid #30363d;border-radius:6px;
             padding:12px 16px;margin-bottom:12px;font-size:13px;color:#8b949e}
      .story p{margin:4px 0}
      .section-header{font-size:12px;font-weight:bold;text-transform:uppercase;
                       letter-spacing:0.08em;padding:6px 0 4px;border-bottom:1px solid #30363d;
                       margin-bottom:8px}
      .section-low  .section-header{color:#3fb950}
      .section-mod  .section-header{color:#d29922}
      .company-card{border:1px solid #30363d;border-radius:6px;padding:12px;margin-bottom:8px;
                    background:#161b22}
      .company-name{font-size:14px;font-weight:bold;color:#58a6ff;margin-bottom:4px}
      .company-name .ticker{color:#8b949e;font-size:12px;margin-left:4px}
      .line{margin:3px 0;font-size:13px}
      .label{color:#8b949e}
      .up{color:#3fb950}
      .down{color:#f85149}
      .warn{background:#272210;border-left:3px solid #d29922;padding:6px 8px;
            margin-top:6px;font-size:12px;color:#d29922;border-radius:3px}
      .notice-info{background:#1c2128;border-left:3px solid #58a6ff;padding:6px 8px;
                   margin-top:6px;font-size:12px;color:#8b949e;border-radius:3px}
      .conf-strong{color:#3fb950;font-weight:bold}
      .conf-mod{color:#d29922;font-weight:bold}
      .conf-weak{color:#8b949e;font-weight:bold}
      .overflow{background:#161b22;border:1px solid #30363d;border-radius:6px;
                padding:10px 16px;margin-top:8px;font-size:13px;color:#8b949e}
      .overflow a{color:#58a6ff}
      .disclaimer{margin-top:16px;font-size:11px;color:#484f58;border-top:1px solid #30363d;
                  padding-top:8px;line-height:1.4}
    </style>
    """


def _conf_css_class(label: str) -> str:
    if label == 'STRONG':
        return 'conf-strong'
    elif label == 'MODERATE':
        return 'conf-mod'
    return 'conf-weak'


def _render_company_card(c: dict, show_mod_risk: bool = False) -> str:
    """Renders a single company card as HTML string."""
    ticker       = c.get('ticker', '')
    name         = c.get('display_name', ticker)
    conf_lbl     = c.get('confidence_label', 'MODERATE')
    conf_score   = c.get('conf_score_int', 0)
    conf_class   = _conf_css_class(conf_lbl)
    price_line   = c.get('price_line', '')
    intro        = c.get('intro_sentence', '')
    trend_lbl    = c.get('trend_label', '')
    fin_health   = c.get('financial_health', '')
    vol_line     = c.get('volume_line', '')
    mod_risk     = c.get('moderate_risk_text', '') if show_mod_risk else ''
    notices      = c.get('notices', [])
    sector_plain = c.get('sector_plain', '')

    # Notices (earnings warning, divergence, unusual volume, drawdown)
    notices_html = ''
    for n in notices:
        is_warn = '■■' in n
        css_cls = 'warn' if is_warn else 'notice-info'
        notices_html += f'<div class="{css_cls}">{n}</div>\n'

    mod_risk_html = ''
    if mod_risk:
        mod_risk_html = f'<div class="warn">■■ {mod_risk}</div>\n'

    return f"""
<div class="company-card">
  <div class="company-name">■■■ {name} <span class="ticker">({ticker})</span> — {sector_plain} ■■■</div>
  <div class="line">{intro}</div>
  <div class="line"><span class="label">■ Trend:</span> {trend_lbl}</div>
  <div class="line"><span class="label">■</span> {price_line}</div>
  <div class="line"><span class="label">■</span> {fin_health}</div>
  <div class="line"><span class="label">■</span> {vol_line}</div>
  <div class="line"><span class="label">■ Confidence:</span>
    <span class="{conf_class}">{conf_lbl} ({conf_score}/100)</span>
  </div>
  {mod_risk_html}{notices_html}
</div>
"""


def build_email_html(
    slot:           str,
    date_str:       str,
    subject:        str,
    pulse_lines:    list[str],
    story_sentences: list[str],
    low_risk:       list[dict],
    moderate_risk:  list[dict],
    overflow_count: int,
    full_report_url: str,
    regime_label:   str,
) -> str:
    """
    Builds a self-contained email HTML body string.
    Called by report_builder.py (and directly by email_sender.py in tests).

    Parameters:
      low_risk, moderate_risk — lists of enriched company dicts from report_builder._enrich_company_for_template()
      overflow_count          — number of companies not shown in email body
      full_report_url         — GitHub Pages URL for the full browser report
      regime_label            — e.g. 'Normal market', 'Elevated uncertainty'

    Returns:
      A complete HTML string ready to send as email body.
    """
    try:
        css = _css()

        # ── Header ─────────────────────────────────────────────────────────
        header_html = f"""
<div class="header">
  <h1>■ Stock Research — {slot} Update</h1>
  <div class="sub">{date_str} · Market: {regime_label}</div>
</div>
"""

        # ── Market Pulse ────────────────────────────────────────────────────
        pulse_rows = '\n'.join(f'<div class="pulse-line">{pl}</div>' for pl in pulse_lines)
        pulse_html = f"""
<div class="pulse">
  <h2>Market Pulse</h2>
  {pulse_rows}
</div>
"""

        # ── Today's Story ───────────────────────────────────────────────────
        story_rows = '\n'.join(f'<p>{s}</p>' for s in story_sentences)
        story_html = f'<div class="story"><p><em>Today\'s story</em></p>\n{story_rows}\n</div>'

        # ── Low Risk Section ────────────────────────────────────────────────
        low_cards = '\n'.join(_render_company_card(c, show_mod_risk=False) for c in low_risk)
        low_html = ''
        if low_risk:
            low_html = f"""
<div class="section-low">
  <div class="section-header">■ LOW RISK OPPORTUNITIES</div>
  {low_cards}
</div>
"""

        # ── Moderate Risk Section ───────────────────────────────────────────
        mod_cards = '\n'.join(_render_company_card(c, show_mod_risk=True) for c in moderate_risk)
        mod_html = ''
        if moderate_risk:
            mod_html = f"""
<div class="section-mod">
  <div class="section-header">■ MODERATE RISK OPPORTUNITIES</div>
  {mod_cards}
</div>
"""

        # ── Overflow Notice ─────────────────────────────────────────────────
        overflow_html = ''
        if overflow_count > 0:
            overflow_html = f"""
<div class="overflow">
  + {overflow_count} more {"company" if overflow_count == 1 else "companies"} found today.
  <a href="{full_report_url}">View full report</a>
</div>
"""

        # ── Disclaimer ──────────────────────────────────────────────────────
        disclaimer_html = f'<div class="disclaimer">{DISCLAIMER}</div>'

        # ── Assemble ────────────────────────────────────────────────────────
        body = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{subject}</title>
{css}
</head>
<body>
<div class="wrap">
{header_html}
{pulse_html}
{story_html}
{low_html}
{mod_html}
{overflow_html}
{disclaimer_html}
</div>
</body>
</html>"""

        return body

    except Exception as e:
        log.error(f'email_builder.build_email_html failed: {e}')
        # Ultra-minimal fallback
        return (
            f'<html><body>'
            f'<h2>Stock Research — {slot}</h2>'
            f'<p>Report generation encountered an error. Check logs.</p>'
            f'<p><em>{DISCLAIMER}</em></p>'
            f'</body></html>'
        )

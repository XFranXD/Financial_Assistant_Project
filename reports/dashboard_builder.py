"""
reports/dashboard_builder.py
Builds static HTML dashboard pages for GitHub Pages.
Called from main.py step 28b — after build_intraday_report() completes.
NEVER raises — all failures logged and skipped safely.

Does NOT replace any existing report output.
Reads computed data, writes to docs/ directory.
"""

import os
import json
from datetime import datetime
import pytz
from utils.logger import get_logger

log = get_logger('dashboard_builder')

DOCS_DIR  = 'docs'
DATA_DIR  = os.path.join(DOCS_DIR, 'assets', 'data')


def build_dashboard(companies: list, slot: str, indices: dict,
                    breadth: dict, regime: dict, rotation: dict) -> None:
    """
    Entry point called from main.py step 28b.
    Updates: docs/index.html, docs/rank.html, docs/assets/data/*.json
    Does not touch: docs/guide.html (static, written once)

    IMPORTANT: The docs/ directory must exist in the repository for GitHub Pages
    to serve it. If docs/ does not exist on first run, this function creates it.
    After creation, commit docs/ to the repository manually once so GitHub Pages
    can be configured to serve from the docs/ folder on the main branch.
    """
    try:
        os.makedirs(DOCS_DIR, exist_ok=True)
        os.makedirs(DATA_DIR, exist_ok=True)
        _update_reports_index(companies, slot, indices, breadth, regime)
        _update_rank_board(companies)
        _write_index_page(indices, breadth, regime)
        _write_rank_page()
        log.info('Dashboard updated successfully')
    except Exception as e:
        log.error(f'Dashboard build failed (non-fatal): {e}')


def _update_reports_index(companies, slot, indices, breadth, regime):
    index_path = os.path.join(DATA_DIR, 'reports.json')
    try:
        with open(index_path) as f:
            index = json.load(f)
    except Exception:
        index = {'reports': []}

    now_et = datetime.now(pytz.utc).astimezone(pytz.timezone('America/New_York'))
    entry = {
        'date':      now_et.strftime('%Y-%m-%d'),
        'time':      now_et.strftime('%H:%M'),
        'slot':      slot,
        'breadth':   breadth.get('label', 'unknown'),
        'regime':    regime.get('label', 'unknown'),
        'count':     len(companies),
        'tickers':   [c.get('ticker', '') for c in companies[:5]],
        'top_score': max((c.get('composite_confidence', 0) for c in companies), default=0),
    }
    index['reports'].insert(0, entry)
    index['reports'] = index['reports'][:50]

    with open(index_path, 'w') as f:
        json.dump(index, f, indent=2)


def _update_rank_board(companies):
    rank_path = os.path.join(DATA_DIR, 'rank.json')
    now_et    = datetime.now(pytz.utc).astimezone(pytz.timezone('America/New_York'))
    week_key  = now_et.strftime('%Y-W%W')

    try:
        with open(rank_path) as f:
            rank_data = json.load(f)
    except Exception:
        rank_data = {}

    if rank_data.get('week') != week_key:
        rank_data = {'week': week_key, 'stocks': {}}

    for c in companies:
        ticker   = c.get('ticker', '')
        if not ticker:
            continue
        existing = rank_data['stocks'].get(ticker, {})
        new_conf = c.get('composite_confidence', 0)
        if new_conf > existing.get('confidence', 0):
            rank_data['stocks'][ticker] = {
                'ticker':     ticker,
                'name':       c.get('company_name', ticker),
                'sector':     c.get('sector', ''),
                'price':      (c.get('current_price')
                               or c.get('financials', {}).get('current_price')),
                'confidence': round(new_conf, 1),
                'risk':       round(c.get('risk_score', 50), 1),
                'eq_score':   round(c.get('eq_score_final', 0), 1),
                'eq_label':   c.get('eq_label', ''),
                'eq_pass':    c.get('pass_tier', ''),
            }

    with open(rank_path, 'w') as f:
        json.dump(rank_data, f, indent=2)


def _write_index_page(indices, breadth, regime):
    index_path = os.path.join(DATA_DIR, 'reports.json')
    try:
        with open(index_path) as f:
            index = json.load(f)
        reports = index.get('reports', [])[:14]
    except Exception:
        reports = []

    rank_path = os.path.join(DATA_DIR, 'rank.json')
    try:
        with open(rank_path) as f:
            rank_data = json.load(f)
        top_stocks = sorted(
            rank_data.get('stocks', {}).values(),
            key=lambda x: x.get('confidence', 0),
            reverse=True
        )[:5]
    except Exception:
        top_stocks = []

    now_et = datetime.now(pytz.utc).astimezone(pytz.timezone('America/New_York'))
    html = _render_index_html(reports, top_stocks, indices, breadth, regime, now_et)

    with open(os.path.join(DOCS_DIR, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html)


def _write_rank_page():
    rank_path = os.path.join(DATA_DIR, 'rank.json')
    try:
        with open(rank_path) as f:
            rank_data = json.load(f)
        stocks = sorted(
            rank_data.get('stocks', {}).values(),
            key=lambda x: x.get('confidence', 0),
            reverse=True
        )
        week = rank_data.get('week', '')
    except Exception:
        stocks = []
        week   = ''

    html = _render_rank_html(stocks, week)
    with open(os.path.join(DOCS_DIR, 'rank.html'), 'w', encoding='utf-8') as f:
        f.write(html)


def _nav_html(active: str) -> str:
    pages  = [('index.html', 'HOME'), ('rank.html', 'RANK'), ('guide.html', 'GUIDE')]
    links  = []
    for href, label in pages:
        is_active = (label.lower() == active.lower())
        color     = '#ffffff' if is_active else '#8888aa'
        underline = 'text-decoration:underline;' if is_active else ''
        links.append(
            f'<a href="{href}" style="color:{color};{underline}'
            f'text-decoration-color:#00aaff;margin:0 12px;'
            f'font-family:monospace;font-size:13px;">{label}</a>'
        )
    return (
        '<div style="background:#0f0f1a;border-bottom:1px solid #1e1e3a;'
        'padding:12px 24px;display:flex;align-items:center;justify-content:space-between;">'
        '<span style="color:#ffffff;font-family:monospace;font-weight:bold;font-size:14px;">'
        'STOCK RESEARCH</span>'
        f'<div>{"".join(links)}</div>'
        '</div>'
    )


def _breadth_color(label: str) -> str:
    if 'weak' in label.lower():   return '#ff3355'
    if 'strong' in label.lower(): return '#00ff88'
    return '#ffcc00'


def _conf_color(score: float) -> str:
    if score >= 70: return '#00ff88'
    if score >= 60: return '#ffcc00'
    return '#ff3355'


def _render_index_html(reports, top_stocks, indices, breadth, regime, now_et) -> str:
    dow    = indices.get('dow', {})
    sp     = indices.get('sp500', {})
    nas    = indices.get('nasdaq', {})

    def idx_html(name, data):
        val   = data.get('value')
        chg   = data.get('change_pct', 0) or 0
        label = data.get('label', '')
        color = '#00ff88' if chg > 0 else '#ff3355' if chg < 0 else '#8888aa'
        arrow = '▲' if chg > 0 else '▼' if chg < 0 else '–'
        val_s = f'{val:,.0f}' if val else 'n/a'
        return (
            f'<div style="background:#0f0f1a;border:1px solid #1e1e3a;'
            f'border-radius:6px;padding:14px;text-align:center;">'
            f'<div style="color:#8888aa;font-size:11px;text-transform:uppercase;'
            f'letter-spacing:.08em;margin-bottom:6px;">{name}</div>'
            f'<div style="color:#e8e8f0;font-size:20px;font-weight:bold;'
            f'font-family:monospace;">{val_s}</div>'
            f'<div style="color:{color};font-size:13px;margin-top:4px;">'
            f'{arrow} {abs(chg):.1f}% {label}</div>'
            f'</div>'
        )

    pulse = (
        '<div style="display:grid;grid-template-columns:repeat(3,1fr);'
        'gap:12px;margin-bottom:20px;">'
        + idx_html('Dow Jones', dow)
        + idx_html('S&P 500', sp)
        + idx_html('Nasdaq', nas)
        + '</div>'
    )

    b_color  = _breadth_color(breadth.get('label', ''))
    b_label  = breadth.get('label', 'unknown')
    r_label  = regime.get('label', 'unknown')

    status = (
        f'<div style="background:#0f0f1a;border:1px solid #1e1e3a;border-radius:6px;'
        f'padding:10px 16px;margin-bottom:20px;font-family:monospace;font-size:13px;">'
        f'<span style="color:#8888aa;">BREADTH: </span>'
        f'<span style="color:{b_color};">{b_label.upper()}</span>'
        f'&nbsp;&nbsp;&nbsp;'
        f'<span style="color:#8888aa;">MARKET: </span>'
        f'<span style="color:#e8e8f0;">{r_label}</span>'
        f'</div>'
    )

    rank_html = ''
    if top_stocks:
        rows = ''
        for i, s in enumerate(top_stocks, 1):
            conf  = s.get('confidence', 0)
            color = _conf_color(conf)
            rows += (
                f'<div style="display:flex;justify-content:space-between;'
                f'padding:6px 0;border-bottom:1px solid #1e1e3a;font-size:13px;">'
                f'<span style="color:#8888aa;">#{i}</span>'
                f'<span style="color:#e8e8f0;font-weight:bold;">{s.get("ticker","")}</span>'
                f'<span style="color:#8888aa;">{s.get("sector","").replace("_"," ").title()}</span>'
                f'<span style="color:{color};">{conf:.0f}/100</span>'
                f'</div>'
            )
        rank_html = (
            f'<div style="background:#0f0f1a;border:1px solid #1e1e3a;border-radius:6px;'
            f'padding:14px 16px;margin-bottom:20px;">'
            f'<div style="color:#8888aa;font-size:11px;text-transform:uppercase;'
            f'letter-spacing:.08em;margin-bottom:10px;">THIS WEEK\'S BEST</div>'
            f'{rows}'
            f'<div style="margin-top:10px;font-size:12px;">'
            f'<a href="rank.html" style="color:#00aaff;">→ Full rank board</a></div>'
            f'</div>'
        )

    cards = ''
    for r in reports:
        date      = r.get('date', '')
        time_s    = r.get('time', '')
        slot      = r.get('slot', '')
        count     = r.get('count', 0)
        b         = r.get('breadth', '')
        tickers   = ', '.join(r.get('tickers', []))
        top_score = r.get('top_score', 0)
        b_col     = _breadth_color(b)

        cards += (
            f'<div class="report-card" style="background:#0f0f1a;border:1px solid #1e1e3a;'
            f'border-radius:6px;margin-bottom:8px;overflow:hidden;'
            f'transition:border-color .2s,box-shadow .2s,transform .2s;cursor:pointer;"'
            f'onclick="this.classList.toggle(\'expanded\')">'
            f'<div style="padding:12px 16px;display:flex;justify-content:space-between;'
            f'align-items:center;">'
            f'<div style="font-family:monospace;font-size:13px;">'
            f'<span style="color:#e8e8f0;">{date}</span>'
            f'<span style="color:#8888aa;"> · {time_s} · {slot} · {count} stock{"s" if count!=1 else ""}</span>'
            f'</div>'
            f'<div style="color:{b_col};font-size:11px;text-transform:uppercase;">{b}</div>'
            f'</div>'
            f'<div class="report-card-body" style="max-height:0;overflow:hidden;'
            f'transition:max-height .4s cubic-bezier(.4,0,.2,1),opacity .3s;opacity:0;">'
            f'<div style="padding:0 16px 14px;border-top:1px solid #1e1e3a;">'
            f'<div style="font-family:monospace;font-size:12px;color:#8888aa;margin-top:8px;">'
            f'Tickers: <span style="color:#e8e8f0;">{tickers}</span></div>'
            f'<div style="font-family:monospace;font-size:12px;color:#8888aa;margin-top:4px;">'
            f'Top score: <span style="color:#00ff88;">{top_score:.0f}/100</span></div>'
            f'</div></div>'
            f'</div>'
        )

    if not cards:
        cards = '<div style="color:#8888aa;font-size:13px;font-family:monospace;">No reports yet.</div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stock Research Dashboard</title>
<link rel="stylesheet" href="assets/style.css">
<style>
  body{{background:#0a0a0f;color:#e8e8f0;margin:0;padding:0;font-family:'JetBrains Mono','Fira Code','Courier New',monospace;}}
  .wrap{{max-width:900px;margin:0 auto;padding:24px 16px;}}
  .report-card:hover{{border-color:#3a3a70!important;box-shadow:0 0 20px rgba(58,58,112,.3);transform:translateY(-1px);}}
  .report-card.expanded .report-card-body{{max-height:200px!important;opacity:1!important;}}
  .stagger-item{{opacity:0;transform:translateY(8px);animation:fadeUp .4s ease forwards;}}
  @keyframes fadeUp{{to{{opacity:1;transform:translateY(0);}}}}
  .stagger-item:nth-child(1){{animation-delay:.05s;}}
  .stagger-item:nth-child(2){{animation-delay:.10s;}}
  .stagger-item:nth-child(3){{animation-delay:.15s;}}
  .stagger-item:nth-child(4){{animation-delay:.20s;}}
  .stagger-item:nth-child(5){{animation-delay:.25s;}}
</style>
</head>
<body>
{_nav_html('home')}
<div class="wrap">
  <h1 style="color:#ffffff;font-size:22px;margin:20px 0 4px;">STOCK RESEARCH</h1>
  <div style="color:#8888aa;font-size:12px;margin-bottom:20px;">{now_et.strftime('%Y-%m-%d %H:%M ET')}</div>
  <div class="stagger-item">{pulse}</div>
  <div class="stagger-item">{status}</div>
  <div class="stagger-item">{rank_html}</div>
  <div class="stagger-item">
    <div style="color:#8888aa;font-size:11px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px;">RECENT REPORTS</div>
    {cards}
  </div>
</div>
<div style="text-align:center;padding:20px;color:#444466;font-size:11px;font-family:monospace;">
  Free-tier data only &nbsp;·&nbsp; Not investment advice &nbsp;·&nbsp; Always verify before acting
</div>
</body>
</html>"""


def _render_rank_html(stocks, week) -> str:
    rows = ''
    for i, s in enumerate(stocks, 1):
        conf   = s.get('confidence', 0)
        risk   = s.get('risk', 50)
        color  = _conf_color(conf)
        price  = s.get('price')
        price_s = f'${price:,.2f}' if price else 'n/a'
        rows += (
            f'<tr style="border-bottom:1px solid #1e1e3a;transition:background .15s;"'
            f'onmouseover="this.style.background=\'#1f1f40\'"'
            f'onmouseout="this.style.background=\'transparent\'">'
            f'<td style="color:#8888aa;padding:8px 12px;font-size:13px;">#{i}</td>'
            f'<td style="color:#e8e8f0;font-weight:bold;padding:8px 12px;">{s.get("ticker","")}</td>'
            f'<td style="color:#e8e8f0;padding:8px 12px;">{s.get("name","")}</td>'
            f'<td style="color:#8888aa;padding:8px 12px;font-size:12px;">'
            f'{s.get("sector","").replace("_"," ").title()}</td>'
            f'<td style="padding:8px 12px;font-family:monospace;">{price_s}</td>'
            f'<td style="color:{color};font-weight:bold;padding:8px 12px;">{conf:.0f}</td>'
            f'<td style="color:#8888aa;padding:8px 12px;">{risk:.0f}</td>'
            f'</tr>'
        )

    if not rows:
        rows = ('<tr><td colspan="7" style="text-align:center;color:#8888aa;'
                'padding:20px;font-size:13px;">No stocks ranked this week yet.</td></tr>')

    week_display = week.replace('W', ' week ') if week else 'current week'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Weekly Rank Board</title>
<link rel="stylesheet" href="assets/style.css">
<style>
  body{{background:#0a0a0f;color:#e8e8f0;margin:0;padding:0;font-family:'JetBrains Mono','Fira Code','Courier New',monospace;}}
  .wrap{{max-width:900px;margin:0 auto;padding:24px 16px;}}
  table{{width:100%;border-collapse:collapse;}}
  th{{color:#8888aa;font-size:11px;text-transform:uppercase;letter-spacing:.08em;padding:8px 12px;text-align:left;border-bottom:2px solid #1e1e3a;}}
</style>
</head>
<body>
{_nav_html('rank')}
<div class="wrap">
  <h1 style="color:#ffffff;font-size:20px;margin:20px 0 4px;">WEEKLY RANK BOARD</h1>
  <div style="color:#8888aa;font-size:12px;margin-bottom:20px;">{week_display} — resets every Monday</div>
  <table>
    <thead>
      <tr>
        <th>Rank</th><th>Ticker</th><th>Name</th><th>Sector</th>
        <th>Price</th><th>Confidence</th><th>Risk</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</div>
<div style="text-align:center;padding:20px;color:#444466;font-size:11px;font-family:monospace;">
  Free-tier data only &nbsp;·&nbsp; Not investment advice
</div>
</body>
</html>"""

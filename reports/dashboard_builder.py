"""
reports/dashboard_builder.py
Builds static HTML dashboard pages for GitHub Pages.
Called from main.py step 28b — after build_intraday_report() completes.
NEVER raises — all failures logged and skipped safely.
"""

import html
import json
import math
import os
from datetime import datetime

import pytz

from utils.logger import get_logger

log = get_logger('dashboard_builder')

DOCS_DIR = 'docs'
DATA_DIR = os.path.join(DOCS_DIR, 'assets', 'data')

_FONTS_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link href="https://fonts.googleapis.com/css2?family=Orbitron'
    ':wght@400;600;700;900&family=Share+Tech+Mono&display=swap" rel="stylesheet">'
)
_CHARTJS = '<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js" defer></script>'
_EM = '\u2014'  # em dash — safe to use inside f-string expressions

_LOADER_CSS = (
    '<style>'
    '#mre-loader{'
        'position:fixed;inset:0;z-index:9999;'
        'background:#0a0a12;'
        'display:flex;flex-direction:column;align-items:center;justify-content:center;gap:20px;'
        'transition:opacity 0.4s ease;'
    '}'
    '#mre-loader.done{opacity:0;pointer-events:none;}'
    '.mre-bar-shell{'
        'position:relative;width:280px;height:40px;'
        'border:2px solid #c850c0;border-radius:6px;padding:5px;'
        'box-shadow:0 0 8px #c850c080,0 0 20px #c850c040,inset 0 0 6px #c850c020;'
        'overflow:hidden;'
    '}'
    '.mre-bar-shell::after{'
        'content:\'\';position:absolute;inset:0;'
        'background:repeating-linear-gradient('
            '90deg,'
            'transparent,'
            'transparent calc(100% / 10 - 3px),'
            '#0a0a12 calc(100% / 10 - 3px),'
            '#0a0a12 calc(100% / 10)'
        ');'
        'pointer-events:none;z-index:2;'
    '}'
    '.mre-bar-fill{'
        'height:100%;width:0%;border-radius:2px;'
        'background:linear-gradient(90deg,#5c6fff,#9b59ff,#c850c0);'
        'box-shadow:0 0 12px #9b59ff80;'
        'position:relative;z-index:1;'
        'transition:width 0.05s linear;'
    '}'
    '#mre-loader-text{'
        'font-family:\'Orbitron\',sans-serif;font-size:13px;'
        'letter-spacing:0.25em;color:#9b59ff;'
        'text-shadow:0 0 10px #9b59ff80;'
        'min-width:130px;text-align:center;'
    '}'
    '</style>'
)

_LOADER_HTML = (
    '<div id="mre-loader">'
    '<div class="mre-bar-shell"><div class="mre-bar-fill" id="mre-bar-fill"></div></div>'
    '<div id="mre-loader-text">LOADING</div>'
    '</div>'
)

_LOADER_JS = (
    '<script>'
    '(function(){'
    'var _li=0,_ls=["LOADING","LOADING.","LOADING..","LOADING..."];'
    'var _lt=document.getElementById("mre-loader-text");'
    'var _lp=setInterval(function(){_li=(_li+1)%4;if(_lt)_lt.textContent=_ls[_li];},420);'
    'var _bf=document.getElementById("mre-bar-fill");'
    'var _bt=null;'
    'function _bStep(ts){'
    'if(!_bt)_bt=ts;'
    'var prog=Math.min((ts-_bt)/1800,1);'
    'var ease=1-Math.pow(1-prog,3);'
    'if(_bf)_bf.style.width=(ease*100)+"%";'
    'if(prog<1)requestAnimationFrame(_bStep);'
    '}'
    'requestAnimationFrame(_bStep);'
    'window.dismissLoader=function(){'
    'clearInterval(_lp);'
    'if(_bf)_bf.style.width="100%";'
    'setTimeout(function(){'
    'var el=document.getElementById("mre-loader");'
    'if(el){el.classList.add("done");setTimeout(function(){if(el.parentNode)el.parentNode.removeChild(el);},450);}'
    '},120);'
    '};'
    '})();'
    '</script>'
)

_INDEX_FETCH_JS = (
    "// ── Rank preview fetch ───────────────────────────────────────────────────\n"
    "fetch('assets/data/rank.json?v='+Date.now())\n"
    "  .then(function(r){ return r.ok ? r.json() : Promise.reject(r.status); })\n"
    "  .then(function(rankData) {\n"
    "    var stocks = rankData.stocks || {};\n"
    "    var arr = Array.isArray(stocks) ? stocks : Object.values(stocks);\n"
    "    arr = arr.filter(function(s){ return s && typeof s === 'object'; });\n"
    "    arr.sort(function(a,b){\n"
    "      var ca = typeof a.confidence === 'number' ? a.confidence : -1;\n"
    "      var cb = typeof b.confidence === 'number' ? b.confidence : -1;\n"
    "      return cb - ca;\n"
    "    });\n"
    "    var top5 = arr.slice(0, 5);\n"
    "    var rows = '';\n"
    "    top5.forEach(function(s, idx) {\n"
    "      var i    = idx + 1;\n"
    "      var conf = typeof s.confidence === 'number' ? s.confidence : null;\n"
    "      var cCls = conf === null ? 'nt' : conf >= 70 ? 'up' : conf >= 50 ? 'nt' : 'dn';\n"
    "      var eqV  = s.eq_verdict_display  || '';\n"
    "      var eqCls  = eqV  === 'STRONG'  ? 'up' : eqV  === 'WEAK'    ? 'dn' : 'nt';\n"
    "      var rotS = s.rotation_signal_display || '';\n"
    "      var rotCls = rotS === 'LEADING' ? 'up' : rotS === 'LAGGING' ? 'dn' : 'nt';\n"
    "      var verdict  = s.market_verdict_display || s.market_verdict || '\\u2014';\n"
    "      var confStr  = conf !== null ? Math.round(conf) : '\\u2014';\n"
    "      var riskStr  = typeof s.risk_score === 'number' ? Math.round(s.risk_score) : '\\u2014';\n"
    "      var ret1m = typeof s.return_1m === 'number' ? (s.return_1m >= 0 ? '\\u25b2' : '\\u25bc') + ' ' + Math.abs(s.return_1m).toFixed(1) + '%' : '\\u2014';\n"
    "      var ret3m = typeof s.return_3m === 'number' ? (s.return_3m >= 0 ? '\\u25b2' : '\\u25bc') + ' ' + Math.abs(s.return_3m).toFixed(1) + '%' : '\\u2014';\n"
    "      var ret6m = typeof s.return_6m === 'number' ? (s.return_6m >= 0 ? '\\u25b2' : '\\u25bc') + ' ' + Math.abs(s.return_6m).toFixed(1) + '%' : '\\u2014';\n"
    "      var rpConfVal = typeof s.confidence === 'number' ? s.confidence : null;\n"
    "      var rpConf    = rpConfVal !== null ? Math.round(rpConfVal) : '\\u2014';\n"
    "      var rpConfCls = rpConfVal !== null ? (rpConfVal >= 70 ? 'rpill-cup' : rpConfVal >= 50 ? 'rpill-cnt' : 'rpill-cdn') : 'rpill-una';\n"
    "      var rpPrice   = typeof s.price === 'number' ? '$' + s.price.toFixed(2) : '\\u2014';\n"
    "      var sector    = (s.sector || '').replace(/_/g,' ').replace(/\\b\\w/g, function(c){ return c.toUpperCase(); });\n"
    "      var _sMap={'Energy':'#f4a44a','Technology':'#7dd8ff','Healthcare':'#7be8b0','Financials':'#c9b8ff',\n"
    "        'Consumer Discretionary':'#ff9ec4','Consumer Staples':'#b8e8c8','Industrials':'#ffd27a',\n"
    "        'Materials':'#a8e6cf','Real Estate':'#ffb8a0','Utilities':'#9ecfff',\n"
    "        'Communication Services':'#d4b8ff'};\n"
    "      var _sKey=_sMap[sector]?sector:Object.keys(_sMap).find(function(k){return sector.toLowerCase().indexOf(k.toLowerCase())!==-1;})||'';\n"
    "      var sectorColor=_sMap[_sKey]||'#a89bc2';\n"
    # ── PS fields for Top 5 preview ──────────────────────────────────────────
    "      var psEntry   = s.ps_verdict_display || '\\u2014';\n"
    "      var psKeyLvl  = s.ps_key_level_display || s.ps_key_level || '\\u2014';\n"
    "      var psMoveExt = typeof s.ps_move_extension_pct === 'number' ? s.ps_move_extension_pct.toFixed(1) + '%' : '\\u2014';\n"
    "      rows += '<div class=\"rank-card\" onclick=\"rpT(\\'rp' + i + '\\')\">'\n"
    "            + '<div class=\"rank-card-main\">'\n"
    "            + '<div class=\"rck-n\">#' + i + '</div>'\n"
    "            + '<div class=\"rck-t\">' + (s.ticker || '\\u2014') + '</div>'\n"
    "            + '<div class=\"rck-s\" style=\"color:' + sectorColor + '\">' + sector + '</div>'\n"
    "            + '<div class=\"rck-pills\">'\n"
    "            + '<span class=\"rpill rpill-price\"><span class=\"rpill-lbl\">Price</span>' + rpPrice + '</span>'\n"
    "            + '<span class=\"rpill ' + rpConfCls + '\"><span class=\"rpill-lbl\">Conf</span>' + rpConf + '/100</span>'\n"
    "            + '</div>'\n"
    "            + '</div>'\n"
    "            + '<div class=\"rp-exp\" id=\"rp' + i + '\"><div class=\"rp-exp-inner\">'\n"
    "            + '<div class=\"pex-item\"><div class=\"pex-k\">1M Return</div><div class=\"pex-v\">' + ret1m + '</div></div>'\n"
    "            + '<div class=\"pex-item\"><div class=\"pex-k\">3M Return</div><div class=\"pex-v\">' + ret3m + '</div></div>'\n"
    "            + '<div class=\"pex-item\"><div class=\"pex-k\">6M Return</div><div class=\"pex-v\">' + ret6m + '</div></div>'\n"
    "            + '<div class=\"pex-item\"><div class=\"pex-k\">Verdict</div><div class=\"pex-v ' + cCls + '\">' + verdict + '</div></div>'\n"
    "            + '<div class=\"pex-item\"><div class=\"pex-k\">Entry</div><div class=\"pex-v\">' + psEntry + '</div></div>'\n"
    "            + '<div class=\"pex-item\"><div class=\"pex-k\">Key Level</div><div class=\"pex-v\">' + psKeyLvl + '</div></div>'\n"
    "            + '<div class=\"pex-item\"><div class=\"pex-k\">Move Ext.</div><div class=\"pex-v\">' + psMoveExt + '</div></div>'\n"
    "            + '</div></div>'\n"
    "            + '</div>';\n"
    "    });\n"
    "    if (!rows) rows = '<div style=\"padding:14px 18px;color:var(--mist);font-size:11px;\">No candidates this week.</div>';\n"
    "    document.getElementById('rank-preview-mount').innerHTML =\n"
    "        '<div class=\"rank-preview\">'\n"
    "      + '<div class=\"rank-preview-head\">'\n"
    "      + '<span class=\"rank-preview-title\">Top 5 Candidates \\u00b7 Week Rank</span>'\n"
    "      + '<a href=\"rank.html\" class=\"rp-link\">Full \\u2192</a>'\n"
    "      + '</div>'\n"
    "      + rows\n"
    "      + '</div>';\n"
    "    document.querySelectorAll('#rank-preview-mount .rank-card').forEach(function(card, i) {\n"
    "      card.style.animation = 'none';\n"
    "      card.offsetHeight;\n"
    "      card.style.animation = 'stagger-up 0.52s cubic-bezier(0.16,1,0.3,1) both ' + (0.05 + i * 0.07) + 's';\n"
    "    });\n"
    "  })\n"
    "  .catch(function() {\n"
    "    document.getElementById('rank-preview-mount').innerHTML =\n"
    "      '<div style=\"color:var(--dn);font-family:var(--ff-mono);font-size:11px;padding:14px;\">Error loading rank data.</div>';\n"
    "  });\n"
    "\n"
    "// ── Report cards fetch ───────────────────────────────────────────────────\n"
    "// NOTE: dismissLoader() is called here (reports fetch), not in rank fetch,\n"
    "// because this is the last fetch to resolve. Both .then and .catch call it.\n"
    "fetch('assets/data/reports.json?v='+Date.now())\n"
    "  .then(function(r){ return r.ok ? r.json() : Promise.reject(r.status); })\n"
    "  .then(function(data) {\n"
    "    var reports = Array.isArray(data.reports) ? data.reports.slice(0, 14) : [];\n"
    "    var html = '';\n"
    "    reports.forEach(function(r, idx) {\n"
    "      var vc = r.verdicts || {};\n"
    "      var rnC, wC, sC;\n"
    "      if (Array.isArray(vc)) {\n"
    "        rnC = vc.filter(function(v){ return v === 'RESEARCH NOW'; }).length;\n"
    "        wC  = vc.filter(function(v){ return v === 'WATCH'; }).length;\n"
    "        sC  = vc.filter(function(v){ return v === 'SKIP'; }).length;\n"
    "      } else {\n"
    "        rnC = (typeof vc['RESEARCH NOW'] === 'number') ? vc['RESEARCH NOW'] : 0;\n"
    "        wC  = (typeof vc['WATCH']        === 'number') ? vc['WATCH']        : 0;\n"
    "        sC  = (typeof vc['SKIP']         === 'number') ? vc['SKIP']         : 0;\n"
    "      }\n"
    "      var tickers  = Array.isArray(r.tickers) ? r.tickers.join(', ') : '\\u2014';\n"
    "      var topScore = typeof r.top_score === 'number' ? Math.round(r.top_score) : '\\u2014';\n"
    "      var b        = r.breadth || '';\n"
    "      var bCls     = b === 'BULLISH' ? 'up' : b === 'BEARISH' ? 'dn' : 'nt';\n"
    "      var bTitle   = b.charAt(0).toUpperCase() + b.slice(1).toLowerCase();\n"
    "      var count    = r.count || 0;\n"
    "      var regimeRaw = (r.regime || '').toLowerCase();\n"
    "      var regimeLabel = (r.regime || '').replace(/\\b\\w/g, function(c){ return c.toUpperCase(); });\n"
    "      var regimeCls = regimeRaw.indexOf('calm') !== -1 ? 'regime-calm' : regimeRaw.indexOf('normal') !== -1 ? 'regime-normal' : regimeRaw.indexOf('elevated') !== -1 ? 'regime-elevated' : regimeRaw.indexOf('stress') !== -1 ? 'regime-crisis' : 'regime-normal';\n"
    "      var regimeBadge = '<span class=\"regime-badge ' + regimeCls + '\">' + regimeLabel + '</span>';\n"
    "      var uid      = 'prompt_' + (idx + 1);\n"
    "      var promptText  = r.prompt || '';\n"
    "      var scriptBlock = '';\n"
    "      var copyBtn     = '';\n"
    "      if (promptText) {\n"
    "        var safePrompt = JSON.stringify(promptText).replace(/<\\/script>/gi, '<\\\\/script>');\n"
    "        scriptBlock = '<script type=\"application/json\" id=\"' + uid + '\">' + safePrompt + '<\\/script>';\n"
    "        copyBtn = '<button class=\"btn mg copy-prompt-btn\" data-ref=\"' + uid + '\">\\u29c9 Copy AI Prompt</button>';\n"
    "      }\n"
    "      var reportUrl = r.report_url || '';\n"
    "      var fullBtn = reportUrl\n"
    "        ? '<a href=\"' + reportUrl + '\" class=\"btn\" target=\"_blank\" onclick=\"event.stopPropagation()\">\\u2197 Full Report</a>'\n"
    "        : '';\n"
    "      html += scriptBlock\n"
    "           + '<div class=\"rcard\" onclick=\"rcT(this)\">'\n"
    "           + '<div class=\"rcard-head\"><div>'\n"
    "           + '<div class=\"rcard-date\">' + (r.date || '') + ' \\u00b7 ' + (r.slot || '') + ' \\u00b7 ' + count + ' stock' + (count !== 1 ? 's' : '') + '</div>'\n"
    "           + '<div class=\"rcard-slot\" style=\"font-size:11px;color:var(--mist);\">' + (r.time || '') + ' ET \\u00b7 ' + regimeBadge + '</div>'\n"
    "           + '</div>'\n"
    "           + '<span class=\"rcard-badge ' + bCls + '\">' + bTitle + '</span>'\n"
    "           + '</div>'\n"
    "           + '<div class=\"rcard-body\"><div class=\"rcard-inner\">'\n"
    "           + '<div class=\"rcard-cols\">'\n"
    "           + '<div><div class=\"rcc-k\">Sys 1 \\u00b7 Tickers</div><div class=\"rcc-v\">' + tickers\n"
    "           + '<br><span class=\"top-conf-val\" style=\"font-size:11px;\">Confidence: ' + topScore + '/100</span></div></div>'\n"
    "           + '<div><div class=\"rcc-k\">Verdicts</div><div class=\"rcc-v\">'\n"
    "           + '<span style=\"color:var(--up)\">RN:' + rnC + '</span> '\n"
    "           + '<span style=\"color:var(--nt)\">W:' + wC + '</span> '\n"
    "           + '<span style=\"color:var(--dn)\">S:' + sC + '</span></div></div>'\n"
    "           + '<div><div class=\"rcc-k\">Breadth</div><div class=\"rcc-v\" style=\"color:var(--' + bCls + ')\">' + bTitle + '</div></div>'\n"
    "           + '</div>'\n"
    "           + '<div class=\"rcard-btns\">' + fullBtn + copyBtn + '</div>'\n"
    "           + '</div></div></div>';\n"
    "    });\n"
    "    if (!html) html = '<div style=\"color:var(--mist);font-family:var(--ff-mono);font-size:11px;\">No reports yet.</div>';\n"
    "    document.getElementById('report-cards-mount').innerHTML = html;\n"
    "    // ── Dismiss loader after final data is in the DOM ──\n"
    "    if (window.dismissLoader) window.dismissLoader();\n"
    "  })\n"
    "  .catch(function() {\n"
    "    document.getElementById('report-cards-mount').innerHTML =\n"
    "      '<div style=\"color:var(--dn);font-family:var(--ff-mono);font-size:11px;padding:14px;\">Error loading reports. Try refreshing.</div>';\n"
    "    if (window.dismissLoader) window.dismissLoader();\n"
    "  });\n"
)

_RANK_FETCH_JS = (
    "fetch('assets/data/rank.json?v='+Date.now())\n"
    "  .then(function(r){ return r.ok ? r.json() : Promise.reject(r.status); })\n"
    "  .then(function(rankData) {\n"
    "    var stocks = rankData.stocks || {};\n"
    "    var arr = Array.isArray(stocks) ? stocks : Object.values(stocks);\n"
    "    arr = arr.filter(function(s){ return s && typeof s === 'object'; });\n"
    "    arr.sort(function(a,b){\n"
    "      var ca = typeof a.confidence === 'number' ? a.confidence : -1;\n"
    "      var cb = typeof b.confidence === 'number' ? b.confidence : -1;\n"
    "      return cb - ca;\n"
    "    });\n"
    "    var html    = '';\n"
    "    var scripts = '';\n"
    "    arr.forEach(function(stock, idx) {\n"
    "      var i    = idx + 1;\n"
    "      var conf = typeof stock.confidence === 'number' ? stock.confidence : null;\n"
    "      var risk = typeof stock.risk_score  === 'number' ? stock.risk_score  : null;\n"
    "      var cCls   = conf === null ? 'nt' : conf >= 70 ? 'up' : conf >= 50 ? 'nt' : 'dn';\n"
    "      var eqV    = stock.eq_verdict_display  || '';\n"
    "      var eqCls  = eqV  === 'STRONG'  ? 'up' : eqV  === 'WEAK'    ? 'dn' : 'nt';\n"
    "      var rotS   = stock.rotation_signal_display || '';\n"
    "      var rotCls = rotS === 'LEADING' ? 'up' : rotS === 'LAGGING' ? 'dn' : 'nt';\n"
    "      var psV    = stock.ps_verdict_display  || '';\n"
    "      var psCls  = psV  === 'GOOD'     ? 'up' : psV  === 'EXTENDED' ? 'dn' : psV === 'WEAK' ? 'dn' : psV === 'EARLY' ? 'nt' : 'pu';\n"
    "      var verdict  = stock.market_verdict_display || stock.market_verdict || '\\u2014';\n"
    "      var confStr  = conf !== null ? Math.round(conf) : '\\u2014';\n"
    "      var riskStr  = risk !== null ? Math.round(risk)  : '\\u2014';\n"
    "      var price    = typeof stock.price === 'number' ? '$' + stock.price.toFixed(2) : '\\u2014';\n"
    "      var alignVal = stock.alignment || '';\n"
    "      var aCls     = alignVal === 'ALIGNED' ? 'up' : alignVal === 'MIXED' ? 'nt' : 'dn';\n"
    "      var sector    = (stock.sector || '').replace(/_/g,' ').replace(/\\b\\w/g, function(c){ return c.toUpperCase(); });\n"
    "      var _sMap={'Energy':'#f4a44a','Technology':'#7dd8ff','Healthcare':'#7be8b0','Financials':'#c9b8ff',\n"
    "        'Consumer Discretionary':'#ff9ec4','Consumer Staples':'#b8e8c8','Industrials':'#ffd27a',\n"
    "        'Materials':'#a8e6cf','Real Estate':'#ffb8a0','Utilities':'#9ecfff',\n"
    "        'Communication Services':'#d4b8ff'};\n"
    "      var _sKey=_sMap[sector]?sector:Object.keys(_sMap).find(function(k){return sector.toLowerCase().indexOf(k.toLowerCase())!==-1;})||'';\n"
    "      var sectorColor=_sMap[_sKey]||'#a89bc2';\n"
    "      var ret1m = typeof stock.return_1m === 'number' ? (stock.return_1m >= 0 ? '\\u25b2' : '\\u25bc') + ' ' + Math.abs(stock.return_1m).toFixed(1) + '%' : '\\u2014';\n"
    "      var ret3m = typeof stock.return_3m === 'number' ? (stock.return_3m >= 0 ? '\\u25b2' : '\\u25bc') + ' ' + Math.abs(stock.return_3m).toFixed(1) + '%' : '\\u2014';\n"
    "      var ret6m = typeof stock.return_6m === 'number' ? (stock.return_6m >= 0 ? '\\u25b2' : '\\u25bc') + ' ' + Math.abs(stock.return_6m).toFixed(1) + '%' : '\\u2014';\n"
    "      var raw1m = typeof stock.return_1m === 'number' ? (stock.return_1m >= 0 ? '\\u25b2' : '\\u25bc') + '|' + Math.abs(stock.return_1m).toFixed(1) + '|%' : '';\n"
    "      var raw3m = typeof stock.return_3m === 'number' ? (stock.return_3m >= 0 ? '\\u25b2' : '\\u25bc') + '|' + Math.abs(stock.return_3m).toFixed(1) + '|%' : '';\n"
    "      var raw6m = typeof stock.return_6m === 'number' ? (stock.return_6m >= 0 ? '\\u25b2' : '\\u25bc') + '|' + Math.abs(stock.return_6m).toFixed(1) + '|%' : '';\n"
    "      var phUid  = 'ph-' + i;\n"
    "      var rawPh  = Array.isArray(stock.price_history) ? stock.price_history : [];\n"
    "      var phList = rawPh.filter(function(v){ return typeof v === 'number' && isFinite(v); });\n"
    "      var hasCh  = phList.length > 1;\n"
    "      var chartEl = hasCh\n"
    "        ? '<canvas id=\"ec' + i + '\" height=\"92\"></canvas>'\n"
    "        : '<div style=\"color:var(--mist);font-size:11px;padding:8px 0;\">Price history unavailable</div>';\n"
    "      scripts += '<script type=\"application/json\" id=\"' + phUid + '\">'\n"
    "              + JSON.stringify(phList).replace(/<\\/script>/gi,'<\\\\/script>')\n"
    "              + '<\\/script>';\n"
    "      var confVal    = typeof stock.confidence === 'number' ? stock.confidence : null;\n"
    "      var riskVal    = typeof stock.risk_score === 'number' ? stock.risk_score : null;\n"
    "      var confCls    = confVal !== null ? (confVal >= 70 ? 'rpill-cup' : confVal >= 50 ? 'rpill-cnt' : 'rpill-cdn') : 'rpill-una';\n"
    "      var riskCls    = riskVal !== null ? (riskVal <= 30 ? 'rpill-rlo' : riskVal <= 55 ? 'rpill-rmd' : 'rpill-rhi') : 'rpill-una';\n"
    "      var eqMap      = {'SUPPORTIVE':'rpill-eq-sup','NEUTRAL':'rpill-eq-neu','WEAK':'rpill-eq-wk','RISKY':'rpill-eq-rsk','UNAVAILABLE':'rpill-eq-una'};\n"
    "      var rotMap     = {'SUPPORT':'rpill-rt-sup','WAIT':'rpill-rt-wt','WEAKEN':'rpill-rt-wk','UNKNOWN':'rpill-rt-unk'};\n"
    "      var eqPillCls  = eqMap[eqV]  || 'rpill-una';\n"
    "      var rotPillCls = rotMap[rotS] || 'rpill-una';\n"
    "      var psMap      = {'GOOD':'rpill-ps-gd','EXTENDED':'rpill-ps-ex','EARLY':'rpill-ps-ea','WEAK':'rpill-ps-wk','UNAVAILABLE':'rpill-eq-una'};\n"
    "      var psPillCls  = psMap[psV]  || 'rpill-una';\n"
    "      var evMap      = {'NORMAL':'rpill-ev-ok','HIGH RISK':'rpill-ev-hr'};\n"
    "      var insMap     = {'ACCUMULATING':'rpill-ins-ac','DISTRIBUTING':'rpill-ins-di','NEUTRAL':'rpill-ins-nt','UNAVAILABLE':'rpill-ins-na'};\n"
    "      var expMap     = {'BEATING':'rpill-exp-bt','INLINE':'rpill-exp-in','MISSING':'rpill-exp-ms','UNAVAILABLE':'rpill-exp-na'};\n"
    "      var evV        = stock.event_risk        || 'NORMAL';\n"
    "      var insV       = stock.insider_signal    || 'UNAVAILABLE';\n"
    "      var evPillCls  = evMap[evV]  || 'rpill-ev-ok';\n"
    "      var insPillCls = insMap[insV] || 'rpill-ins-na';\n"
    "      var confDisp   = confVal !== null ? Math.round(confVal) : '\\u2014';\n"
    "      var riskDisp   = riskVal !== null ? Math.round(riskVal) : '\\u2014';\n"
    "      var priceDisp  = typeof stock.price === 'number' ? '$' + stock.price.toFixed(2) : '\\u2014';\n"
    # ── PS fields for weekly rank expanded row ───────────────────────────────
    "      var psKeyLvl   = stock.ps_key_level_display || stock.ps_key_level_position || '\\u2014';\n"
    "      var psPaScore  = typeof stock.ps_price_action_score === 'number' ? stock.ps_price_action_score + '/100' : '\\u2014';\n"
    "      var psMoveExt  = typeof stock.ps_move_extension_pct === 'number' ? stock.ps_move_extension_pct.toFixed(1) + '%' : '\\u2014';\n"
    "      var psTrend    = stock.ps_trend_structure || '\\u2014';\n"
    "      var psDistSup  = typeof stock.ps_distance_to_support_pct === 'number' ? stock.ps_distance_to_support_pct.toFixed(1) + '%' : '\\u2014';\n"
    "      var psDistRes  = typeof stock.ps_distance_to_resistance_pct === 'number' ? stock.ps_distance_to_resistance_pct.toFixed(1) + '%' : '\\u2014';\n"
    "      var psAvail    = stock.ps_available === true;\n"
    "      html += '<div class=\"rank-card\" data-ref=\"' + phUid + '\" data-eid=\"e' + i + '\" data-cid=\"ec' + i + '\">'\n"
    "           + '<div class=\"rank-card-main\" onclick=\"expT(this.closest(\\'.rank-card\\'))\">'  \n"
    "           + '<div class=\"rck-n\">#' + i + '</div>'\n"
    "           + '<div class=\"rck-t\">' + (stock.ticker || '\\u2014') + '</div>'\n"
    "           + '<div class=\"rck-s\" style=\"color:' + sectorColor + '\">' + sector + '</div>'\n"
    "           + '<div class=\"rck-pills\">'\n"
    "           + '<span class=\"rpill rpill-price\"><span class=\"rpill-lbl\">Price</span>' + priceDisp + '</span>'\n"
    "           + '<span class=\"rpill ' + confCls + '\"><span class=\"rpill-lbl\">Conf</span>' + confDisp + '/100</span>'\n"
    "           + '<span class=\"rpill ' + riskCls + '\"><span class=\"rpill-lbl\">Risk</span>' + riskDisp + '</span>'\n"
    "           + '<span class=\"rpill ' + eqPillCls + '\"><span class=\"rpill-lbl\">EQ</span>' + (eqV || '\\u2014') + '</span>'\n"
    "           + '<span class=\"rpill ' + rotPillCls + '\"><span class=\"rpill-lbl\">Rotation</span>' + (rotS || '\\u2014') + '</span>'\n"
    "           + '<span class=\"rpill ' + psPillCls + '\"><span class=\"rpill-lbl\">Entry</span>' + (psV || '\\u2014') + '</span>'\n"
    "           + '<span class=\"rpill ' + evPillCls + '\"><span class=\"rpill-lbl\">Event</span>' + evV + '</span>'\n"
    "           + '<span class=\"rpill ' + insPillCls + '\"><span class=\"rpill-lbl\">Insider</span>' + insV + '</span>'\n"
    "           + '</div>'\n"
    "           + '</div>'\n"
    "           + '<div class=\"exp-row\" id=\"e' + i + '\" onclick=\"event.stopPropagation()\"><div class=\"exp-inner\">'\n"
    "           + '<div class=\"exp-stats\">'\n"
    "           + '<div class=\"est\"><div class=\"est-k\">1M</div><div class=\"est-v\" data-raw=\"' + raw1m + '\">' + ret1m + '</div></div>'\n"
    "           + '<div class=\"est\"><div class=\"est-k\">3M</div><div class=\"est-v\" data-raw=\"' + raw3m + '\">' + ret3m + '</div></div>'\n"
    "           + '<div class=\"est\"><div class=\"est-k\">6M</div><div class=\"est-v\" data-raw=\"' + raw6m + '\">' + ret6m + '</div></div>'\n"
    "           + '<div class=\"est\"><div class=\"est-k\">Verdict</div><div class=\"est-v ' + cCls + '\">' + verdict + '</div></div>'\n"
    "           + '<div class=\"est\"><div class=\"est-k\">Align</div><div class=\"est-v ' + aCls + '\">' + (alignVal || '\\u2014') + '</div></div>'\n"
    # ── PS block: only rendered when ps_available is true ───────────────────
    "           + (psAvail ? ('<div class=\"est est-divider\"></div>'\n"
    "           + '<div class=\"est\"><div class=\"est-k\">Entry</div><div class=\"est-v est-ps est-ps-' + psV.toLowerCase() + '\">' + (psV || '\\u2014') + '</div></div>'\n"
    "           + '<div class=\"est\"><div class=\"est-k\">Key Level</div><div class=\"est-v\">' + psKeyLvl + '</div></div>'\n"
    "           + '<div class=\"est\"><div class=\"est-k\">PA Score</div><div class=\"est-v\">' + psPaScore + '</div></div>'\n"
    "           + '<div class=\"est\"><div class=\"est-k\">Move Ext.</div><div class=\"est-v\">' + psMoveExt + '</div></div>'\n"
    "           + '<div class=\"est\"><div class=\"est-k\">Trend</div><div class=\"est-v\">' + psTrend + '</div></div>'\n"
    "           + '<div class=\"est\"><div class=\"est-k\">Dist Sup.</div><div class=\"est-v\">' + psDistSup + '</div></div>'\n"
    "           + '<div class=\"est\"><div class=\"est-k\">Dist Res.</div><div class=\"est-v\">' + psDistRes + '</div></div>'\n"
    "           + '<div class=\"est\"><div class=\"est-k\">Entry $</div><div class=\"est-v\">' + (typeof stock.ps_entry_price==='number' ? '$'+stock.ps_entry_price.toFixed(2) : '\\u2014') + '</div></div>'\n"
    "           + '<div class=\"est\"><div class=\"est-k\">Stop $</div><div class=\"est-v\">' + (typeof stock.ps_stop_loss==='number' ? '$'+stock.ps_stop_loss.toFixed(2) : '\\u2014') + '</div></div>'\n"
    "           + '<div class=\"est\"><div class=\"est-k\">Target $</div><div class=\"est-v\">' + (typeof stock.ps_price_target==='number' ? '$'+stock.ps_price_target.toFixed(2) : '\\u2014') + '</div></div>'\n"
    "           + '<div class=\"est\"><div class=\"est-k\">R/R</div><div class=\"est-v\">' + (typeof stock.ps_risk_reward_ratio==='number' ? stock.ps_risk_reward_ratio.toFixed(2)+'x' : '\\u2014') + '</div></div>'\n"
    "           + '<div class=\"est est-divider\"></div>') : '')\n"
    "           + '<div class=\"est\"><div class=\"est-k\">Event Risk</div><div class=\"est-v\">' + (stock.event_risk || 'NORMAL') + '</div></div>'\n"
    "           + '<div class=\"est\"><div class=\"est-k\">Insider</div><div class=\"est-v\">' + (stock.insider_signal || 'N/A') + '</div></div>'\n"
    "           + '<div class=\"est\"><div class=\"est-k\">Expect.</div><div class=\"est-v\">' + (stock.expectations_signal || 'N/A') + '</div></div>'\n"
    "           + '<div class=\"est\"><div class=\"est-k\">Portfolio</div>'\n"
    "           + '<div class=\"est-v\">'\n"
    "           + (stock.pl_selected\n"
    "               ? (stock.pl_position_weight != null ? stock.pl_position_weight.toFixed(1) + '%' : 'Selected')\n"
    "               : (stock.pl_exclusion_reason || 'Excluded')) + '</div></div>'\n"
    "           + '</div>'\n"
    "           + '<div class=\"exp-chart\">' + chartEl + '</div>'\n"
    "           + '</div></div>'\n"
    "           + '</div>';\n"
    "    });\n"
    "    if (!html) html = '<div style=\"color:var(--mist);font-family:var(--ff-mono);padding:28px;\">No candidates this week.</div>';\n"
    "    // Inject script blocks first (before HTML) so they exist when onclick handlers fire\n"
    "    document.getElementById('rank-board-mount').innerHTML = scripts + html;\n"
    "    if (window.dismissLoader) window.dismissLoader();\n"
    "  })\n"
    "  .catch(function() {\n"
    "    document.getElementById('rank-board-mount').innerHTML =\n"
    "      '<div style=\"color:var(--dn);font-family:var(--ff-mono);font-size:11px;padding:28px;\">Error loading rank data. Try refreshing.</div>';\n"
    "    if (window.dismissLoader) window.dismissLoader();\n"
    "  });\n"
)

_ARCHIVE_FETCH_JS = (
    "fetch('assets/data/weekly_archive.json?v='+Date.now())\n"
    "  .then(function(r){ return r.ok ? r.json() : Promise.reject(r.status); })\n"
    "  .then(function(archiveData) {\n"
    "    var weeksRaw = archiveData.weeks || {};\n"
    "    if (typeof weeksRaw !== 'object' || Array.isArray(weeksRaw)) weeksRaw = {};\n"
    "    var weekKeys = Object.keys(weeksRaw).sort().reverse();\n"
    "    var html = '';\n"
    "    weekKeys.forEach(function(wk) {\n"
    "      var weekInfo = weeksRaw[wk];\n"
    "      var runs     = (weekInfo && Array.isArray(weekInfo.runs)) ? weekInfo.runs : [];\n"
    "      var label    = wk.replace('W', ' \\u2014 Week ');\n"
    "      var cardsHtml = '';\n"
    "      runs.forEach(function(run, runIdx) {\n"
    "        var slot      = run.slot      || '';\n"
    "        var ts        = run.timestamp || '';\n"
    "        var breadth   = run.breadth   || '';\n"
    "        var regime    = run.regime    || '';\n"
    "        var count     = run.count     || 0;\n"
    "        var runType   = run.run_type  || '';\n"
    "        var bCls      = breadth === 'BULLISH' ? 'up' : breadth === 'BEARISH' ? 'dn' : 'nt';\n"
    "        var bTitle    = breadth.charAt(0).toUpperCase() + breadth.slice(1).toLowerCase();\n"
    "        var regRaw    = regime.toLowerCase();\n"
    "        var regTitle  = regime.charAt(0).toUpperCase()  + regime.slice(1).toLowerCase();\n"
    "        var regimeCls = regRaw.indexOf('calm') !== -1 ? 'regime-calm' : regRaw.indexOf('normal') !== -1 ? 'regime-normal' : regRaw.indexOf('elevated') !== -1 ? 'regime-elevated' : regRaw.indexOf('stress') !== -1 ? 'regime-crisis' : 'regime-normal';\n"
    "        var regimeBadge = '<span class=\"regime-badge ' + regimeCls + '\">' + regTitle + '</span>';\n"
    "        var cands     = Array.isArray(run.candidates) ? run.candidates : [];\n"
    "        var tickers   = cands.slice(0,5).map(function(c){ return c.ticker||''; }).filter(Boolean).join(', ') || '\\u2014';\n"
    "        var topConf   = cands.length\n"
    "          ? Math.max.apply(null, cands.map(function(c){ return typeof c.confidence === 'number' ? c.confidence : 0; }))\n"
    "          : 0;\n"
    "        var topConfStr = topConf > 0 ? Math.round(topConf) : '\\u2014';\n"
    "        var vc  = run.verdict_counts || {};\n"
    "        var rnC = typeof vc['RESEARCH NOW'] === 'number' ? vc['RESEARCH NOW'] : 0;\n"
    "        var wC  = typeof vc['WATCH']        === 'number' ? vc['WATCH']        : 0;\n"
    "        var sC  = typeof vc['SKIP']         === 'number' ? vc['SKIP']         : 0;\n"
    "        var promptText  = run.prompt || '';\n"
    "        var scriptBlock = '';\n"
    "        var copyBtn     = '';\n"
    "        if (promptText) {\n"
    "          var uid = 'arc_' + wk + '_' + runIdx;\n"
    "          scriptBlock = '<script type=\"application/json\" id=\"' + uid + '\">'\n"
    "                      + JSON.stringify(promptText).replace(/<\\/script>/gi,'<\\\\/script>')\n"
    "                      + '<\\/script>';\n"
    "          copyBtn = '<button class=\"btn mg copy-prompt-btn\" data-ref=\"' + uid + '\">\\u29c9 Copy AI Prompt</button>';\n"
    "        }\n"
    "        var reportUrl = run.report_url || '';\n"
    "        var fullBtn = reportUrl\n"
    "          ? '<a href=\"' + reportUrl + '\" class=\"btn\" target=\"_blank\" onclick=\"event.stopPropagation()\">\\u2197 Full Report</a>'\n"
    "          : '';\n"
    "        var rtypeBadge = runType === 'MANUAL'\n"
    "          ? '<span style=\"font-size:8px;color:var(--sun);margin-left:8px\">MANUAL</span>'\n"
    "          : '';\n"
    "        cardsHtml += scriptBlock\n"
    "          + '<div class=\"rcard\" onclick=\"rcT(this)\">'\n"
    "          + '<div class=\"rcard-head\"><div>'\n"
    "          + '<div class=\"rcard-date\">' + ts + ' \\u00b7 ' + slot + ' \\u00b7 ' + count + ' stock' + (count !== 1 ? 's' : '') + rtypeBadge + '</div>'\n"
    "          + '<div class=\"rcard-slot\">' + regimeBadge + '</div>'\n"
    "          + '</div><span class=\"rcard-badge ' + bCls + '\">' + bTitle + '</span></div>'\n"
    "          + '<div class=\"rcard-body\"><div class=\"rcard-inner\">'\n"
    "          + '<div class=\"rcard-cols\">'\n"
    "          + '<div><div class=\"rcc-k\">Sys 1</div><div class=\"rcc-v\">' + tickers\n"
    "          + '<br><span class=\"top-conf-val\" style=\"font-size:10px;\">Confidence: ' + topConfStr + '/100</span></div></div>'\n"
    "          + '<div><div class=\"rcc-k\">Verdicts</div><div class=\"rcc-v\">'\n"
    "          + '<span style=\"color:var(--up)\">RN:' + rnC + '</span> '\n"
    "          + '<span style=\"color:var(--nt)\">W:' + wC  + '</span> '\n"
    "          + '<span style=\"color:var(--dn)\">S:'  + sC  + '</span>'\n"
    "          + '</div></div>'\n"
    "          + '<div><div class=\"rcc-k\">Breadth</div><div class=\"rcc-v\" style=\"color:var(--' + bCls + ')\">' + bTitle + '</div></div>'\n"
    "          + '</div>'\n"
    "          + '<div class=\"rcard-btns\">' + fullBtn + copyBtn + '</div>'\n"
    "          + '</div></div></div>';\n"
    "      });\n"
    "      html += '<div class=\"week-block\">'\n"
    "            + '<div class=\"week-head\">' + label + ' <span class=\"week-count\">' + runs.length + ' report' + (runs.length !== 1 ? 's' : '') + '</span></div>'\n"
    "            + cardsHtml\n"
    "            + '</div>';\n"
    "    });\n"
    "    if (!html) html = '<div style=\"color:var(--mist);font-family:var(--ff-mono);font-size:11px;padding:28px;\">No archive data yet.</div>';\n"
    "    document.getElementById('archive-mount').innerHTML = html;\n"
    "    if (window.dismissLoader) window.dismissLoader();\n"
    "  })\n"
    "  .catch(function() {\n"
    "    document.getElementById('archive-mount').innerHTML =\n"
    "      '<div style=\"color:var(--dn);font-family:var(--ff-mono);font-size:11px;padding:28px;\">Error loading archive. Try refreshing.</div>';\n"
    "    if (window.dismissLoader) window.dismissLoader();\n"
    "  });\n"
)


# ── Safe helpers ────────────────────────────────────────────────────────────

def _esc(val) -> str:
    """Escape a data-derived string for HTML insertion. Returns '—' for None/empty."""
    if not val:
        return '\u2014'
    return html.escape(str(val))


def _safe_json(data) -> str:
    """Serialize data for <script type="application/json"> blocks (Pattern A)."""
    return (
        json.dumps(data)
        .replace('</script>', '<\\/script>')
        .replace('\u2028', '\\u2028')
        .replace('\u2029', '\\u2029')
    )


def _safe_js_json(data) -> str:
    """Serialize data for inline JS variable assignment (Pattern B)."""
    return json.dumps(data, ensure_ascii=True).replace('</script>', '<\\/script>')


# ── Numeric formatters ──────────────────────────────────────────────────────

def _fmt_pct(val) -> str:
    if not isinstance(val, (int, float)):
        return '\u2014'
    arrow = '\u25b2' if val > 0 else '\u25bc' if val < 0 else '\u2014'
    return f'{arrow}{abs(val):.1f}%'


def _fmt_score(val, decimals=1) -> str:
    if not isinstance(val, (int, float)):
        return '\u2014'
    return f'{val:.{decimals}f}'


def _fmt_price(val) -> str:
    if not isinstance(val, (int, float)):
        return '\u2014'
    return f'${val:,.2f}'


def _fmt_index_val(val) -> str:
    if not isinstance(val, (int, float)) or math.isnan(val):
        return '\u2014'
    return f'{val:,.0f}'


def _calc_return_from_history(data: list, trading_days: int) -> str:
    if not data or len(data) <= trading_days:
        return '\u2014'
    try:
        start = data[-trading_days - 1]
        end   = data[-1]
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            return '\u2014'
        if start == 0:
            return '\u2014'
        pct   = ((end - start) / start) * 100
        arrow = '\u25b2' if pct > 0 else '\u25bc' if pct < 0 else '\u2014'
        return f'{arrow}{abs(pct):.1f}%'
    except Exception:
        return '\u2014'


def _sanitize_price_history(raw: list) -> list:
    """
    Remove any non-numeric or NaN values from a price history list before storage.

    SYSTEM CONTRACT: rank.json MUST NEVER contain unsanitized price_history.
    All writes to price_history in rank.json must pass through _update_rank_board(),
    which calls this function. Never bypass _update_rank_board() to write price_history
    directly to rank.json — doing so breaks the Chart.js render pipeline.
    """
    import math
    if not raw or not isinstance(raw, list):
        return []
    return [p for p in raw if isinstance(p, (int, float)) and not math.isnan(p)]


def _build_idx_data(index_history: dict, indices: dict) -> dict:
    """Build IDX_DATA dict for index page Chart.js injection (Pattern B)."""
    def _dir_color(chg):
        if isinstance(chg, (int, float)) and chg > 0:
            return '#39e8a0', 'rgba(57,232,160,0.12)'
        if isinstance(chg, (int, float)) and chg < 0:
            return '#ff4d6d', 'rgba(255,77,109,0.12)'
        return '#ff9a3c', 'rgba(255,154,60,0.12)'

    idx_map = {
        'dow': ('Dow Jones', 'dow',    'dow'),
        'sp':  ('S&P 500',   'sp500',  'sp500'),
        'nq':  ('Nasdaq',    'nasdaq', 'nasdaq'),
    }
    result = {}
    for key, (name, idx_key, hist_key) in idx_map.items():
        chg     = (indices.get(idx_key) or {}).get('change_pct')
        col, bg = _dir_color(chg)
        data    = _sanitize_price_history(
            index_history.get(hist_key) or []
        )
        result[key] = {
            'name':     name,
            'color':    col,
            'bg_color': bg,
            'data':     data,
            'stat1m':   _calc_return_from_history(data, 21),
            'stat3m':   _calc_return_from_history(data, 63),
            'stat6m':   _calc_return_from_history(data, 126),
        }
    return result


# ── CSS-class helpers ────────────────────────────────────────────────────────

def _conf_cls(score) -> str:
    if not isinstance(score, (int, float)):
        return 'nt'
    if score >= 75: return 'up'
    if score >= 50: return 'nt'
    return 'dn'


def _breadth_cls(label: str) -> str:
    l = (label or '').lower()
    if 'strong' in l: return 'up'
    if 'weak'   in l: return 'dn'
    return 'nt'


def _eq_cls(verdict: str) -> str:
    s = (verdict or '').upper()
    if 'SUPPORT' in s: return 'up'
    if 'WEAK' in s or 'RISK' in s: return 'dn'
    if 'NEUTRAL' in s: return 'nt'
    return 'pu'


def _rot_cls(signal: str) -> str:
    s = (signal or '').upper()
    if s == 'SUPPORT': return 'up'
    if s == 'WEAKEN':  return 'dn'
    if s == 'WAIT':    return 'nt'
    return 'pu'


def _align_cls(val: str) -> str:
    v = (val or '').strip().upper()
    if v == 'ALIGNED':  return 'sig-up'
    if v == 'CONFLICT': return 'sig-dn'
    return 'sig-nt'


# ── Module-level JS string constants ────────────────────────────────────────
# These are NOT f-strings — { } have their literal meaning inside them.

_DAYS_JS = """
const DAYS = Array.from({length:30},(_,i)=>{
  const d=new Date(); d.setDate(d.getDate()-(29-i));
  return d.toLocaleDateString('en-US',{month:'short',day:'numeric'});
});
"""

_EASING_JS = """
function easeOutExpo(t)  { return t===1?1:1-Math.pow(2,-10*t); }
function easeOutCubic(t) { return 1-Math.pow(1-t,3); }
"""

_GENIE_JS = """
function genieClipOpen(t){
  const e=easeOutExpo(t),x1=46*(1-e),x2=54+46*e,tx1=3*(1-e),tx2=97+3*e;
  return `polygon(${tx1.toFixed(1)}% 0%, ${tx2.toFixed(1)}% 0%, ${x2.toFixed(1)}% 100%, ${x1.toFixed(1)}% 100%)`;
}
function genieClipClose(t){
  const tB=Math.min(t*1.6,1),tT=Math.max((t-0.4)/0.6,0);
  const bx1=easeOutCubic(tB)*46,bx2=100-easeOutCubic(tB)*46;
  const tx1=easeOutCubic(tT)*46,tx2=100-easeOutCubic(tT)*46;
  return `polygon(${tx1.toFixed(1)}% 0%, ${tx2.toFixed(1)}% 0%, ${bx2.toFixed(1)}% 100%, ${bx1.toFixed(1)}% 100%)`;
}
let expandRAF=null, expandHeight=0;
function getFullHeight(){
  const ex=document.getElementById('idx-expand'),pan=document.getElementById('idx-panel-active');
  if(!pan) return 200;
  const pH=ex.style.height,pC=ex.style.clipPath;
  ex.style.height='auto'; ex.style.clipPath='';
  const h=pan.offsetHeight+8;
  ex.style.height=pH; ex.style.clipPath=pC;
  return h;
}
function animateGenie(fromH,toH,dur,onDone){
  if(expandRAF){cancelAnimationFrame(expandRAF);expandRAF=null;}
  const ex=document.getElementById('idx-expand'),start=performance.now(),opening=toH>fromH;
  function frame(now){
    const raw=Math.min((now-start)/dur,1);
    const tH=opening?easeOutExpo(raw):easeOutCubic(raw);
    const h=fromH+(toH-fromH)*tH; expandHeight=h;
    const clip=opening?genieClipOpen(raw):genieClipClose(raw);
    const sc=opening?0.93+0.07*easeOutExpo(raw):1.0-0.07*easeOutCubic(raw);
    const mt=h>0?8*Math.min(raw*4,1):0;
    ex.style.height=h+'px'; ex.style.marginTop=mt+'px';
    ex.style.opacity=opening?Math.min(raw*3,1):Math.max(1-raw,0);
    ex.style.clipPath=clip; ex.style.transform=`scaleX(${sc.toFixed(4)})`;
    if(raw<1){expandRAF=requestAnimationFrame(frame);}
    else{
      expandRAF=null;
      if(toH>0){ex.style.height=toH+'px';ex.style.marginTop='8px';ex.style.opacity='1';
        ex.style.clipPath='polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%)';ex.style.transform='scaleX(1)';}
      else{ex.style.height='0';ex.style.marginTop='0';ex.style.opacity='0';
        ex.style.clipPath='polygon(46% 0%, 54% 0%, 54% 0%, 46% 0%)';ex.style.transform='scaleX(0.93)';}
      isAnimating=false; if(onDone)onDone();
    }
  }
  expandRAF=requestAnimationFrame(frame);
}
"""

_SLIDE_JS = """
function animateSlide(prevKey,nextKey,onDone){
  const fromO=IDX_ORDER.indexOf(prevKey),toO=IDX_ORDER.indexOf(nextKey);
  const dir=toO>fromO?'left':'right';
  const ex=document.getElementById('idx-expand'),vp=document.getElementById('idx-slide-viewport');
  const tr=document.getElementById('idx-slide-track'),ac=document.getElementById('idx-panel-active');
  if(window._mreCharts&&window._mreCharts['idx-chart']){window._mreCharts['idx-chart'].destroy();delete window._mreCharts['idx-chart'];}
  ex.classList.add('sliding');
  const pW=ac.offsetWidth,pH=ac.offsetHeight;
  vp.style.height=pH+'px'; vp.style.overflow='hidden';
  const cl=ac.cloneNode(true); cl.removeAttribute('id');
  cl.style.cssText=`position:absolute;top:0;left:0;width:${pW}px;z-index:1;transform:translateX(0);opacity:1;pointer-events:none;`;
  tr.appendChild(cl);
  const d=IDX_DATA[nextKey];
  ac.querySelector('.idx-expand-name').textContent=d.name;
  ac.querySelector('#idx-stat-1m').textContent=d.stat1m;
  ac.querySelector('#idx-stat-3m').textContent=d.stat3m;
  ac.querySelector('#idx-stat-6m').textContent=d.stat6m;
  const eX=dir==='left'?pW:-pW;
  ac.style.cssText=`position:absolute;top:0;left:0;width:${pW}px;z-index:2;transform:translateX(${eX}px);opacity:0.7;`;
  tr.style.position='relative'; tr.style.height=pH+'px';
  const DUR=520,start=performance.now(),exitX=dir==='left'?-pW:pW;
  let slideRAF=null;
  function frame(now){
    const raw=Math.min((now-start)/DUR,1),ease=easeOutCubic(raw);
    const fo=Math.max(1-raw/0.6,0),fi=raw<0.3?0:easeOutCubic((raw-0.3)/0.7);
    cl.style.transform=`translateX(${exitX*ease}px)`; cl.style.opacity=fo.toFixed(3);
    ac.style.transform=`translateX(${eX*(1-ease)}px)`; ac.style.opacity=fi.toFixed(3);
    if(raw<1){slideRAF=requestAnimationFrame(frame);}
    else{
      cl.remove(); ac.style.cssText='';
      tr.style.height=''; tr.style.position='';
      vp.style.height=''; vp.style.overflow='';
      ex.classList.remove('sliding');
      ac.querySelector('.idx-panel-header').style.opacity='0';
      ac.querySelector('.idx-panel-header').style.transform='translateY(-6px)';
      ac.querySelector('.idx-chart-wrap').style.opacity='0';
      ac.querySelector('.idx-chart-wrap').style.transform='translateY(-6px)';
      requestAnimationFrame(()=>{
        ac.querySelector('.idx-panel-header').style.opacity='';
        ac.querySelector('.idx-panel-header').style.transform='';
        ac.querySelector('.idx-chart-wrap').style.opacity='';
        ac.querySelector('.idx-chart-wrap').style.transform='';
        ex.classList.add('slide-reveal');
      });
      isAnimating=false;
      if(onDone) pendingChartTimer=setTimeout(()=>{pendingChartTimer=null;onDone();},320);
    }
  }
  slideRAF=requestAnimationFrame(frame);
}
"""

_TOGGLE_IDX_JS = """
let currentIdx=null, isAnimating=false, pendingChartTimer=null;
const IDX_ORDER=['dow','sp','nq'];
function toggleIdx(key){
  if(isAnimating)return;
  if(pendingChartTimer){clearTimeout(pendingChartTimer);pendingChartTimer=null;}
  if(window._mreCharts&&window._mreCharts['idx-chart']){
    window._mreCharts['idx-chart'].destroy();delete window._mreCharts['idx-chart'];
  }
  const ex=document.getElementById('idx-expand'),pill=document.getElementById('pill-'+key);
  if(currentIdx===key){
    pill.classList.remove('active');
    ex.classList.remove('content-visible','slide-reveal');
    currentIdx=null; isAnimating=true;
    animateGenie(expandHeight,0,340,null); return;
  }
  const prevIdx=currentIdx,panelOpen=expandHeight>20;
  document.querySelectorAll('.idx-pill').forEach(p=>p.classList.remove('active'));
  pill.classList.add('active'); currentIdx=key; isAnimating=true;
  if(panelOpen){
    animateSlide(prevIdx,key,()=>buildIdxChart(IDX_DATA[key]));
  } else {
    const d=IDX_DATA[key];
    document.getElementById('idx-expand-name').textContent=d.name;
    document.getElementById('idx-stat-1m').textContent=d.stat1m;
    document.getElementById('idx-stat-3m').textContent=d.stat3m;
    document.getElementById('idx-stat-6m').textContent=d.stat6m;
    const full=getFullHeight();
    animateGenie(0,full,580,()=>{ex.classList.add('content-visible');buildIdxChart(d);});
  }
}
"""

_BUILD_IDX_CHART_JS = """
function buildIdxChart(d){
  if(typeof Chart==='undefined')return;
  window._mreCharts=window._mreCharts||{};
  const cid='idx-chart',cv=document.getElementById(cid);
  if(!cv)return;
  if(window._mreCharts[cid]){window._mreCharts[cid].destroy();delete window._mreCharts[cid];}
  const col=d.color;
  window._mreCharts[cid]=new Chart(cv.getContext('2d'),{
    type:'line',
    data:{labels:DAYS,datasets:[{data:d.data,borderColor:col,borderWidth:1.8,fill:true,tension:0.38,
      backgroundColor:ctx=>{const{ctx:c,chartArea:a}=ctx.chart;if(!a)return 'transparent';
        const g=c.createLinearGradient(0,a.top,0,a.bottom);g.addColorStop(0,col+'30');g.addColorStop(1,'transparent');return g;},
      pointRadius:0,pointHoverRadius:3,pointHoverBackgroundColor:col,
      pointHoverBorderColor:'#0a0610',pointHoverBorderWidth:2,hitRadius:20}]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false},tooltip:{mode:'index',intersect:false,
        backgroundColor:'#1a1430',borderColor:'rgba(155,89,255,0.25)',borderWidth:1,
        titleColor:'#9b59ff',bodyColor:'#f0eaff',
        titleFont:{family:'Share Tech Mono',size:10},bodyFont:{family:'Share Tech Mono',size:11},
        callbacks:{title:i=>DAYS[i[0].dataIndex],label:i=>' $'+i.raw.toFixed(2)}}},
      scales:{x:{display:false},y:{display:false}},
      interaction:{mode:'index',intersect:false},animation:{duration:600,easing:'easeInOutCubic'}}
  });
}
"""

_RAF_COLLAPSE_JS = """
function rafExpandRow(el,innerSel,duration,onDone){
  el.style.display='block'; el.style.overflow='hidden'; el.style.height='0px';
  const inner=el.querySelector(innerSel);
  if(inner){
    inner.style.opacity='0';
    inner.style.transform='translateY(-10px)';
    inner.style.transition='none';
    inner.querySelectorAll('.est').forEach(function(t){
      t.style.opacity='0'; t.style.transform='translateY(8px) scale(0.96)';
    });
  }
  const toH=el.scrollHeight;
  const start=performance.now();
  function frame(now){
    const raw=Math.min((now-start)/duration,1);
    const eH=easeOutExpo(raw), eO=easeOutCubic(Math.min(raw*2.5,1));
    el.style.height=(toH*eH).toFixed(1)+'px';
    if(inner){
      inner.style.opacity=eO.toFixed(3);
      inner.style.transform=`translateY(${(-10*(1-eH)).toFixed(2)}px)`;
    }
    if(raw<1){requestAnimationFrame(frame);}
    else{
      el.classList.add('open');
      el.style.height=''; el.style.overflow='';
      if(inner){
        inner.style.opacity=''; inner.style.transform=''; inner.style.transition='';
        inner.querySelectorAll('.est').forEach(function(t,i){
          t.style.opacity='0'; t.style.transform='translateY(8px) scale(0.96)';
          t.style.transition='none';
          setTimeout(function(){
            t.style.transition='opacity 0.22s ease, transform 0.22s ease';
            t.style.opacity='1'; t.style.transform='translateY(0) scale(1)';
            setTimeout(function(){t.style.transition='';},240);
          }, 30+i*45);
        });
      }
      if(onDone)onDone();
    }
  }
  requestAnimationFrame(frame);
}
function rafCollapseRow(el,innerSel,duration,onDone){
  const fromH=el.offsetHeight;
  if(fromH===0){el.style.display='none';if(onDone)onDone();return;}
  const inner=el.querySelector(innerSel);
  el.style.height=fromH+'px'; el.style.overflow='hidden';
  const start=performance.now();
  function frame(now){
    const raw=Math.min((now-start)/duration,1);
    const eH=easeOutCubic(raw), eO=Math.max(1-raw*2.2,0);
    el.style.height=(fromH*(1-eH)).toFixed(1)+'px';
    if(inner){
      inner.style.opacity=eO.toFixed(3);
      inner.style.transform=`translateY(${(-8*eH).toFixed(2)}px)`;
    }
    if(raw<1){requestAnimationFrame(frame);}
    else{
      el.classList.remove('open'); el.style.display='none';
      el.style.height=''; el.style.overflow='';
      if(inner){inner.style.opacity=''; inner.style.transform='';
        inner.querySelectorAll('.est').forEach(function(t){t.style.opacity='';t.style.transform='';t.style.transition='';});
      }
      if(onDone)onDone();
    }
  }
  requestAnimationFrame(frame);
}
function closeRpExp(el){if(!el.classList.contains('open'))return;rafCollapseRow(el,'.rp-exp-inner',380,null);}
function closeRpExpInstant(el){
  if(!el.classList.contains('open'))return;
  el.classList.remove('open'); el.style.display='none'; el.style.height='';
  const inner=el.querySelector('.rp-exp-inner');
  if(inner){inner.style.opacity='';inner.style.transform='';inner.style.transformOrigin='';}
}
function rpT(id){
  const el=document.getElementById(id),was=el.classList.contains('open');
  const anyOpen=!!document.querySelector('.rp-exp.open');
  document.querySelectorAll('.rp-exp').forEach(e=>{if(e!==el)closeRpExpInstant(e);});
  if(!was){
    function fireItems(){
      el.querySelectorAll('.pex-item').forEach(function(item,i){
        item.style.opacity='';
        item.style.animation='none'; item.offsetHeight;
        item.style.animation='pex-spark 0.22s ease both '+(0.04+i*0.06)+'s';
      });
    }
    if(anyOpen){
      el.style.display='block'; el.style.height='';
      const inner=el.querySelector('.rp-exp-inner');
      if(inner){inner.style.opacity='1';inner.style.transform='';}
      el.classList.add('open');
      requestAnimationFrame(fireItems);
    } else {
      el.style.display='block'; el.style.overflow='hidden'; el.style.height='0px';
      const inner=el.querySelector('.rp-exp-inner');
      if(inner){inner.style.opacity='1';inner.style.transform='';}
      el.querySelectorAll('.pex-item').forEach(function(item){
        item.style.opacity='0'; item.style.animation='none';
      });
      const toH=el.scrollHeight;
      const start=performance.now(),dur=380;
      function frame(now){
        const raw=Math.min((now-start)/dur,1);
        const ease=1-Math.pow(1-raw,3);
        el.style.height=(toH*ease).toFixed(1)+'px';
        if(raw<1){requestAnimationFrame(frame);}
        else{
          el.classList.add('open');
          el.style.height=''; el.style.overflow='';
          requestAnimationFrame(fireItems);
        }
      }
      requestAnimationFrame(frame);
    }
  } else { closeRpExp(el); }
}
function closeExpRow(row){
  if(!row.classList.contains('open'))return;
  const card=row.closest('.rank-card'),cid=card?card.dataset.cid:null;
  if(cid&&window._mreCharts&&window._mreCharts[cid]){
    window._mreCharts[cid].destroy();delete window._mreCharts[cid];
    const _oc=document.getElementById(cid);
    if(_oc){const _octx=_oc.getContext('2d');_octx.clearRect(0,0,_oc.width,_oc.height);}
  }
  rafCollapseRow(row,'.exp-inner',380,null);
}
function closeExpRowInstant(row){
  if(!row.classList.contains('open'))return;
  const card=row.closest('.rank-card'),cid=card?card.dataset.cid:null;
  if(cid&&window._mreCharts&&window._mreCharts[cid]){
    window._mreCharts[cid].destroy();delete window._mreCharts[cid];
    const _oc=document.getElementById(cid);
    if(_oc){const _octx=_oc.getContext('2d');_octx.clearRect(0,0,_oc.width,_oc.height);}
  }
  row.classList.remove('open'); row.style.display='none'; row.style.height='';
  const inner=row.querySelector('.exp-inner');
  if(inner){inner.style.opacity='';inner.style.transform='';inner.style.transformOrigin='';}
}
"""

_EXP_T_JS = r"""
window._mreCharts=window._mreCharts||{};
function mkC(cid,data){
  if(typeof Chart==='undefined')return;
  const cv=document.getElementById(cid);if(!cv)return;
  if(window._mreCharts[cid]){window._mreCharts[cid].destroy();delete window._mreCharts[cid];const _oc=document.getElementById(cid);if(_oc){const _octx=_oc.getContext('2d');_octx.clearRect(0,0,_oc.width,_oc.height);}}
  const up=data[data.length-1]>=data[0],col=up?'#39e8a0':'#ff4d6d';
  const labels=DAYS.slice(-data.length);
  window._mreCharts[cid]=new Chart(cv.getContext('2d'),{
    type:'line',
    data:{labels:labels,datasets:[{data:data,borderColor:col,borderWidth:1.8,fill:true,tension:0.38,
      backgroundColor:ctx=>{const{ctx:c,chartArea:a}=ctx.chart;if(!a)return 'transparent';
        const g=c.createLinearGradient(0,a.top,0,a.bottom);
        g.addColorStop(0,up?'rgba(57,232,160,.18)':'rgba(255,77,109,.18)');
        g.addColorStop(1,'transparent');return g;},
      pointRadius:0,pointHoverRadius:3,pointHoverBackgroundColor:col,
      pointHoverBorderColor:'#0a0610',pointHoverBorderWidth:2,hitRadius:20}]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false},tooltip:{mode:'index',intersect:false,
        backgroundColor:'#1a1430',borderColor:'rgba(155,89,255,0.25)',borderWidth:1,
        titleColor:'#9b59ff',bodyColor:'#f0eaff',
        titleFont:{family:'Share Tech Mono',size:10},bodyFont:{family:'Share Tech Mono',size:11},
        callbacks:{title:i=>labels[i[0].dataIndex],label:i=>' $'+i.raw.toFixed(2)}}},
      scales:{x:{display:false},y:{display:false}},
      interaction:{mode:'index',intersect:false},
      animation:{duration:700,easing:'easeInOutCubic'}}
  });
}
function countUp(el,target,prefix,suffix,duration){
  const start=performance.now();
  function step(now){
    const p=Math.min((now-start)/duration,1),ease=1-Math.pow(1-p,3);
    el.textContent=prefix+(target*ease).toFixed(target%1===0?0:1)+suffix;
    if(p<1)requestAnimationFrame(step);
    else el.textContent=prefix+(Number.isInteger(target)?target:target.toFixed(1))+suffix;
  }
  requestAnimationFrame(step);
}
function expT(btn){
  var el=document.getElementById(btn.dataset.ref);
  if(!el)return;
  var data;
  try{data=JSON.parse(el.textContent);}catch(e){data=[];}
  var cid=btn.dataset.cid,eid=btn.dataset.eid;
  var row=document.getElementById(eid);if(!row)return;
  var card=btn.closest('.rank-card');
  var was=row.classList.contains('open');
  document.querySelectorAll('.rank-card').forEach(function(c){
    c.classList.remove('selected','dimmed','closing');
  });
  var anyOpen=!!document.querySelector('.exp-row.open');
  document.querySelectorAll('.exp-row').forEach(r=>{if(r!==row)closeExpRowInstant(r);});
  if(!was){
    document.querySelectorAll('.rank-card').forEach(function(c){
      if(c!==card){c.classList.add('dimmed');}
    });
    if(card){card.classList.add('selected');}
    function runContent(){
      if(data&&data.length>=2){mkC(cid,data);}
      row.querySelectorAll('.est-v').forEach(function(ev,i){
        var stored=ev.dataset.raw||'';
        if(!stored)return;
        var parts=stored.split('|');
        if(parts.length!==3)return;
        var prefix=parts[0],num=parseFloat(parts[1]),suffix=parts[2];
        if(!isNaN(num)&&num>0){
          setTimeout(function(){countUp(ev,num,prefix,suffix,420);},i*50);
        }
      });
    }
    if(anyOpen){
      row.style.display='block'; row.style.height=''; row.style.overflow='';
      var inner=row.querySelector('.exp-inner');
      if(inner){
        inner.style.opacity='1'; inner.style.transform='';
        inner.querySelectorAll('.est').forEach(function(t,i){
          t.style.opacity='0'; t.style.transform='translateY(8px) scale(0.96)';
          t.style.transition='none';
          setTimeout(function(){
            t.style.transition='opacity 0.22s ease, transform 0.22s ease';
            t.style.opacity='1'; t.style.transform='translateY(0) scale(1)';
            setTimeout(function(){t.style.transition='';},240);
          },30+i*45);
        });
      }
      row.classList.add('open');
      requestAnimationFrame(runContent);
    } else {
      rafExpandRow(row,'.exp-inner',400,runContent);
    }
  } else {
    if(card){card.classList.remove('selected');}
    document.querySelectorAll('.rank-card').forEach(function(c){c.classList.remove('dimmed');});
    closeExpRow(row);
  }
}
"""

_RCT_JS = "function rcT(el){el.classList.toggle('open');}"

_COPY_PROMPT_JS = """
document.addEventListener('click', function(e) {
  var btn = e.target.closest('.copy-prompt-btn');
  if (!btn) return;
  e.stopPropagation();
  var el = document.getElementById(btn.dataset.ref);
  if (!el) return;
  var text;
  try { text = JSON.parse(el.textContent); } catch(err) {
    btn.textContent = 'Error';
    btn.style.color = 'var(--dn)';
    setTimeout(function() {
      btn.textContent = '\u2389 Copy AI Prompt';
      btn.style.color = '';
    }, 1800);
    return;
  }
  function onCopied() {
    var orig = btn.textContent;
    btn.textContent = 'Copied \u2713';
    btn.style.color = 'var(--up)';
    btn.style.borderColor = 'rgba(57,232,160,.5)';
    setTimeout(function() {
      btn.textContent = orig;
      btn.style.color = '';
      btn.style.borderColor = '';
    }, 1800);
  }
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text).then(onCopied).catch(function() {
      var ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      onCopied();
    });
  } else {
    var ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    onCopied();
  }
});
"""


# ── Nav ──────────────────────────────────────────────────────────────────────

def _nav_html(active: str) -> str:
    """Returns sticky nav HTML. active: 'home' | 'rank' | 'news' | 'archive' | 'guide' | 'tests'"""
    pages = [
        ('index.html',   'home',    'Home'),
        ('rank.html',    'rank',    'Rank'),
        ('trades.html',  'trades',  'Paper Trading'),
        ('news.html',    'news',    'News'),
        ('archive.html', 'archive', 'Archive'),
        ('tests.html',   'tests',   'Tests'),
        ('guide.html',   'guide',   'Guide'),
    ]
    tabs = ''
    for href, key, label in pages:
        on = ' on' if key == active.lower() else ''
        tabs += f'<a href="{href}" class="tab{on}">{label}</a>'
    return (
        '<nav>'
        '<div class="brand">'
        '<div class="brand-pulse"></div>'
        '<span>MRE // System</span>'
        '</div>'
        f'<div class="nav-tabs">{tabs}</div>'
        '</nav>'
    )


# ── Error fallback page ──────────────────────────────────────────────────────

def _err_page(nav_key: str, msg: str) -> str:
    return (
        '<!DOCTYPE html><html lang="en"><head>'
        '<meta charset="UTF-8">'
        f'{_FONTS_LINK}'
        '<link rel="stylesheet" href="assets/style.css">'
        f'{_LOADER_CSS}'
        '</head><body>'
        f'{_LOADER_HTML}'
        f'{_LOADER_JS}'
        '<div class="scanlines"></div>'
        f'{_nav_html(nav_key)}'
        '<div class="pages"><div class="page on">'
        f'<div style="color:var(--dn);font-family:var(--ff-mono);padding:44px 28px;">{msg}</div>'
        '</div></div>'
        '<footer><span>MRE</span> &middot; Not investment advice</footer>'
        '<script>document.addEventListener("DOMContentLoaded",function(){if(window.dismissLoader)window.dismissLoader();});</script>'
        '</body></html>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# DATA WRITERS
def _write_news_json(confirmed_sectors: dict) -> None:
    """
    Writes docs/assets/data/news.json from confirmed sector articles.

    Preserve-on-empty: if confirmed_sectors is empty this run, the file is left
    unchanged so the index page npc widget retains last-run headlines.
    Intentional divergence from _write_news_page() which always reflects current
    run state. This may cause index and news page to temporarily display different
    data states after empty runs. This is by design.
    """
    if not isinstance(confirmed_sectors, dict):
        return
    if not confirmed_sectors:
        return
    news_path = os.path.join(DATA_DIR, 'news.json')
    now_et    = datetime.now(pytz.utc).astimezone(pytz.timezone('America/New_York'))
    payload   = {'generated': now_et.strftime('%Y-%m-%d %H:%M ET'), 'sectors': []}
    sectors_sorted = sorted(
        [(s, d) for s, d in confirmed_sectors.items() if d.get('articles')],
        key=lambda x: x[1].get('score', 0) if isinstance(x[1].get('score'), (int, float)) else 0,
        reverse=True,
    )
    for sector, data in sectors_sorted:
        payload['sectors'].append({
            'sector':   sector,
            'score':    data.get('score', 0),
            'articles': data.get('articles', []),
        })
    try:
        tmp = news_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp, news_path)
        log.info(f'News JSON written: {len(payload["sectors"])} sectors')
    except Exception as e:
        log.error(f'News JSON write failed: {e}')


def _update_reports_index(companies, slot, indices, breadth, regime, full_url='', prompt_text='', market_regime_dict=None, portfolio_summary=None):
    index_path = os.path.join(DATA_DIR, 'reports.json')
    try:
        with open(index_path, encoding='utf-8') as f:
            index = json.load(f)
    except Exception:
        index = {'reports': []}

    now_et = datetime.now(pytz.utc).astimezone(pytz.timezone('America/New_York'))
    vc = {
        'RESEARCH NOW': sum(1 for c in companies if c.get('market_verdict_display', c.get('summary_verdict', '')) == 'RESEARCH NOW'),
        'WATCH':        sum(1 for c in companies if c.get('market_verdict_display', c.get('summary_verdict', '')) == 'WATCH'),
        'SKIP':         sum(1 for c in companies if c.get('market_verdict_display', c.get('summary_verdict', '')) == 'SKIP'),
    }
    entry = {
        'date':       now_et.strftime('%Y-%m-%d'),
        'time':       now_et.strftime('%H:%M'),
        'slot':       slot,
        'breadth':    breadth.get('label', 'unknown') if breadth else 'unknown',
        'regime':     regime.get('label', 'unknown')  if regime  else 'unknown',
        'market_regime': (market_regime_dict or {}).get('market_regime', 'NEUTRAL'),
        'breadth_pct':   (market_regime_dict or {}).get('breadth_pct'),
        'count':      len(companies),
        'tickers':    [c.get('ticker', '') for c in companies[:5]],
        'top_score':  max((c.get('composite_confidence', 0) for c in companies), default=0),
        'verdicts':   vc,
        'report_url': full_url,
        'prompt':     prompt_text[:12000] if prompt_text else '',
        'pl_recommended_subset':    (portfolio_summary or {}).get('pl_recommended_subset', []),
        'pl_sector_exposure':       (portfolio_summary or {}).get('pl_sector_exposure', {}),
        'pl_diversification_score': (portfolio_summary or {}).get('pl_diversification_score'),
        'pl_avg_correlation':       (portfolio_summary or {}).get('pl_avg_correlation'),
    }
    if not isinstance(index.get('reports'), list):
        index['reports'] = []
    index['reports'].insert(0, entry)
    index['reports'] = index['reports'][:50]
    try:
        tmp = index_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(index, f, indent=2)
        os.replace(tmp, index_path)
    except Exception as e:
        log.error(f'reports.json write failed: {e}')


def _update_rank_board(companies):
    rank_path = os.path.join(DATA_DIR, 'rank.json')
    now_et    = datetime.now(pytz.utc).astimezone(pytz.timezone('America/New_York'))
    week_key  = now_et.strftime('%Y-W%W')
    try:
        with open(rank_path, encoding='utf-8') as f:
            rank_data = json.load(f)
    except Exception:
        rank_data = {}
    if rank_data.get('week') != week_key:
        rank_data = {'week': week_key, 'stocks': {}}
    for c in companies:
        # Test-run tickers are never written to the rank board.
        # They belong exclusively in tests.json / tests.html.
        if c.get('is_test'):
            continue
        ticker = c.get('ticker', '')
        if not ticker:
            continue
        existing = rank_data['stocks'].get(ticker, {})
        new_conf  = c.get('composite_confidence', 0)
        if new_conf >= existing.get('confidence', 0):
            raw_ph = c.get('price_history') or existing.get('price_history', [])
            rank_data['stocks'][ticker] = {
                'ticker':                       ticker,
                'name':                         c.get('company_name', ticker),
                'sector':                       c.get('sector', ''),
                'price':                        (c.get('current_price') or c.get('financials', {}).get('current_price')),
                'confidence':                   round(new_conf, 1),
                'risk_score':                   round(c.get('risk_score', 50), 1),
                'opportunity_score':            c.get('opportunity_score'),
                'signal_agreement':             c.get('agreement_score'),
                'return_1m':                    c.get('return_1m'),
                'return_3m':                    c.get('return_3m'),
                'return_6m':                    c.get('return_6m'),
                'eq_verdict_display':           c.get('eq_verdict_display', ''),
                'rotation_signal_display':      c.get('rotation_signal_display', ''),
                'ps_verdict_display':           c.get('ps_verdict_display', 'UNAVAILABLE'),
                'market_verdict_display':       c.get('market_verdict_display', c.get('summary_verdict', '')),
                'market_verdict':               c.get('summary_verdict', ''),
                'price_history':                _sanitize_price_history(raw_ph),
                'alignment':                    c.get('alignment', 'PARTIAL'),
                # ── Sub4 fields for rank page expanded row ───────────────────
                'ps_available':                 c.get('ps_available', False),
                'ps_key_level_position':        c.get('key_level_position', ''),
                'ps_key_level_display':         c.get('key_level_position', '').replace('_', ' ').title(),
                'ps_price_action_score':        c.get('price_action_score'),
                'ps_move_extension_pct':        c.get('move_extension_pct'),
                'ps_trend_structure':           c.get('trend_structure', ''),
                'ps_distance_to_support_pct':   c.get('distance_to_support_pct'),
                'ps_distance_to_resistance_pct': c.get('distance_to_resistance_pct'),
                # ── Phase 1 (1A/1B/1C) fields ──
                'event_risk':          c.get('event_risk',        'NORMAL'),
                'event_risk_reason':   c.get('event_risk_reason', ''),
                'days_to_earnings':    c.get('days_to_earnings'),
                'insider_signal':      c.get('insider_signal',    'UNAVAILABLE'),
                'insider_note':        c.get('insider_note',      ''),
                'expectations_signal': c.get('expectations_signal', 'UNAVAILABLE'),
                'earnings_beat_rate':  c.get('earnings_beat_rate'),
                'peg_ratio':           c.get('peg_ratio'),
                'ps_entry_price':      c.get('entry_price'),
                'ps_stop_loss':        c.get('stop_loss'),
                'ps_price_target':     c.get('price_target'),
                'ps_risk_reward_ratio': c.get('risk_reward_ratio'),
                'ps_rr_override':      bool(c.get('rr_override', False)),
                # ── Sub5 fields ─────────────────────────────────────────────────
                'pl_selected':          c.get('pl_selected', False),
                'pl_position_weight':   c.get('pl_position_weight'),
                'pl_cluster_id':        c.get('pl_cluster_id'),
                'pl_correlation_flags': c.get('pl_correlation_flags', []),
                'pl_exclusion_reason':  c.get('pl_exclusion_reason'),
            }
    try:
        tmp = rank_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(rank_data, f, indent=2)
        os.replace(tmp, rank_path)
    except Exception as e:
        log.error(f'rank.json write failed: {e}')


def _update_weekly_archive(companies, slot, breadth, regime, prompt_text='', is_debug=False, full_url='', market_regime_dict=None):
    # Test runs (is_debug=True) are stored in tests.json, not the archive.
    if is_debug:
        return
    archive_path = os.path.join(DATA_DIR, 'weekly_archive.json')
    try:
        with open(archive_path, encoding='utf-8') as f:
            archive = json.load(f)
    except Exception:
        archive = {'weeks': {}}
    now_et   = datetime.now(pytz.utc).astimezone(pytz.timezone('America/New_York'))
    week_key = now_et.strftime('%Y-W%W')
    run_id   = f"{slot}_{now_et.strftime('%Y-%m-%dT%H:%M')}"
    run_entry = {
        'id':        run_id,
        'run_type':  'MANUAL' if is_debug else 'SCHEDULED',
        'timestamp': now_et.strftime('%Y-%m-%dT%H:%M'),
        'slot':      slot,
        'breadth':   breadth.get('label', '') if breadth else '',
        'regime':    regime.get('label', '')  if regime  else '',
        'market_regime': (market_regime_dict or {}).get('market_regime', 'NEUTRAL'),
        'breadth_pct':   (market_regime_dict or {}).get('breadth_pct'),
        'count':     len(companies),
        'verdict_counts': {
            'RESEARCH NOW': sum(1 for c in companies if c.get('market_verdict_display', c.get('summary_verdict', '')) == 'RESEARCH NOW'),
            'WATCH':        sum(1 for c in companies if c.get('market_verdict_display', c.get('summary_verdict', '')) == 'WATCH'),
            'SKIP':         sum(1 for c in companies if c.get('market_verdict_display', c.get('summary_verdict', '')) == 'SKIP'),
        },
        'candidates': [
            {
                'ticker':          c.get('ticker', ''),
                'confidence':      round(c.get('composite_confidence', 0), 1),
                'eq_verdict':      c.get('eq_verdict_display', ''),
                'rotation_signal': c.get('rotation_signal_display', ''),
                'ps_entry_quality': c.get('ps_verdict_display', 'UNAVAILABLE'),
                'conclusion':      (c.get('eq_combined_reading', {}).get('conclusion', '') if c.get('eq_combined_reading') else '')[:200],
            }
            for c in companies
        ],
        'prompt':     prompt_text[:12000] if prompt_text else '',
        'report_url': full_url,
    }
    if week_key not in archive['weeks']:
        archive['weeks'][week_key] = {'runs': []}
    existing = archive['weeks'][week_key]['runs']
    if not any(r.get('id') == run_id for r in existing):
        existing.insert(0, run_entry)
    archive['weeks'][week_key]['runs'] = existing[:10]
    if len(archive['weeks']) > 12:
        for old in sorted(archive['weeks'].keys())[:len(archive['weeks']) - 12]:
            del archive['weeks'][old]
    try:
        tmp = archive_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(archive, f, indent=2)
        os.replace(tmp, archive_path)
    except Exception as e:
        log.error(f'weekly_archive.json write failed: {e}')


def _write_index_page(indices, breadth, regime, index_history=None, market_regime_dict=None):
    index_history = index_history or {}
    index_path    = os.path.join(DATA_DIR, 'reports.json')
    rank_path     = os.path.join(DATA_DIR, 'rank.json')
    news_path     = os.path.join(DATA_DIR, 'news.json')
    try:
        with open(index_path, encoding='utf-8') as f:
            reports_data = json.load(f)
    except Exception:
        reports_data = {}
    if not isinstance(reports_data, dict):
        reports = []
    else:
        reports_raw = reports_data.get('reports')
        reports = reports_raw if isinstance(reports_raw, list) else []

    try:
        with open(rank_path, encoding='utf-8') as f:
            rank_data = json.load(f)
    except Exception:
        rank_data = {}
    try:
        with open(news_path, encoding='utf-8') as f:
            news_data = json.load(f)
    except Exception:
        news_data = {}
    now_et = datetime.now(pytz.utc).astimezone(pytz.timezone('America/New_York'))
    html_content = _render_index_html(reports[:14], rank_data, indices, breadth, regime, now_et, index_history, news_data, market_regime_dict)
    out_path = os.path.join(DOCS_DIR, 'index.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html_content)


def _write_rank_page():
    rank_path = os.path.join(DATA_DIR, 'rank.json')
    try:
        with open(rank_path, encoding='utf-8') as f:
            rank_data = json.load(f)
    except Exception:
        rank_data = {}
    html_content = _render_rank_html(rank_data)
    with open(os.path.join(DOCS_DIR, 'rank.html'), 'w', encoding='utf-8') as f:
        f.write(html_content)


def _write_archive_page():
    archive_path = os.path.join(DATA_DIR, 'weekly_archive.json')
    try:
        with open(archive_path, encoding='utf-8') as f:
            archive_data = json.load(f)
    except Exception:
        archive_data = {'weeks': {}}
    html_content = _render_archive_html(archive_data)
    with open(os.path.join(DOCS_DIR, 'archive.html'), 'w', encoding='utf-8') as f:
        f.write(html_content)


def _write_news_page(confirmed_sectors: dict) -> None:
    """
    Writes docs/news.html from confirmed_sectors parameter directly.

    Run-current: always reflects this run's state. If nothing confirmed,
    renders a placeholder. Intentional divergence from _write_news_json()
    which preserves stale data on empty runs. This may cause index and news
    page to temporarily display different data states. This is by design.
    """
    if not isinstance(confirmed_sectors, dict):
        confirmed_sectors = {}
    news_html_path = os.path.join(DOCS_DIR, 'news.html')
    if not confirmed_sectors:
        sectors   = []
        generated = datetime.now(pytz.utc).astimezone(pytz.timezone('America/New_York')).strftime('%Y-%m-%d %H:%M ET')
    else:
        now_et    = datetime.now(pytz.utc).astimezone(pytz.timezone('America/New_York'))
        generated = now_et.strftime('%Y-%m-%d %H:%M ET')
        sectors   = sorted(
            [
                {'sector': s, 'score': d.get('score', 0), 'articles': d.get('articles', [])}
                for s, d in confirmed_sectors.items()
                if d.get('articles')
            ],
            key=lambda x: x['score'] if isinstance(x['score'], (int, float)) else 0,
            reverse=True,
        )
    html_content = _render_news_html(sectors, generated)
    try:
        tmp = news_html_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(html_content)
        os.replace(tmp, news_html_path)
    except Exception as e:
        log.error(f'news.html write failed: {e}')
def _render_index_html(reports, rank_data, indices, breadth, regime, now_et, index_history, news_data, market_regime_dict=None) -> str:
    try:
        indices = indices or {}
        # ── Index pills ──────────────────────────────────────────────────────
        _pill_colors = {
            'dow': ('#ffb347', 'rgba(40,25,0,.85)',  'rgba(60,40,0,.90)',   'rgba(255,179,71,.75)'),
            'sp':  ('#ff7c2a', 'rgba(40,18,0,.85)',  'rgba(60,30,0,.90)',   'rgba(255,124,42,.75)'),
            'nq':  ('#ff4466', 'rgba(40,5,12,.85)',  'rgba(60,10,20,.90)',  'rgba(255,68,102,.75)'),
        }

        def _pill(key, pill_id, label_text):
            d     = indices.get(key, {})
            val   = _fmt_index_val(d.get('value'))
            chg   = d.get('change_pct')
            lbl   = (d.get('label') or '').upper()
            col, bg_flat, bd_dark, bd_light = _pill_colors.get(pill_id, ('#9b59ff', 'rgba(20,5,40,.85)', 'rgba(40,10,80,.90)', 'rgba(155,89,255,.75)'))
            if isinstance(chg, (int, float)):
                arrow = '\u25b2' if chg > 0 else '\u25bc' if chg < 0 else '\u2014'
                cls   = 'up' if chg > 0 else 'dn' if chg < 0 else 'nt'
                chg_s = f'{arrow} {abs(chg):.2f}% {lbl}'
            else:
                cls   = 'nt'
                chg_s = '\u2014'
            label_badge = (
                f'<span style="'
                f'display:inline-block;'
                f'background:linear-gradient(90deg,{bd_dark} 0%,{bd_light} 100%);'
                f'border-radius:5px;padding:1px;">'
                f'<span style="'
                f'display:inline-block;'
                f'font-size:10px;color:{col};font-family:var(--ff-mono);letter-spacing:0.1em;'
                f'text-transform:uppercase;white-space:nowrap;'
                f'background:{bg_flat};'
                f'border-radius:4px;padding:2px 7px;">{label_text}</span></span>'
            )
            return (
                f'<div class="idx-pill" id="pill-{pill_id}" onclick="toggleIdx(\'{pill_id}\')">'
                f'<div class="pill-left">'
                f'<div class="pill-label">{label_badge}</div>'
                f'<div class="pill-val">{val}</div>'
                f'<div class="pill-change {cls}">{chg_s}</div>'
                f'</div><div class="pill-chevron">\u25bc</div></div>'
            )

        pills = (
            _pill('dow',    'dow', 'Dow Jones') +
            _pill('sp500',  'sp',  'S&amp;P 500') +
            _pill('nasdaq', 'nq',  'Nasdaq')
        )

        # ── IDX_DATA Pattern B ───────────────────────────────────────────────
        idx_data_dict = _build_idx_data(index_history, indices)
        idx_script    = f'<script>const IDX_DATA={_safe_js_json(idx_data_dict)};</script>'

        # ── Status strip ─────────────────────────────────────────────────────
        b_label   = (breadth.get('label', '') if breadth else '').upper() or 'UNKNOWN'
        r_label   = (regime.get('label', '')  if regime  else '') or 'unknown'
        b_cls     = _breadth_cls(b_label)

        _mr_dict_s  = market_regime_dict or {}
        _mr_lbl_s   = _mr_dict_s.get('market_regime', 'NEUTRAL')
        _mr_cls_s   = 'up' if _mr_lbl_s == 'BULL' else ('dn' if _mr_lbl_s == 'BEAR' else 'nt')
        _mr_esc_s   = _esc(_mr_lbl_s)
        _r_esc_s    = _esc(r_label)
        _b_esc_s    = _esc(b_label)

        strip = (
            '<div class="status-strip stagger-3">'
            '<span class="ss-label" style="font-size:11px;">Breadth</span>'
            f'<span class="ss-val {b_cls}">{_b_esc_s}</span>'
            '<span class="ss-divider">&middot;</span>'
            '<span class="ss-label" style="font-size:11px;">Market</span>'
            f'<span class="ss-val nt">{_r_esc_s}</span>'
            '<span class="ss-divider">&middot;</span>'
            '<span class="ss-label" style="font-size:11px;">Regime</span>'
            f'<span class="ss-val {_mr_cls_s}">{_mr_esc_s}</span>'
            '</div>'
        )

        # ── Rank preview ─────────────────────────────────────────────────────
        rank_preview = '<div id="rank-preview-mount"></div>'

        # ── Report cards ─────────────────────────────────────────────────────
        cards_html = '<div id="report-cards-mount" class="rcard-grid"></div>'

        # ── Signal Headlines ──────────────────────────────────────────────────
        try:
            sectors_list = news_data.get('sectors') if isinstance(news_data, dict) else None
            if not isinstance(sectors_list, list):
                sectors_list = []
            all_articles = []
            for sec in sectors_list:
                for art in sec.get('articles', []):
                    new_art = dict(art)
                    new_art['sector'] = sec.get('sector', '')
                    all_articles.append(new_art)
            all_articles.sort(
                key=lambda x: x.get('score') if isinstance(x.get('score'), (int, float)) else 0,
                reverse=True
            )
            top_headlines = all_articles[:5]
        except Exception:
            top_headlines = []

        npc_html = ''
        for art in top_headlines:
            score    = art.get('score', 0)
            sc       = 'var(--up)' if isinstance(score,(int,float)) and score>5 else 'var(--nt)' if isinstance(score,(int,float)) and score>2 else 'var(--pu-lt)'
            title    = _esc((art.get('title') or '')[:120])
            sector   = _esc((art.get('sector') or '').replace('_',' ').title())
            source   = _esc(art.get('source') or 'Unknown')
            pub      = _esc(art.get('published') or '')
            npc_html += (
                f'<div class="npc">'
                f'<div class="npc-stripe" style="background:linear-gradient(180deg,{sc},transparent)"></div>'
                f'<div>'
                f'<div class="npc-title">{title}</div>'
                f'<div class="npc-meta"><span class="ntag pu">{sector}</span> {source} &middot; {pub}</div>'
                f'</div></div>'
            )
        if not npc_html:
            npc_html = '<div style="color:var(--mist);font-family:var(--ff-mono);font-size:11px;">No signal headlines this run.</div>'

        # ── Inline page CSS ───────────────────────────────────────────────────
        page_css = (
            '<style>'
            '.idx-taskbar{display:flex;gap:8px;}'
            '.idx-chart-wrap canvas{width:100%!important;height:100%!important;}'
            '.exp-chart canvas{width:100%!important;height:100%!important;}'
            '</style>'
        )

        scan_time = now_et.strftime('%Y-%m-%d %H:%M ET')
        cand_count = rank_data.get('week', '')
        pg_sub     = f'{scan_time} &middot; Last scan'

        js_block = (
            f'<script>{_DAYS_JS}{_EASING_JS}{_GENIE_JS}{_SLIDE_JS}'
            f'{_TOGGLE_IDX_JS}{_BUILD_IDX_CHART_JS}'
            f'{_RAF_COLLAPSE_JS}{_RCT_JS}</script>'
            f'{idx_script}'
            f'<script>{_COPY_PROMPT_JS}</script>'
        )

        return (
            '<!DOCTYPE html><html lang="en"><head>'
            '<meta charset="UTF-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1.0">'
            '<meta name="description" content="MRE Market Research Engine — Live dashboard">'
            '<title>MRE // Market Overview</title>'
            f'{_FONTS_LINK}'
            f'{_CHARTJS}'
            '<link rel="stylesheet" href="assets/style.css">'
            f'{page_css}'
            f'{_LOADER_CSS}'
            '</head><body>'
            f'{_LOADER_HTML}'
            f'{_LOADER_JS}'
            '<div class="scanlines"></div>'
            f'{_nav_html("home")}'
            '<div class="pages"><div id="p-home" class="page on">'
            '<div class="pg-eyebrow stagger-1">Dashboard &middot; Active</div>'
            '<div class="pg-title stagger-1">Market <span class="hi">Overview</span></div>'
            f'<div class="pg-sub stagger-1">{pg_sub}</div>'
            '<div class="idx-section stagger-2">'
            '<div class="sl">Market Indices &middot; 30-day</div>'
            f'<div class="idx-taskbar">{pills}</div>'
            '<div class="idx-expand" id="idx-expand">'
            '<div class="idx-slide-viewport" id="idx-slide-viewport">'
            '<div class="idx-slide-track" id="idx-slide-track">'
            '<div class="idx-panel" id="idx-panel-active">'
            '<div class="idx-panel-header">'
            '<div class="idx-expand-name" id="idx-expand-name">\u2014</div>'
            '<div class="idx-expand-stats">'
            '<span>1M <span class="val" id="idx-stat-1m">\u2014</span></span>'
            '<span>3M <span class="val" id="idx-stat-3m">\u2014</span></span>'
            '<span>6M <span class="val" id="idx-stat-6m">\u2014</span></span>'
            '</div></div>'
            '<div class="idx-chart-wrap"><canvas id="idx-chart"></canvas></div>'
            '</div></div></div></div>'
            '</div>'
            '<div class="home-below" id="home-below">'
            f'{strip}'
            '<div class="stagger-4">'
            '<div class="sl">This Week\'s Best <a href="rank.html" class="rp-link" style="margin-left:8px">Full board &rarr;</a></div>'
            f'{rank_preview}'
            '</div>'
            '<div class="stagger-5">'
            '<div class="sl" style="margin-top:28px">Recent Reports</div>'
            f'{cards_html}'
            '</div>'
            '<div class="stagger-5">'
            '<div class="sl" style="margin-top:28px">Signal Headlines '
            '<a href="news.html" class="rp-link" style="margin-left:8px">All &rarr;</a></div>'
            f'<div class="npc-group">{npc_html}</div>'
            '</div>'
            '</div>'
            '</div></div>'
            '<footer><span>MRE</span> &middot; Free-tier data only &middot; Not investment advice &middot; Always verify before acting</footer>'
            f'{js_block}'
            f'<script>' + _INDEX_FETCH_JS + '</script>'
            '</body></html>'
        )
    except Exception as e:
        log.error(f'Index page render failed: {e}')
        return _err_page('home', 'Dashboard render error. Check logs.')


def _render_rank_html(rank_data: dict) -> str:
    try:
        week = rank_data.get('week', '')
        week_display = week.replace('W', ' \u2014 week ') if week else 'current week'

        return (
            '<!DOCTYPE html><html lang="en"><head>'
            '<meta charset="UTF-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1.0">'
            '<meta name="description" content="MRE Weekly Rank Board">'
            '<title>MRE // Weekly Rankings</title>'
            f'{_FONTS_LINK}'
            f'{_CHARTJS}'
            '<link rel="stylesheet" href="assets/style.css">'
            f'{_LOADER_CSS}'
            '<style>'
            '.exp-chart canvas{width:100%!important;height:100%!important;}'
            '.est-divider{width:100%;height:1px;background:var(--rim);margin:6px 0;grid-column:1/-1;}'
            '.est-ps{font-weight:bold;}'
            '.est-ps-good{color:var(--up);}'
            '.est-ps-extended{color:var(--dn);}'
            '.est-ps-early{color:var(--nt);}'
            '.est-ps-weak{color:var(--dn);}'
            '.est-ps-unavailable{color:var(--slate);}'
            '</style>'
            '</head><body>'
            f'{_LOADER_HTML}'
            f'{_LOADER_JS}'
            '<div class="scanlines"></div>'
            f'{_nav_html("rank")}'
            '<div class="pages"><div id="p-rank" class="page on">'
            '<div class="pg-eyebrow">Rank Board &middot; Active</div>'
            '<div class="pg-title">Weekly <span class="hi">Rankings</span></div>'
            f'<div class="pg-sub">{_esc(week_display)} &middot; Resets Monday &middot; Click row to expand</div>'
            '<div class="rank-wrap">'
            '<div id="rank-board-mount"></div>'
            '</div>'
            '</div></div>'
            '<footer><span>MRE</span> &middot; Free-tier data only &middot; Not investment advice</footer>'
            f'<script>{_DAYS_JS}{_EASING_JS}{_RAF_COLLAPSE_JS}{_EXP_T_JS}{_COPY_PROMPT_JS}</script>'
            '<script>' + _RANK_FETCH_JS + '</script>'
            '</body></html>'
        )
    except Exception as e:
        log.error(f'Rank page render failed: {e}')
        return _err_page('rank', 'Rank render error. Check logs.')


def _render_archive_html(archive_data: dict) -> str:
    try:
        return (
            '<!DOCTYPE html><html lang="en"><head>'
            '<meta charset="UTF-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1.0">'
            '<meta name="description" content="MRE Report Archive">'
            '<title>MRE // Report Archive</title>'
            f'{_FONTS_LINK}'
            '<link rel="stylesheet" href="assets/style.css">'
            f'{_LOADER_CSS}'
            '</head><body>'
            f'{_LOADER_HTML}'
            f'{_LOADER_JS}'
            '<div class="scanlines"></div>'
            f'{_nav_html("archive")}'
            '<div class="pages"><div id="p-archive" class="page on">'
            '<div class="pg-eyebrow">History &middot; Stored</div>'
            '<div class="pg-title">Report <span class="hi">Archive</span></div>'
            '<div class="pg-sub">12 weeks retained &middot; 10 runs per week max</div>'
            '<div id="archive-mount"></div>'
            '</div></div>'
            '<footer><span>MRE</span> &middot; Free-tier data only &middot; Not investment advice</footer>'
            f'<script>{_RCT_JS}{_COPY_PROMPT_JS}</script>'
            '<script>' + _ARCHIVE_FETCH_JS + '</script>'
            '</body></html>'
        )
    except Exception as e:
        log.error(f'Archive render failed: {e}')
        return _err_page('archive', 'Archive render error. Check logs.')


def _render_news_html(sectors: list, generated: str) -> str:
    try:
        if not sectors:
            body = (
                '<div style="color:var(--mist);font-family:var(--ff-mono);font-size:11px;padding:28px 0;">'
                'No sector news this run. Headlines will appear when sector signals are confirmed.'
                '</div>'
            )
        else:
            body = ''
            stripe_colors = [
                'linear-gradient(180deg,var(--up),transparent)',
                'linear-gradient(180deg,var(--nt),transparent)',
                'linear-gradient(180deg,var(--pu-lt),transparent)',
                'linear-gradient(180deg,var(--cyan),transparent)',
                'linear-gradient(180deg,var(--mg),transparent)',
            ]
            for si, sec in enumerate(sectors):
                sector_name = _esc((sec.get('sector') or '').replace('_', ' ').title())
                articles    = sec.get('articles', [])
                if not articles:
                    continue
                sc = stripe_colors[si % len(stripe_colors)]
                body += (
                    f'<div class="news-section">'
                    f'<div class="news-sec-head">'
                    f'<div class="nsh-stripe" style="background:{sc}"></div>'
                    f'<span class="nsh-name">{sector_name}</span>'
                    f'<span class="nsh-count">// {len(articles)} article{"s" if len(articles)!=1 else ""}</span>'
                    f'</div>'
                )
                for art in articles:
                    title   = _esc((art.get('title') or '')[:200])
                    summary = _esc((art.get('body') or art.get('summary') or '')[:400])
                    source  = _esc(art.get('source') or 'Unknown')
                    pub     = _esc(art.get('published') or '')
                    body    += (
                        f'<div class="news-card-full">'
                        f'<div class="ncf-title">{title}</div>'
                        f'<div class="ncf-summary">{summary}</div>'
                        f'<div class="ncf-foot">'
                        f'<span class="ncf-source">{source} &middot; {pub}</span>'
                        f'</div></div>'
                    )
                body += '</div>'

        return (
            '<!DOCTYPE html><html lang="en"><head>'
            '<meta charset="UTF-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1.0">'
            '<meta name="description" content="MRE Signal Feed">'
            '<title>MRE // Signal Feed</title>'
            f'{_FONTS_LINK}'
            '<link rel="stylesheet" href="assets/style.css">'
            f'{_LOADER_CSS}'
            '</head><body>'
            f'{_LOADER_HTML}'
            f'{_LOADER_JS}'
            '<div class="scanlines"></div>'
            f'{_nav_html("news")}'
            '<div class="pages"><div id="p-news" class="page on">'
            '<div class="pg-eyebrow">Signal Feed &middot; Current</div>'
            '<div class="pg-title">Today\'s <span class="hi">News</span></div>'
            f'<div class="pg-sub">Engine-filtered headlines &middot; {_esc(generated)}</div>'
            f'{body}'
            '</div></div>'
            '<footer><span>MRE</span> &middot; Free-tier data only &middot; Not investment advice</footer>'
            '<script>document.addEventListener("DOMContentLoaded",function(){if(window.dismissLoader)window.dismissLoader();});</script>'
            '</body></html>'
        )
    except Exception as e:
        log.error(f'News render failed: {e}')
        return _err_page('news', 'News render error. Check logs.')


# ── Sub6 Paper Trading ───────────────────────────────────────────────────────

def write_trades_json(paper_trading_summary: dict) -> None:
    try:
        from contracts.eq_schema import (
            PT_AVAILABLE, PT_OPEN_COUNT, PT_NEW_COUNT, PT_CLOSED_COUNT
        )
        from contracts.paper_trading_schema import (
            PT_TICKER, PT_ENTRY_DATE, PT_ENTRY_RUN, PT_ENTRY_TIMESTAMP,
            PT_ENTRY_PRICE, PT_STOP_LOSS, PT_PRICE_TARGET, PT_RISK_REWARD,
            PT_POSITION_SIZE_PCT, PT_MARKET_VERDICT, PT_ENTRY_QUALITY,
            PT_EQ_VERDICT, PT_ROTATION_SIGNAL, PT_ALIGNMENT, PT_COMPOSITE_SCORE,
            PT_MARKET_REGIME, PT_INSIDER_SIGNAL, PT_EVENT_RISK,
            PT_EXPECTATIONS_SIGNAL, PT_STATUS, PT_EXIT_DATE, PT_EXIT_RUN,
            PT_EXIT_PRICE, PT_EXIT_REASON, PT_LIVE_PNL_PCT, PT_DAYS_HELD,
            PT_CLOSED_AT_TIMESTAMP, PT_EXPECTED_RETURN_PCT, PT_ERROR_PCT,
            PT_DIRECTION_CORRECT, PT_BENCHMARK_RETURN, PT_ALPHA,
            PT_LAST_UPDATED_RUN, PT_DATA_VALID, PT_VERSION, PT_IS_TEST,
            PT_STATUS_OPEN, PT_STATUS_CLOSED, PT_STATUS_DROPPED,
        )

        pt_avail = paper_trading_summary.get('pt_available', False)
        trades_list = paper_trading_summary.get('trades', [])
        
        output = {
            "generated_at": datetime.now(pytz.utc).isoformat(),
            "pt_available": pt_avail,
            "open_count":   paper_trading_summary.get('open_count', 0),
            "new_count":    paper_trading_summary.get('new_count', 0),
            "closed_count": paper_trading_summary.get('closed_count', 0),
            "total_count":  len(trades_list),
            "real_open_count":   paper_trading_summary.get('real_open_count', 0),
            "real_new_count":    paper_trading_summary.get('real_new_count', 0),
            "real_closed_count": paper_trading_summary.get('real_closed_count', 0),
            "test_open_count":   paper_trading_summary.get('test_open_count', 0),
            "test_new_count":    paper_trading_summary.get('test_new_count', 0),
            "test_closed_count": paper_trading_summary.get('test_closed_count', 0),
            "trades": []
        }
        
        for t in trades_list:
            output["trades"].append({
                "trade_id": t.get("trade_id"),
                PT_TICKER: t.get(PT_TICKER),
                PT_ENTRY_DATE: t.get(PT_ENTRY_DATE),
                PT_ENTRY_RUN: t.get(PT_ENTRY_RUN),
                PT_ENTRY_TIMESTAMP: t.get(PT_ENTRY_TIMESTAMP),
                PT_ENTRY_PRICE: t.get(PT_ENTRY_PRICE),
                PT_STOP_LOSS: t.get(PT_STOP_LOSS),
                PT_PRICE_TARGET: t.get(PT_PRICE_TARGET),
                PT_RISK_REWARD: t.get(PT_RISK_REWARD),
                PT_POSITION_SIZE_PCT: t.get(PT_POSITION_SIZE_PCT),
                PT_MARKET_VERDICT: t.get(PT_MARKET_VERDICT),
                PT_ENTRY_QUALITY: t.get(PT_ENTRY_QUALITY),
                PT_EQ_VERDICT: t.get(PT_EQ_VERDICT),
                PT_ROTATION_SIGNAL: t.get(PT_ROTATION_SIGNAL),
                PT_ALIGNMENT: t.get(PT_ALIGNMENT),
                PT_COMPOSITE_SCORE: t.get(PT_COMPOSITE_SCORE),
                PT_MARKET_REGIME: t.get(PT_MARKET_REGIME),
                PT_INSIDER_SIGNAL: t.get(PT_INSIDER_SIGNAL),
                PT_EVENT_RISK: t.get(PT_EVENT_RISK),
                PT_EXPECTATIONS_SIGNAL: t.get(PT_EXPECTATIONS_SIGNAL),
                PT_STATUS: t.get(PT_STATUS),
                PT_EXIT_DATE: t.get(PT_EXIT_DATE),
                PT_EXIT_RUN: t.get(PT_EXIT_RUN),
                PT_EXIT_PRICE: t.get(PT_EXIT_PRICE),
                PT_EXIT_REASON: t.get(PT_EXIT_REASON),
                PT_LIVE_PNL_PCT: t.get(PT_LIVE_PNL_PCT),
                PT_DAYS_HELD: t.get(PT_DAYS_HELD),
                PT_CLOSED_AT_TIMESTAMP: t.get(PT_CLOSED_AT_TIMESTAMP),
                PT_EXPECTED_RETURN_PCT: t.get(PT_EXPECTED_RETURN_PCT),
                PT_ERROR_PCT: t.get(PT_ERROR_PCT),
                PT_DIRECTION_CORRECT: t.get(PT_DIRECTION_CORRECT),
                PT_BENCHMARK_RETURN: t.get(PT_BENCHMARK_RETURN),
                PT_ALPHA: t.get(PT_ALPHA),
                PT_LAST_UPDATED_RUN: t.get(PT_LAST_UPDATED_RUN),
                PT_DATA_VALID: t.get(PT_DATA_VALID),
                PT_VERSION: t.get(PT_VERSION),
                PT_IS_TEST: bool(t.get(PT_IS_TEST, False)),
            })
            
        out_path = os.path.join(DATA_DIR, 'trades.json')
        tmp = out_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False)
        os.replace(tmp, out_path)
    except Exception as e:
        log.warning(f'trades.json write failed: {e}')


def build_trades_page(paper_trading_summary: dict) -> None:
    html_content = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1.0">'
        '<title>Paper Trading | MRE</title>'
        f'{_FONTS_LINK}'
        '<link rel="stylesheet" href="assets/style.css">'
        f'{_LOADER_CSS}'
        '</head><body>'
        f'{_LOADER_HTML}'
        f'{_LOADER_JS}'
        '<div class="scanlines"></div>'
        f'{_nav_html("trades")}'
        '<div class="pages">'
        '<div class="page on">'
        '<div class="pg-eyebrow">LEDGER</div>'
        '<div class="pg-title">Paper <span class="hi">Trading</span></div>'
        f'<div class="pg-sub">Simulated trade ledger | Google Sheets backed'
        f'<span style="float:right;color:var(--pu);">Generated: {datetime.now(pytz.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}</span></div>'
        
        '<div id="pt-mount"></div>'
        
        '</div>'
        '</div>'
        
        '<script>'
        'function fmtPct(val) {'
        '  if (val === null || val === undefined) return "\\u2014";'
        '  return val.toFixed(2) + "%";'
        '}'
        'function fmtErrPct(val) {'
        '  if (val === null || val === undefined) return "\\u2014";'
        '  var s = val > 0 ? "+" : "";'
        '  var c = val > 0 ? "pt-pnl-pos" : val < 0 ? "pt-pnl-neg" : "";'
        '  return "<span class=\\"" + c + "\\">" + s + val.toFixed(2) + "%</span>";'
        '}'
        'function fmtPnl(val) {'
        '  if (val === null || val === undefined) return "\\u2014";'
        '  var c = val > 0 ? "pt-pnl-pos" : val < 0 ? "pt-pnl-neg" : "";'
        '  return "<span class=\\"" + c + "\\">" + val.toFixed(2) + "%</span>";'
        '}'
        'function fmtNum(val, dec) {'
        '  if (val === null || val === undefined) return "\\u2014";'
        '  return val.toFixed(dec);'
        '}'
        'function fmtPrice(val) {'
        '  if (val === null || val === undefined) return "\\u2014";'
        '  return "$" + val.toFixed(2);'
        '}'
        'function calcDaysOpen(entryDate) {'
        '  if (!entryDate) return "\\u2014";'
        '  var e = new Date(entryDate);'
        '  var diff = Date.now() - e.getTime();'
        '  return Math.max(0, Math.floor(diff / (1000 * 3600 * 24)));'
        '}'
        'function getPillClass(reason) {'
        '  if (reason === "TARGET_HIT") return "pt-pill-target";'
        '  if (reason === "STOP_HIT") return "pt-pill-stop";'
        '  if (reason === "TIMEOUT") return "pt-pill-timeout";'
        '  if (reason === "DROPPED") return "pt-pill-dropped";'
        '  return "pt-pill-dropped";'
        '}'
        
        'function renderTrades(data) {'
        '  if (!data.pt_available) {'
        '    document.getElementById("pt-mount").innerHTML = '
        '      "<div class=\\"pt-unavailable\\">Paper trading data unavailable \\u2014 Google Sheets connection required.</div>";'
        '    if(window.dismissLoader) window.dismissLoader();'
        '    return;'
        '  }'
        
        '  var realOpen   = data.real_open_count   || 0;'
        '  var realNew    = data.real_new_count    || 0;'
        '  var realClosed = data.real_closed_count || 0;'
        '  var testOpen   = data.test_open_count   || 0;'
        '  var testNew    = data.test_new_count    || 0;'
        '  var hc = "<div class=\\"pt-scorecard stagger-1\\">";'
        '  hc += "<div class=\\"pt-stat-tile\\"><span class=\\"pt-stat-value\\">" + realOpen + "</span><span class=\\"pt-stat-label\\">Open Trades</span></div>";'
        '  hc += "<div class=\\"pt-stat-tile\\"><span class=\\"pt-stat-value\\">" + realNew + "</span><span class=\\"pt-stat-label\\">New This Run</span></div>";'
        '  hc += "<div class=\\"pt-stat-tile\\"><span class=\\"pt-stat-value\\">" + realClosed + "</span><span class=\\"pt-stat-label\\">Closed This Run</span></div>";'
        '  var realTotal = realOpen + realClosed;'
        '  hc += "<div class=\\"pt-stat-tile\\"><span class=\\"pt-stat-value\\">" + realTotal + "</span><span class=\\"pt-stat-label\\">Total Trades</span></div>";'
        '  if (testOpen > 0 || testNew > 0) {'
        '    hc += "<div class=\\"pt-stat-tile pt-stat-tile-test\\"><span class=\\"pt-stat-value\\">" + testOpen + "</span><span class=\\"pt-stat-label\\">TEST Open</span></div>";'
        '    hc += "<div class=\\"pt-stat-tile pt-stat-tile-test\\"><span class=\\"pt-stat-value\\">" + testNew + "</span><span class=\\"pt-stat-label\\">TEST New</span></div>";'
        '  }'
        '  hc += "</div>";'
        
        '  var allTrades = Array.isArray(data.trades) ? data.trades : [];'
        '  var realOp = allTrades.filter(function(t) { return t.status === "OPEN" && !t.is_test; });'
        '  var realCl = allTrades.filter(function(t) { return (t.status === "CLOSED" || t.status === "DROPPED") && !t.is_test; });'
        '  var testOp = allTrades.filter(function(t) { return t.status === "OPEN" && t.is_test; });'
        '  var testCl = allTrades.filter(function(t) { return (t.status === "CLOSED" || t.status === "DROPPED") && t.is_test; });'
        
        '  function openRow(t) {'
        '    var reg = t.market_regime || "";'
        '    var regCol = reg === "BULL" ? "var(--up)" : reg === "BEAR" ? "var(--dn)" : "var(--nt)";'
        '    var badge = t.is_test ? " <span class=\\"pt-test-badge\\">TEST</span>" : "";'
        '    var row = "<tr>";'
        '    row += "<td data-label=\\"Ticker\\" style=\\"color:#fff;font-weight:700;\\">" + (t.ticker || "\\u2014") + badge + "</td>";'
        '    row += "<td data-label=\\"Entry Date\\">" + (t.entry_date || "\\u2014") + "</td>";'
        '    row += "<td data-label=\\"Entry $\\">" + fmtPrice(t.entry_price) + "</td>";'
        '    row += "<td data-label=\\"Stop $\\">" + fmtPrice(t.stop_loss) + "</td>";'
        '    row += "<td data-label=\\"Target $\\">" + fmtPrice(t.price_target) + "</td>";'
        '    row += "<td data-label=\\"R/R\\">" + (t.risk_reward_ratio !== null && t.risk_reward_ratio !== undefined ? t.risk_reward_ratio.toFixed(2)+"x" : "\\u2014") + "</td>";'
        '    row += "<td data-label=\\"Regime\\"><span style=\\"color:" + regCol + "\\">" + reg + "</span></td>";'
        '    row += "<td data-label=\\"Quality\\">" + (t.entry_quality || "\\u2014") + "</td>";'
        '    row += "<td data-label=\\"Days Open\\">" + calcDaysOpen(t.entry_date) + "</td>";'
        '    row += "<td data-label=\\"Score\\">" + fmtNum(t.composite_score, 1) + "</td>";'
        '    row += "</tr>";'
        '    return row;'
        '  }'
        
        '  function closedRow(t) {'
        '    var dir = t.direction_correct;'
        '    var dirH = dir === true ? "<span style=\\"color:#00f0ff;font-weight:bold;\\">\\u2713</span>" : dir === false ? "<span style=\\"color:#ff2d78;font-weight:bold;\\">\\u2717</span>" : "\\u2014";'
        '    var res = t.exit_reason || "DROPPED";'
        '    var resH = "<span class=\\"" + getPillClass(res) + "\\">" + res + "</span>";'
        '    var badge = t.is_test ? " <span class=\\"pt-test-badge\\">TEST</span>" : "";'
        '    var row = "<tr>";'
        '    row += "<td data-label=\\"Ticker\\" style=\\"color:#fff;font-weight:700;\\">" + (t.ticker || "\\u2014") + badge + "</td>";'
        '    row += "<td data-label=\\"Entry\\">" + (t.entry_date || "\\u2014") + "</td>";'
        '    row += "<td data-label=\\"Exit\\">" + (t.exit_date || "\\u2014") + "</td>";'
        '    row += "<td data-label=\\"P&L %\\">" + fmtPnl(t.live_pnl_pct) + "</td>";'
        '    row += "<td data-label=\\"Exit Reason\\">" + resH + "</td>";'
        '    row += "<td data-label=\\"Expected %\\">" + fmtPct(t.expected_return_pct) + "</td>";'
        '    row += "<td data-label=\\"Error %\\">" + fmtErrPct(t.error_pct) + "</td>";'
        '    row += "<td data-label=\\"Direction\\" style=\\"text-align:center;\\">" + dirH + "</td>";'
        '    row += "<td data-label=\\"Days\\">" + (t.days_held !== null && t.days_held !== undefined ? t.days_held : "\\u2014") + "</td>";'
        '    row += "<td data-label=\\"Verdict\\">" + (t.market_verdict || "\\u2014") + "</td>";'
        '    row += "</tr>";'
        '    return row;'
        '  }'
        
        '  function openTable(rows) {'
        '    rows.sort(function(a,b) { var da = a.entry_date || ""; var db = b.entry_date || ""; return da < db ? 1 : da > db ? -1 : 0; });'
        '    var tbl = "<div class=\\"pt-table pt-open-table\\"><table><thead><tr>";'
        '    tbl += "<th>Ticker</th><th>Entry Date</th><th>Entry $</th><th>Stop $</th><th>Target $</th><th>R/R</th><th>Regime</th><th>Quality</th><th>Days Open (cal.)</th><th>Score</th>";'
        '    tbl += "</tr></thead><tbody>";'
        '    rows.forEach(function(t) { tbl += openRow(t); });'
        '    tbl += "</tbody></table></div>";'
        '    return tbl;'
        '  }'
        
        '  function closedTable(rows) {'
        '    rows.sort(function(a,b) { var da = a.exit_date || "0000"; var db = b.exit_date || "0000"; return da < db ? 1 : da > db ? -1 : 0; });'
        '    var tbl = "<div class=\\"pt-table pt-closed-table\\"><table><thead><tr>";'
        '    tbl += "<th>Ticker</th><th>Entry</th><th>Exit</th><th>P&L %</th><th>Exit Reason</th><th>Expected %</th><th>Error %</th><th>Direction</th><th>Days</th><th>Verdict</th>";'
        '    tbl += "</tr></thead><tbody>";'
        '    rows.forEach(function(t) { tbl += closedRow(t); });'
        '    tbl += "</tbody></table></div>";'
        '    return tbl;'
        '  }'
        
        '  hc += "<div class=\\"sl stagger-2\\">OPEN TRADES</div>";'
        '  if (realOp.length === 0) {'
        '    hc += "<div class=\\"stagger-2\\" style=\\"margin-bottom:2rem;color:var(--mist);font-size:0.9rem;\\">No open trades.</div>";'
        '  } else {'
        '    hc += openTable(realOp);'
        '  }'
        
        '  hc += "<div class=\\"sl stagger-3\\">CLOSED TRADES</div>";'
        '  if (realCl.length === 0) {'
        '    hc += "<div class=\\"stagger-3\\" style=\\"margin-bottom:2rem;color:var(--mist);font-size:0.9rem;\\">No closed trades.</div>";'
        '  } else {'
        '    hc += closedTable(realCl);'
        '  }'
        
        '  if (testOp.length > 0 || testCl.length > 0) {'
        '    hc += "<div class=\\"sl stagger-4 pt-test-section-label\\">TEST TRADES \\u2014 debug only, excluded from all strategy metrics</div>";'
        '    hc += "<div class=\\"pt-test-notice\\">These trades were generated during a debug run. They are financially realistic but do not reflect strategy decisions and will be removed by the cleanup workflow.</div>";'
        '    if (testOp.length > 0) { hc += openTable(testOp); }'
        '    if (testCl.length > 0) { hc += closedTable(testCl); }'
        '  }'
        
        '  document.getElementById("pt-mount").innerHTML = hc;'
        '  if(window.dismissLoader) window.dismissLoader();'
        '}'
        
        'function showUnavailable() {'
        '  document.getElementById("pt-mount").innerHTML = '
        '    "<div class=\\"pt-unavailable\\">Paper trading data unavailable \\u2014 Google Sheets connection required.</div>";'
        '  if(window.dismissLoader) window.dismissLoader();'
        '}'
        
        'fetch("assets/data/trades.json?v=" + Date.now())'
        '  .then(function(r){ return r.ok ? r.json() : Promise.reject(r.status); })'
        '  .then(function(data){ renderTrades(data); })'
        '  .catch(function(err){ showUnavailable(); });'
        '</script>'
        '</body></html>'
    )
    
    try:
        out_path = os.path.join(DOCS_DIR, 'trades.html')
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
    except Exception as e:
        log.error(f'trades.html write failed: {e}')


# ─────────────────────────────────────────────────────────────────────────────
# DEBUG TEST LAYER  (tests.json + tests.html)
# Test runs are written here — never to rank.json or weekly_archive.json.
# Label: every entry has is_test=True.  Cleanup: --delete-tests in
# scripts/cleanup_reports.py removes all entries from tests.json and any
# TEST_* rows from Google Sheets.
# ─────────────────────────────────────────────────────────────────────────────

_TESTS_MAX_ENTRIES = 50  # hard cap — oldest entries dropped first


def _build_test_log(companies: list, active_subs: set, slot: str, paper_trading_summary: dict | None = None) -> str:
    """
    Build a plain-text log block for one test run.
    Shows per-ticker outputs for each active subsystem in a format
    suitable for raw inspection — selectable text, no fancy formatting.
    """
    now_et    = datetime.now(pytz.utc).astimezone(pytz.timezone('America/New_York'))
    lines     = []
    _show_all = not active_subs  # scheduled runs pass empty set → show all subs

    _run_kind = 'SCHEDULED RUN' if _show_all else 'TEST RUN'
    lines.append(f'{_run_kind} — {now_et.strftime("%Y-%m-%d %H:%M:%S ET")}')
    lines.append(f'Slot     : {slot}')
    lines.append(f'Subs     : {"all" if _show_all else ", ".join(sorted(active_subs))}')
    lines.append(f'Tickers  : {", ".join(c.get("ticker","?") for c in companies)}')
    lines.append('─' * 72)

    for c in companies:
        t = c.get('ticker', '?')
        lines.append(f'\n{"═"*72}')
        lines.append(f'TICKER: {t}  —  {c.get("company_name", "")}')
        lines.append('═' * 72)

        # ── Sub1: Core scoring ──────────────────────────────────────────
        if _show_all or 'sub1' in active_subs:
            lines.append('\n[SUB1] Filter Candidates / Core Scoring')
            lines.append(f'  current_price        : {c.get("current_price")}')
            lines.append(f'  sector               : {c.get("sector")}')
            lines.append(f'  composite_confidence : {c.get("composite_confidence")}')
            lines.append(f'  confidence_label     : {c.get("confidence_label")}')
            lines.append(f'  risk_score           : {c.get("risk_score")}')
            lines.append(f'  risk_label           : {c.get("risk_label")}')
            lines.append(f'  opportunity_score    : {c.get("opportunity_score")}')
            lines.append(f'  agreement_score      : {c.get("agreement_score")}')
            lines.append(f'  agreement_label      : {c.get("agreement_label")}')
            lines.append(f'  market_verdict       : {c.get("market_verdict_display")}')
            lines.append(f'  alignment            : {c.get("alignment")}')
            _ram = c.get('ram') or {}
            lines.append(f'  ram_score            : {_ram.get("ram_score")}')
            lines.append(f'  return_1m            : {c.get("return_1m")}')
            lines.append(f'  return_3m            : {c.get("return_3m")}')
            lines.append(f'  return_6m            : {c.get("return_6m")}')
            _vol = c.get('volume_confirmation') or {}
            lines.append(f'  volume_score         : {_vol.get("volume_score")}')
            lines.append(f'  volume_ratio         : {_vol.get("volume_ratio")}')
            _uv  = c.get('unusual_volume') or {}
            lines.append(f'  unusual_volume_flag  : {_uv.get("unusual_flag")}')
            _dd  = c.get('drawdown') or {}
            lines.append(f'  drawdown_score       : {_dd.get("drawdown_score")}')
            _fin = c.get('financials') or {}
            lines.append(f'  earnings_warning     : {c.get("earnings_warning")}')
            lines.append(f'  divergence_warning   : {c.get("divergence_warning")}')
            _bkt = c.get('bucket_scores') or {}
            if _bkt:
                lines.append('  bucket_scores        :')
                for _bk, _bv in _bkt.items():
                    lines.append(f'    {_bk:<28}: {_bv}')
            _rsk = c.get('risk_components') or {}
            if _rsk:
                lines.append('  risk_components      :')
                for _rk, _rv in _rsk.items():
                    lines.append(f'    {_rk:<28}: {_rv}')

        # ── Sub2: Earnings Quality ──────────────────────────────────────
        if _show_all or 'sub2' in active_subs:
            lines.append('\n[SUB2] Earnings Quality Analyzer')
            lines.append(f'  eq_available         : {c.get("eq_available")}')
            if c.get('eq_available'):
                lines.append(f'  eq_score_final       : {c.get("eq_score_final")}')
                lines.append(f'  eq_label             : {c.get("eq_label")}')
                lines.append(f'  pass_tier            : {c.get("pass_tier")}')
                lines.append(f'  final_classification : {c.get("final_classification")}')
                lines.append(f'  eq_percentile        : {c.get("eq_percentile")}')
                lines.append(f'  data_confidence      : {c.get("data_confidence")}')
                lines.append(f'  fatal_flaw_reason    : {c.get("fatal_flaw_reason")}')
                lines.append(f'  batch_regime         : {c.get("batch_regime")}')
                lines.append(f'  combined_priority    : {c.get("combined_priority_score")}')
                _str = c.get('top_strengths') or []
                lines.append(f'  top_strengths        : {_str}')
                _rsk2 = c.get('top_risks') or []
                lines.append(f'  top_risks            : {_rsk2}')
                _warn = c.get('warnings') or []
                lines.append(f'  warnings             : {_warn}')
            # 1A/1B sub-modules
            lines.append(f'  event_risk           : {c.get("event_risk")}')
            lines.append(f'  event_risk_reason    : {c.get("event_risk_reason")}')
            lines.append(f'  days_to_earnings     : {c.get("days_to_earnings")}')
            lines.append(f'  insider_signal       : {c.get("insider_signal")}')
            lines.append(f'  insider_note         : {c.get("insider_note")}')
            lines.append(f'  expectations_signal  : {c.get("expectations_signal")}')
            lines.append(f'  earnings_beat_rate   : {c.get("earnings_beat_rate")}')
            lines.append(f'  peg_ratio            : {c.get("peg_ratio")}')

        # ── Sub3: Sector Rotation ───────────────────────────────────────
        if _show_all or 'sub3' in active_subs:
            lines.append('\n[SUB3] Sector Rotation Detector')
            lines.append(f'  rotation_available   : {c.get("rotation_available")}')
            if c.get('rotation_available'):
                lines.append(f'  rotation_score       : {c.get("rotation_score")}')
                lines.append(f'  rotation_status      : {c.get("rotation_status")}')
                lines.append(f'  rotation_signal      : {c.get("rotation_signal")}')
                lines.append(f'  rotation_signal_disp : {c.get("rotation_signal_display")}')
                lines.append(f'  sector_etf           : {c.get("sector_etf")}')
                lines.append(f'  rotation_confidence  : {c.get("rotation_confidence")}')
                lines.append(f'  rotation_reasoning   : {c.get("rotation_reasoning")}')
                lines.append(f'  timeframes_used      : {c.get("timeframes_used")}')

        # ── Sub4: Price Structure ───────────────────────────────────────
        if _show_all or 'sub4' in active_subs:
            lines.append('\n[SUB4] Price Structure Analyzer')
            lines.append(f'  ps_available         : {c.get("ps_available")}')
            if c.get('ps_available'):
                lines.append(f'  entry_quality        : {c.get("entry_quality")}')
                lines.append(f'  ps_verdict_display   : {c.get("ps_verdict_display")}')
                lines.append(f'  trend_structure      : {c.get("trend_structure")}')
                lines.append(f'  trend_strength       : {c.get("trend_strength")}')
                lines.append(f'  key_level_position   : {c.get("key_level_position")}')
                lines.append(f'  volatility_state     : {c.get("volatility_state")}')
                lines.append(f'  compression_location : {c.get("compression_location")}')
                lines.append(f'  consolidation_conf   : {c.get("consolidation_confirmed")}')
                lines.append(f'  support_reaction     : {c.get("support_reaction")}')
                lines.append(f'  base_duration_days   : {c.get("base_duration_days")}')
                lines.append(f'  volume_contraction   : {c.get("volume_contraction")}')
                lines.append(f'  price_action_score   : {c.get("price_action_score")}')
                lines.append(f'  move_extension_pct   : {c.get("move_extension_pct")}')
                lines.append(f'  dist_to_support_pct  : {c.get("distance_to_support_pct")}')
                lines.append(f'  dist_to_resist_pct   : {c.get("distance_to_resistance_pct")}')
                lines.append(f'  structure_state      : {c.get("structure_state")}')
                lines.append(f'  recent_crossover     : {c.get("recent_crossover")}')
                lines.append(f'  ps_data_confidence   : {c.get("ps_data_confidence")}')
                lines.append(f'  entry_price          : {c.get("entry_price")}')
                lines.append(f'  stop_loss            : {c.get("stop_loss")}')
                lines.append(f'  price_target         : {c.get("price_target")}')
                lines.append(f'  risk_reward_ratio    : {c.get("risk_reward_ratio")}')
                lines.append(f'  rr_override          : {c.get("rr_override")}')
                _ps_rsn = c.get('ps_reasoning') or ''
                lines.append(f'  ps_reasoning         : {_ps_rsn}')

        # ── Sub5: Portfolio Layer ───────────────────────────────────────
        if _show_all or 'sub5' in active_subs:
            lines.append('\n[SUB5] Portfolio & Correlation Layer')
            lines.append(f'  pl_available         : {c.get("pl_available")}')
            if c.get('pl_available'):
                lines.append(f'  pl_selected          : {c.get("pl_selected")}')
                lines.append(f'  pl_position_weight   : {c.get("pl_position_weight")}')
                lines.append(f'  pl_cluster_id        : {c.get("pl_cluster_id")}')
                lines.append(f'  pl_correlation_flags : {c.get("pl_correlation_flags")}')
                lines.append(f'  pl_exclusion_reason  : {c.get("pl_exclusion_reason")}')

        # ── Sub6: Paper Trading ─────────────────────────────────────────
        if _show_all or 'sub6' in active_subs:
            lines.append('\n[SUB6] Paper Trading Engine')
            pt = paper_trading_summary or {}
            if not pt.get('pt_available', False):
                lines.append('  pt_available         : False')
            else:
                lines.append(f'  pt_available         : True')
                lines.append(f'  open_count           : {pt.get("open_count", 0)}')
                lines.append(f'  new_count            : {pt.get("new_count", 0)}')
                lines.append(f'  closed_count         : {pt.get("closed_count", 0)}')
                # Per-ticker trade detail — match trades to this candidate by ticker
                ticker_trades = [
                    tr for tr in pt.get('trades', [])
                    if tr.get('ticker') == c.get('ticker')
                ]
                if ticker_trades:
                    for tr in ticker_trades:
                        lines.append(f'  trade_id             : {tr.get("trade_id")}')
                        lines.append(f'  status               : {tr.get("status")}')
                        lines.append(f'  entry_price          : {tr.get("entry_price")}')
                        lines.append(f'  stop_loss            : {tr.get("stop_loss")}')
                        lines.append(f'  price_target         : {tr.get("price_target")}')
                        lines.append(f'  risk_reward_ratio    : {tr.get("risk_reward_ratio")}')
                        lines.append(f'  entry_date           : {tr.get("entry_date")}')
                        lines.append(f'  exit_date            : {tr.get("exit_date")}')
                        lines.append(f'  exit_reason          : {tr.get("exit_reason")}')
                        lines.append(f'  live_pnl_pct         : {tr.get("live_pnl_pct")}')
                        lines.append(f'  days_held            : {tr.get("days_held")}')
                        lines.append(f'  is_test              : {tr.get("is_test")}')
                else:
                    lines.append('  (no trade for this ticker this run)')

        # ── FSV: Financial Standards Validator ──────────────────────────
        _val = c.get('_validator')
        if _val:
            _tv  = _val.get('ticker_verdict', 'UNKNOWN')
            _inc = _val.get('inconsistent_count', 0)
            _que = _val.get('questionable_count', 0)
            _con = _val.get('consistent_count', 0)
            lines.append('\n[FSV] Financial Standards Validator')
            lines.append(f'  ticker_verdict       : {_tv}')
            lines.append(f'  inconsistent_count   : {_inc}')
            lines.append(f'  questionable_count   : {_que}')
            lines.append(f'  consistent_count     : {_con}')
            _checks = _val.get('checks') or []
            _flagged = [ch for ch in _checks if ch.get('verdict') in ('INCONSISTENT', 'QUESTIONABLE')]
            if _flagged:
                lines.append('  flags:')
                for _ch in _flagged:
                    lines.append(
                        f'    [{_ch.get("verdict","?")}] {_ch.get("check_id","?")} '
                        f'— {_ch.get("note","")}'
                    )
            else:
                lines.append('  flags                : (none)')
        else:
            lines.append('\n[FSV] Financial Standards Validator')
            lines.append('  (validator did not run for this ticker)')

    lines.append(f'\n{"─"*72}')
    lines.append('END OF TEST LOG')
    return '\n'.join(lines)


def _write_tests_json(test_entry: dict) -> None:
    """
    Append a test run entry to tests.json.
    Cap at _TESTS_MAX_ENTRIES — oldest entries dropped when over limit.
    All entries carry is_test=True for cleanup targeting.
    """
    tests_path = os.path.join(DATA_DIR, 'tests.json')
    try:
        with open(tests_path, encoding='utf-8') as f:
            tests_data = json.load(f)
    except Exception:
        tests_data = {'tests': []}

    if not isinstance(tests_data.get('tests'), list):
        tests_data['tests'] = []

    tests_data['tests'].insert(0, test_entry)
    tests_data['tests'] = tests_data['tests'][:_TESTS_MAX_ENTRIES]

    try:
        tmp = tests_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(tests_data, f, indent=2)
        os.replace(tmp, tests_path)
        log.info(f'tests.json updated. Total entries: {len(tests_data["tests"])}')
    except Exception as e:
        log.error(f'tests.json write failed: {e}')


def _write_tests_page() -> None:
    """Render tests.html — the Debug Test Layer page."""
    _TESTS_FETCH_JS = (
        "function _esc(s){\n"
        "  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');\n"
        "}\n"
        "fetch('assets/data/tests.json?v=' + Date.now())\n"
        "  .then(function(r){ return r.json(); })\n"
        "  .then(function(data){\n"
        "    var tests = Array.isArray(data.tests) ? data.tests : [];\n"
        "    var mount = document.getElementById('tests-mount');\n"
        "    if (!tests.length) {\n"
        "      mount.innerHTML = '<div class=\"tst-empty\">No test runs recorded yet. "
        "Trigger a workflow_dispatch run with FORCE_TICKERS set.</div>';\n"
        "      if (window.dismissLoader) window.dismissLoader();\n"
        "      return;\n"
        "    }\n"
        "    var html = '';\n"
        "    tests.forEach(function(t, i){\n"
        "      var ts    = t.timestamp_et || '';\n"
        "      var subs  = Array.isArray(t.active_subs) ? t.active_subs.join(', ') : (t.active_subs || 'all');\n"
        "      var ticks = Array.isArray(t.tickers) ? t.tickers.join(', ') : '';\n"
        "      var log   = t.log || '';\n"
        "      var rtype = t.run_type || 'TEST';\n"
        "      var isSched = (rtype === 'SCHEDULED');\n"
        "      var label = isSched\n"
        "        ? 'SCHEDULED \u2014 ' + (t.slot || 'slot?')\n"
        "        : 'TEST \u2014 ' + (t.active_subs_label || subs);\n"
        "      var badgeHtml = isSched\n"
        "        ? '<span class=\"tst-badge tst-badge-sched\">SCHEDULED</span>'\n"
        "        : '<span class=\"tst-badge\">TEST</span>';\n"
        "      html += '<div class=\"tst-card\">';\n"
        "      html += '<div class=\"tst-hdr\">';\n"
        "      html += badgeHtml;\n"
        "      html += '<span class=\"tst-label\">' + label + '</span>';\n"
        "      html += '<span class=\"tst-ts\">' + ts + ' ET</span>';\n"
        "      html += '</div>';\n"
        "      html += '<div class=\"tst-meta\">';\n"
        "      html += '<span class=\"tst-meta-item\"><span class=\"tst-meta-k\">Tickers</span>' + ticks + '</span>';\n"
        "      html += '<span class=\"tst-meta-item\"><span class=\"tst-meta-k\">Slot</span>' + (t.slot||'—') + '</span>';\n"
        "      html += '</div>';\n"
        "      var logId = 'tst-log-' + i;\n"
        "      html += '<div class=\"tst-log-wrap\">';\n"
        "      html += '<button class=\"tst-copy-btn\" data-log-id=\"' + logId + '\" onclick=\"tstCopy(this)\">&#x2398; Copy Log</button>';\n"
        "      html += '<pre class=\"tst-log\" id=\"' + logId + '\" spellcheck=\"false\">' + _esc(log) + '</pre>';\n"
        "      html += '</div>';\n"
        "      html += '</div>';\n"
        "    });\n"
        "    mount.innerHTML = html;\n"
        "    if (window.dismissLoader) window.dismissLoader();\n"
        "  })\n"
        "  .catch(function(){\n"
        "    document.getElementById('tests-mount').innerHTML ="
        " '<div class=\"tst-empty\" style=\"color:var(--dn);\">Error loading test data.</div>';\n"
        "    if (window.dismissLoader) window.dismissLoader();\n"
        "  });\n"
    )

    _TESTS_STYLES = (
        '<style>\n'
        '.tst-empty{color:var(--mist);font-family:var(--ff-mono);font-size:11px;padding:32px 0;}\n'
        '.tst-card{margin-bottom:2rem;border:1px solid var(--rim);border-radius:4px;'
        'background:rgba(20,20,35,.6);overflow:hidden;}\n'
        '.tst-hdr{display:flex;align-items:center;gap:10px;padding:10px 14px;'
        'background:rgba(155,89,255,.08);border-bottom:1px solid var(--rim);flex-wrap:wrap;}\n'
        '.tst-badge{font-family:var(--ff-mono);font-size:9px;letter-spacing:.15em;'
        'color:#fff5a0;background:rgba(180,150,20,.25);border:1px solid rgba(180,150,20,.5);'
        'padding:2px 6px;border-radius:2px;flex-shrink:0;}\n'
        '.tst-badge-sched{color:#a0e8ff;background:rgba(20,140,180,.25);border:1px solid rgba(20,140,180,.5);}\n'
        '.tst-label{font-family:var(--ff-mono);font-size:11px;color:var(--pu);'
        'letter-spacing:.08em;flex:1;min-width:0;}\n'
        '.tst-ts{font-family:var(--ff-mono);font-size:10px;color:var(--mist);'
        'margin-left:auto;white-space:nowrap;}\n'
        '.tst-meta{display:flex;flex-wrap:wrap;gap:18px;padding:8px 14px;'
        'border-bottom:1px solid var(--rim);background:rgba(0,0,0,.2);}\n'
        '.tst-meta-item{font-family:var(--ff-mono);font-size:10px;color:var(--fg);}\n'
        '.tst-meta-k{color:var(--mist);margin-right:6px;}\n'
        '.tst-log{margin:0;padding:14px;font-family:var(--ff-mono);font-size:11px;'
        'line-height:1.65;color:var(--fg);white-space:pre;overflow-x:auto;'
        'background:rgba(0,0,0,.35);tab-size:2;user-select:text;cursor:text;'
        'border:none;outline:none;max-height:700px;overflow-y:auto;}\n'
        '.tst-log::-webkit-scrollbar{width:6px;height:6px;}\n'
        '.tst-log::-webkit-scrollbar-track{background:transparent;}\n'
        '.tst-log::-webkit-scrollbar-thumb{background:var(--rim);border-radius:3px;}\n'
        '.tst-log-wrap{position:relative;}\n'
        '.tst-copy-btn{'
        'position:absolute;top:8px;right:10px;z-index:2;'
        'font-family:var(--ff-mono);font-size:9px;letter-spacing:.1em;'
        'color:var(--pu);background:rgba(155,89,255,.12);'
        'border:1px solid rgba(155,89,255,.35);border-radius:3px;'
        'padding:3px 9px;cursor:pointer;transition:all .2s;'
        '}\n'
        '.tst-copy-btn:hover{background:rgba(155,89,255,.25);border-color:rgba(155,89,255,.7);color:#fff;}\n'
        '.tst-copy-btn.copied{color:var(--up);border-color:rgba(57,232,160,.5);background:rgba(57,232,160,.1);}\n'
        '</style>\n'
    )

    out = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1.0">'
        '<meta name="description" content="MRE Debug Test Layer">'
        '<title>MRE // Debug Tests</title>'
        f'{_FONTS_LINK}'
        '<link rel="stylesheet" href="assets/style.css">'
        f'{_LOADER_CSS}'
        f'{_TESTS_STYLES}'
        '</head><body>'
        f'{_LOADER_HTML}'
        f'{_LOADER_JS}'
        '<div class="scanlines"></div>'
        f'{_nav_html("tests")}'
        '<div class="pages"><div id="p-tests" class="page on">'
        '<div class="pg-eyebrow">System Validation Log &middot; All Runs</div>'
        '<div class="pg-title">Test <span class="hi">Outputs</span></div>'
        '<div class="pg-sub">All runs &middot; Manual and Scheduled &middot; System validation log &middot; '
        'Clean with <code style="font-family:var(--ff-mono);font-size:10px;">--delete-tests</code></div>'
        '<div id="tests-mount"></div>'
        '</div></div>'
        '<footer><span>MRE</span> &middot; Free-tier data only &middot; Not investment advice</footer>'
        '<script>'
        'function tstCopy(btn){'
        '  var pre=document.getElementById(btn.dataset.logId);'
        '  if(!pre)return;'
        '  var text=pre.textContent||pre.innerText;'
        '  function onCopied(){'
        '    btn.textContent=\'Copied \u2713\';'
        '    btn.classList.add(\'copied\');'
        '    setTimeout(function(){btn.textContent=\'\u2398 Copy Log\';btn.classList.remove(\'copied\');},1800);'
        '  }'
        '  if(navigator.clipboard){'
        '    navigator.clipboard.writeText(text).then(onCopied).catch(function(){'
        '      var ta=document.createElement(\'textarea\');ta.value=text;'
        '      document.body.appendChild(ta);ta.select();document.execCommand(\'copy\');'
        '      document.body.removeChild(ta);onCopied();'
        '    });'
        '  } else {'
        '    var ta=document.createElement(\'textarea\');ta.value=text;'
        '    document.body.appendChild(ta);ta.select();document.execCommand(\'copy\');'
        '    document.body.removeChild(ta);onCopied();'
        '  }'
        '}'
        f'{_TESTS_FETCH_JS}'
        '</script>'
        '</body></html>'
    )

    out_path = os.path.join(DOCS_DIR, 'tests.html')
    try:
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(out)
    except Exception as e:
        log.error(f'tests.html write failed: {e}')


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def build_dashboard(
    companies,
    slot,
    indices,
    breadth,
    regime,
    rotation=None,
    *,
    full_url='',
    prompt_text='',
    is_debug=False,
    active_subs=None,
    index_history=None,
    confirmed_sectors=None,
    market_regime_dict=None,
    portfolio_summary=None,
    paper_trading_summary=None,
):
    """
    Main dashboard builder. Call from main.py after build_intraday_report().

    Parameters
    ----------
    companies    : list of company dicts (standard System 1 output)
    slot         : str — e.g. 'morning', 'midday', 'closing'
    indices      : dict — keys: 'dow', 'sp500', 'nasdaq'; values: {value, change_pct, label}
    breadth      : dict — {label: str}
    regime       : dict — {label: str}
    full_url     : str — GitHub Pages report URL
    prompt_text  : str — AI research prompt for copy button
    is_debug     : bool — if True, routes to tests.json/tests.html only (no rank/archive writes)
    active_subs  : set[str] — subsystems active in this run (test runs only)
    index_history: dict — keys 'dow', 'sp500', 'nasdaq'; values: list[float] (30+ closes)
    confirmed_sectors : dict — sector name → {score, articles:[]} from SectorSignalAccumulator
    """
    index_history     = index_history     or {}
    confirmed_sectors = confirmed_sectors or {}
    active_subs       = active_subs       or set()
    os.makedirs(DATA_DIR, exist_ok=True)
    companies = companies or []

    # ── TEST RUN PATH ───────────────────────────────────────────────────────
    # Test runs skip ALL scheduled data stores (rank, archive, reports index).
    # They write only to tests.json + re-render tests.html.
    if is_debug:
        now_et = datetime.now(pytz.utc).astimezone(pytz.timezone('America/New_York'))
        for _c in companies:
            _c['is_test'] = True
        _subs_label = ', '.join(sorted(active_subs)) if active_subs else 'all'
        try:
            _log_text = _build_test_log(companies, active_subs or set(), slot, paper_trading_summary=paper_trading_summary or {})
        except Exception as _log_err:
            _log_text = f'[log build failed: {_log_err}]'
        test_entry = {
            'is_test':           True,
            'run_type':          'TEST',
            'timestamp_et':      now_et.strftime('%Y-%m-%d %H:%M:%S'),
            'slot':              slot,
            'active_subs':       sorted(active_subs) if active_subs else ['all'],
            'active_subs_label': _subs_label,
            'tickers':           [c.get('ticker', '') for c in companies],
            'log':               _log_text,
        }
        try:
            _write_tests_json(test_entry)
        except Exception as e:
            log.error(f'_write_tests_json error: {e}')
        try:
            _write_tests_page()
            log.info('tests.html written (test run)')
        except Exception as e:
            log.error(f'tests.html write failed: {e}')
        # Update the paper trading frontend even in debug mode so test trades
        # are visible in trades.html immediately after the run.
        try:
            _pt_summary = paper_trading_summary or {}
            write_trades_json(_pt_summary)
            build_trades_page(_pt_summary)
            log.info('trades.html written (test run)')
        except Exception as e:
            log.error(f'trades update failed (test run): {e}')
        log.info(
            f'[DEBUG] build_dashboard complete (test path). '
            f'Subs: {_subs_label} | Tickers: {[c.get("ticker") for c in companies]}'
        )
        return

    # ── SCHEDULED RUN PATH ─────────────────────────────────────────────────

    # ── Write index_history.json ────────────────────────────────────────────
    if index_history:
        try:
            ih_path = os.path.join(DATA_DIR, 'index_history.json')
            tmp     = ih_path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(index_history, f, indent=2)
            os.replace(tmp, ih_path)
        except Exception as e:
            log.warning(f'index_history.json write failed: {e}')

    # ── Update data stores ──────────────────────────────────────────────────
    try:
        _update_reports_index(companies, slot, indices, breadth, regime,
                              full_url, prompt_text,
                              market_regime_dict=market_regime_dict,
                              portfolio_summary=portfolio_summary)
    except Exception as e:
        log.error(f'_update_reports_index error: {e}')

    try:
        _update_rank_board(companies)
    except Exception as e:
        log.error(f'_update_rank_board error: {e}')

    try:
        _update_weekly_archive(companies, slot, breadth, regime,
                               prompt_text, is_debug, full_url,
                               market_regime_dict=market_regime_dict)
    except Exception as e:
        log.error(f'_update_weekly_archive error: {e}')

    # ── Write news data ─────────────────────────────────────────────────────
    try:
        _write_news_json(confirmed_sectors)
    except Exception as e:
        log.error(f'_write_news_json error: {e}')

    # ── Render all pages ────────────────────────────────────────────────────
    try:
        _write_index_page(indices, breadth, regime, index_history,
                          market_regime_dict=market_regime_dict)
        log.info('index.html written')
    except Exception as e:
        log.error(f'index.html write failed: {e}')

    try:
        _write_rank_page()
        log.info('rank.html written')
    except Exception as e:
        log.error(f'rank.html write failed: {e}')

    try:
        _write_archive_page()
        log.info('archive.html written')
    except Exception as e:
        log.error(f'archive.html write failed: {e}')

    try:
        _write_news_page(confirmed_sectors)
        log.info('news.html written')
    except Exception as e:
        log.error(f'news.html write failed: {e}')

    try:
        paper_trading_summary = paper_trading_summary or {}
        write_trades_json(paper_trading_summary)
        build_trades_page(paper_trading_summary)
        log.info('trades.html written')
    except Exception as e:
        log.error(f'trades update failed: {e}')

    log.info('build_dashboard complete')
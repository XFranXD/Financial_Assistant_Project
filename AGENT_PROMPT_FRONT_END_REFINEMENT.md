# MRE AGENT PROMPT v7
# Target: Claude Sonnet 4.6 in Antigravity IDE
# Engine: Python 3.11, Linux Ubuntu, GitHub Actions
# Scope: Rank data pipeline fix + rank render rework +
#        visual fixes

==============================================================
CONSTRAINTS — READ FIRST, NEVER VIOLATE
==============================================================

- Python 3.11 only
- Never use datetime.now() — always datetime.now(pytz.utc)
- Never use print() — always use the logger
- Never use backslash escapes (\u2014, \n, etc.) inside
  f-string {} expressions — use module-level constants
  like _EM instead
- All render functions must be wrapped in try/except
  with defined fallback HTML
- All file writes use encoding='utf-8' and os.replace()
  atomic pattern
- JSON data files: only ADD new fields, never rename
  or remove existing ones
- Do NOT touch: analyzers/, filters/, eq_analyzer/,
  sector_detector/, contracts/, utils/,
  reports/report_builder.py, reports/email_builder.py,
  reports/summary_builder.py
- main.py: targeted additions only, no restructuring
- Do not perform any edits until the target file has
  been read into context in full

==============================================================
SECTION 1 — DATA PIPELINE + RANK RENDER
COMPLETE THIS SECTION FULLY BEFORE TOUCHING SECTION 2.
DO NOT BEGIN SECTION 2 UNTIL ALL SECTION 1 VERIFICATION
STEPS PASS.
==============================================================

--------------------------------------------------------------
BACKGROUND — WHY THE DATA IS MISSING
--------------------------------------------------------------

main.py calls build_intraday_report() then
build_dashboard(), passing the same list to both.
_enrich_company_for_template() runs inside
build_intraday_report() only and does not mutate the
shared list. So _update_rank_board() receives candidates
missing these fields:

  return_1m / return_3m / return_6m
    → live at candidate['mtf']['r1m/r3m/r6m']

  price_history
    → lives at candidate['financials']['price_history']
    NOTE: write it raw. _update_rank_board() calls
    _sanitize_price_history() downstream — do not call
    it in the enrichment block.

  eq_verdict_display, rotation_signal_display,
  market_verdict_display, alignment
    → must be derived as described in Task 1A

--------------------------------------------------------------
TASK 1A — main.py
--------------------------------------------------------------

Read main.py in full before editing.

Apply the enrichment block in TWO locations:

LOCATION 1 — debug/force-ticker path:
  Find: # Build and send report
  followed by: build_intraday_report(companies=all_candidates)
  Insert enrichment block AFTER that call and BEFORE
  the try block containing:
  build_dashboard(companies=all_candidates, is_debug=True)
  List variable: all_candidates

  IDEMPOTENCY GUARD: Before inserting at this location,
  search for the string:
    Pre-dashboard candidate enrichment
  within the debug/force-ticker path block. If it is
  already present, DO NOT insert again. Skip to
  Location 2.

LOCATION 2 — scheduled run path:
  Find: # ── Step 28: Build reports ────
  followed by: build_intraday_report(companies=final_companies)
  Insert enrichment block AFTER that call and BEFORE:
  # ── Step 28b — Dashboard update (non-fatal) ───
  List variable: final_companies

  IDEMPOTENCY GUARD: Before inserting at this location,
  search for the string:
    Pre-dashboard candidate enrichment
  within the scheduled run path block. If it is
  already present, DO NOT insert again.

Enrichment block (replace <LIST> with correct variable):

# ── Pre-dashboard candidate enrichment ───────────────
# Populates display fields so _update_rank_board()
# receives complete data. _enrich_company_for_template()
# does this internally inside build_intraday_report()
# but does not mutate the shared list.
for _c in <LIST>:
    try:
        _mtf = _c.get('mtf') or {}
        _c['return_1m'] = _mtf.get('r1m')
        _c['return_3m'] = _mtf.get('r3m')
        _c['return_6m'] = _mtf.get('r6m')

        _fin = _c.get('financials') or {}
        _c['price_history'] = _fin.get('price_history') or []

        # EQ_AVAILABLE, PASS_TIER, FATAL_FLAW_REASON
        # imported from contracts.eq_schema at top of file
        if not _c.get(EQ_AVAILABLE):
            _eq_vd = 'UNAVAILABLE'
        elif _c.get(FATAL_FLAW_REASON):
            _eq_vd = 'RISKY'
        else:
            _tier = (_c.get(PASS_TIER) or '').strip().upper()
            _eq_vd = {
                'PASS':  'SUPPORTIVE',
                'WATCH': 'NEUTRAL',
                'FAIL':  'WEAK',
            }.get(_tier, 'UNAVAILABLE')
        _c['eq_verdict_display'] = _eq_vd

        # ROTATION_SIGNAL imported from
        # contracts.sector_schema at top of file
        _c['rotation_signal_display'] = (
            (_c.get(ROTATION_SIGNAL) or 'UNKNOWN')
            .strip().upper()
        )

        # Thresholds match summary_verdict() exactly:
        # conf >= 70 AND risk <= 35 → RESEARCH NOW
        # conf >= 55                → WATCH
        # else                      → SKIP
        _conf_v = _c.get('composite_confidence') or 0
        _risk_v = _c.get('risk_score') or 100
        if _conf_v >= 70 and _risk_v <= 35:
            _mvd = 'RESEARCH NOW'
        elif _conf_v >= 55:
            _mvd = 'WATCH'
        else:
            _mvd = 'SKIP'
        _c['market_verdict_display'] = _mvd

        # Alignment — all three source fields are now
        # set above. Use .get() for all access so a
        # partial failure earlier in the try block
        # cannot cause a KeyError here.
        _al = 0
        _mvd_n = (_c.get('market_verdict_display') or '').strip().upper()
        _rot_n = (_c.get('rotation_signal_display') or '').strip().upper()
        _eq_n  = (_c.get('eq_verdict_display') or '').strip().upper()

        if _mvd_n == 'RESEARCH NOW': _al += 1
        elif _mvd_n == 'SKIP':       _al -= 1
        if _rot_n == 'SUPPORT':      _al += 1
        elif _rot_n == 'WEAKEN':     _al -= 1
        if _eq_n == 'SUPPORTIVE':            _al += 1
        elif _eq_n in ('WEAK', 'RISKY'):     _al -= 1

        if _al >= 2:   _c['alignment'] = 'ALIGNED'
        elif _al >= 0: _c['alignment'] = 'PARTIAL'
        else:          _c['alignment'] = 'CONFLICT'

    except Exception as _enrich_err:
        log.warning(
            f'Pre-dashboard enrichment failed for '
            f'{_c.get("ticker", "?")}: {_enrich_err} '
            f'— fields: return_1m/3m/6m price_history '
            f'eq_verdict_display rotation_signal_display '
            f'market_verdict_display alignment'
        )
        _c.setdefault('return_1m', None)
        _c.setdefault('return_3m', None)
        _c.setdefault('return_6m', None)
        _c.setdefault('price_history', [])
        _c.setdefault('eq_verdict_display', 'UNAVAILABLE')
        _c.setdefault('rotation_signal_display', 'UNKNOWN')
        _c.setdefault('market_verdict_display', 'WATCH')
        _c.setdefault('alignment', 'PARTIAL')

--------------------------------------------------------------
TASK 1B — reports/dashboard_builder.py
_update_rank_board()
--------------------------------------------------------------

Read _update_rank_board() in full before editing.

Find the dict assigned to rank_data['stocks'][ticker].
It ends with this exact line:
  'price_history': _sanitize_price_history(raw_ph),

Add ONE new field immediately after that line:
  'alignment':     c.get('alignment', 'PARTIAL'),

Do not rename, remove, or reorder any existing fields.
Do not change anything else in this function.

--------------------------------------------------------------
TASK 1C — reports/dashboard_builder.py
Add _align_cls() helper
--------------------------------------------------------------

Read dashboard_builder.py in full before editing.

Find _rot_cls(). Add this function immediately after
_rot_cls() ends, before whatever follows:

def _align_cls(val: str) -> str:
    v = (val or '').strip().upper()
    if v == 'ALIGNED':  return 'sig-up'
    if v == 'CONFLICT': return 'sig-dn'
    return 'sig-nt'

--------------------------------------------------------------
TASK 1D — reports/dashboard_builder.py
_render_rank_html() — replace exp_stats block
--------------------------------------------------------------

Read _render_rank_html() in full before editing.

SCOPE CONFIRMATION:
The exp_stats block is built inside a for loop over
stocks. The following variables are assigned earlier
in the same loop iteration and are already in scope:
  conf    = stock.get('confidence')
  verdict = stock.get('market_verdict_display') or
            stock.get('market_verdict', '')
Do not redefine them. If for any reason they are not
already assigned above the exp_stats block in the
current loop iteration, add these two lines
immediately before the exp_stats block:
  conf    = stock.get('confidence')
  verdict = (stock.get('market_verdict_display') or
             stock.get('market_verdict', ''))

The following are module-level helpers already defined
in dashboard_builder.py — do not import or redefine:
  _fmt_pct(val), _conf_cls(val), _align_cls(val),
  _esc(val), _EM

ANCHOR UNIQUENESS ASSERTION:
Before making any edit, search the entire file for
this exact string:
  f'<div class="est"><div class="est-k">Opportunity</div>
Count the number of occurrences. If the count is not
exactly 1, STOP. Do not modify the file. Report the
actual count found.

REPLACEMENT INSTRUCTION:
Locate the exp_stats block using the anchor line
confirmed above. Once found, identify the full block:
  — it begins at the nearest preceding line containing:
    f'<div class="exp-stats">'
  — it ends at the closing </div> that satisfies ALL
    of these conditions:
    (a) its leading whitespace characters match exactly
        (string equality, not visual alignment) the
        leading whitespace of the opening
        f'<div class="exp-stats">' line
    (b) it is the last such </div> before the line
        containing f'<div class="exp-chart">'
  Do not include the exp-chart line in the replacement.

Replace that entire block (from exp-stats open div
to its closing </div>, inclusive) with this exact
content, preserving the indentation of the surrounding
code:

                f'<div class="exp-stats">'
                f'<div class="est"><div class="est-k">1M</div><div class="est-v">{_fmt_pct(stock.get("return_1m"))}</div></div>'
                f'<div class="est"><div class="est-k">3M</div><div class="est-v">{_fmt_pct(stock.get("return_3m"))}</div></div>'
                f'<div class="est"><div class="est-k">6M</div><div class="est-v">{_fmt_pct(stock.get("return_6m"))}</div></div>'
                f'<div class="est"><div class="est-k">Verdict</div><div class="est-v {_conf_cls(conf)}">{_esc(verdict) or _EM}</div></div>'
                f'<div class="est"><div class="est-k">Align</div><div class="est-v {_align_cls(stock.get("alignment", ""))}">{_esc(stock.get("alignment", "")) or _EM}</div></div>'
                f'</div>'

Do not touch the exp-chart line or anything after it.
Opportunity and Signal Agree must not appear anywhere
in the new block.

--------------------------------------------------------------
TASK 1E — Verify verdict count logic
--------------------------------------------------------------

Read _update_reports_index() in dashboard_builder.py.
Find the verdict count lines. Confirm they read:
  c.get('market_verdict_display',
        c.get('summary_verdict', ''))
If market_verdict_display is first, no change needed.

--------------------------------------------------------------
SECTION 1 VERIFICATION — ALL MUST PASS
--------------------------------------------------------------

V1:
  python3 -c "import reports.dashboard_builder"
  Must complete with zero errors.

V2:
  python3 -c "import main"
  Must complete with zero errors.

V3:
  python3 -c "
  import json
  with open('docs/assets/data/rank.json') as f:
      d = json.load(f)
  stocks = d.get('stocks', {})
  if not stocks:
      print('WARNING: no stocks in rank.json')
  else:
      first = list(stocks.values())[0]
      required = [
          'alignment', 'eq_verdict_display',
          'rotation_signal_display',
          'market_verdict_display', 'price_history',
          'return_1m', 'return_3m', 'return_6m',
      ]
      missing = [k for k in required if k not in first]
      print('Missing fields:', missing if missing else 'NONE — OK')
      for k in required:
          print(f'  {k}: {repr(first.get(k))}')
      assert isinstance(first.get('price_history'), list), \
          'FAIL: price_history is not a list'
      al = first.get('alignment')
      assert al in ('ALIGNED', 'PARTIAL', 'CONFLICT'), \
          f'FAIL: alignment value unexpected: {al}'
      print('Type and value checks — OK')
  "
  Must print: Missing fields: NONE — OK
  Must print: Type and value checks — OK
  NOTE: return_1m/3m/6m values reflect the last run.
  If engine has not run since this fix they will be
  None — that is expected. Field presence matters here.

V4:
  python3 -c "
  import json
  json.load(open('docs/assets/data/rank.json'))
  print('rank.json valid JSON — OK')
  "

V5:
  grep -n 'Opportunity\|Signal Agree' docs/rank.html
  Must return zero matches.

V6:
  grep -n '_align_cls' reports/dashboard_builder.py
  Must return at least 2 matches (definition + usage).

V7 — Render smoke test:
  python3 -c "
  import sys; sys.path.insert(0, '.')
  from reports.dashboard_builder import _render_rank_html
  mock = {
      'week': '2026-W13',
      'stocks': {
          'TEST': {
              'ticker': 'TEST', 'sector': 'energy',
              'price': 100.0, 'confidence': 65.0,
              'risk_score': 30.0, 'return_1m': 5.0,
              'return_3m': 12.0, 'return_6m': 20.0,
              'eq_verdict_display': 'SUPPORTIVE',
              'rotation_signal_display': 'SUPPORT',
              'market_verdict_display': 'WATCH',
              'alignment': 'ALIGNED',
              'price_history': [99,100,101,102,100],
          }
      }
  }
  html = _render_rank_html(mock)
  assert 'Align' in html, 'FAIL: Align label missing'
  assert 'ALIGNED' in html, 'FAIL: alignment value missing'
  assert 'Opportunity' not in html, 'FAIL: Opportunity still present'
  assert 'Signal Agree' not in html, 'FAIL: Signal Agree still present'
  print('Render smoke test — PASSED')
  "

V8 — Alignment logic unit test:
  python3 -c "
  def align(mvd, rot, eq):
      al = 0
      m = mvd.strip().upper()
      r = rot.strip().upper()
      e = eq.strip().upper()
      if m == 'RESEARCH NOW': al += 1
      elif m == 'SKIP':       al -= 1
      if r == 'SUPPORT':      al += 1
      elif r == 'WEAKEN':     al -= 1
      if e == 'SUPPORTIVE':          al += 1
      elif e in ('WEAK','RISKY'):    al -= 1
      return 'ALIGNED' if al>=2 else 'CONFLICT' if al<0 else 'PARTIAL'
  assert align('RESEARCH NOW','SUPPORT','SUPPORTIVE') == 'ALIGNED'
  assert align('SKIP','WEAKEN','RISKY')               == 'CONFLICT'
  assert align('WATCH','SUPPORT','NEUTRAL')           == 'PARTIAL'
  assert align('research now','support','supportive') == 'ALIGNED'
  print('Alignment logic — PASSED')
  "

==============================================================
SECTION 2 — VISUAL FIXES
DO NOT BEGIN UNTIL ALL SECTION 1 VERIFICATION STEPS PASS.
==============================================================

--------------------------------------------------------------
TASK 2A — AI Prompt button label
reports/dashboard_builder.py
--------------------------------------------------------------

Read dashboard_builder.py in full before editing.

Search for the string: copy-prompt-btn
It appears in TWO render locations.

In BOTH locations find this exact string:
  >&#x2389; AI Prompt</button>

For the index page location (run dict named r):
Replace with:
  >{_esc((r.get("tickers") or [""])[0])} Copy AI Prompt</button>

For the archive page location (run dict named run):
Replace with:
  >{_esc((run.get("tickers") or [""])[0])} Copy AI Prompt</button>

Note: the replacement is inside an f-string. Ensure
the surrounding f-string quotes are preserved.

--------------------------------------------------------------
TASK 2B — Stop propagation on button clicks
reports/dashboard_builder.py
--------------------------------------------------------------

ELEMENT 1 — Full Report anchor (appears TWICE):
Find this exact string in both render locations:
  target="_blank">\u2197 Full Report</a>

Replace with:
  target="_blank" onclick="event.stopPropagation()">\u2197 Full Report</a>

ELEMENT 2 — Copy AI Prompt JS handler:
Search for copy-prompt-btn in the JavaScript section
of dashboard_builder.py (not in the HTML f-strings).
Find the forEach or addEventListener handler for this
class. Confirm whether event.stopPropagation() or
e.stopPropagation() already exists as the first
statement inside the handler body.
If it does NOT exist: add it as the first line inside
the handler body, before any other statement.
If it already exists: do not add it again.

--------------------------------------------------------------
TASK 2C — Index chart direction-based colors
reports/dashboard_builder.py — _build_idx_data()
--------------------------------------------------------------

Read _build_idx_data() in full before editing.

The function begins with:
  def _build_idx_data(index_history: dict,
                      indices: dict) -> dict:
and ends with:
  return result

Replace everything between the function signature
line and the return result line with this exact body
(preserve the docstring if one exists, preserve the
signature, preserve the return statement). After
replacement there must be exactly ONE return result
statement in the function body — verify this before
saving:

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
            'stat3m':   _EM,
            'stat6m':   _EM,
        }
    return result

Then find the Chart.js dataset block in the JS
section. Search for this string:
  backgroundColor:'#1a1430'
Replace ALL occurrences with:
  backgroundColor:d.bg_color

--------------------------------------------------------------
TASK 2D — Index name visibility
reports/dashboard_builder.py
--------------------------------------------------------------

Read _render_index_html() in full before editing.

Find the _pill() inner function. Inside it find
this exact string:
  f'<div class="pill-label">// {label_text}</div>'

Replace with:
  f'<div class="pill-label" style="font-size:13px;color:var(--star);font-family:var(--ff-mono);letter-spacing:0.04em;">// {label_text}</div>'

--------------------------------------------------------------
TASK 2E — Small label visibility
docs/assets/style.css and reports/dashboard_builder.py
--------------------------------------------------------------

CATEGORY 1 — est-k labels (1M, 3M, 6M, Verdict, Align):
  Open docs/assets/style.css.
  Before appending, read the last line of the file.
  If the last line does not end with a newline
  character, add one before appending.
  Then append these lines at the very end of the file,
  after all existing rules. Do not search for or
  modify any existing .est-k rule:

  .est-k {
      font-size: 11px;
      color: var(--fog);
  }

CATEGORY 2 — Breadth and Market small labels:
  In _render_index_html() in dashboard_builder.py,
  find where the text labels 'Breadth' and 'Market'
  are rendered as small display elements.
  Add or update their inline style to include:
  font-size:11px;color:var(--fog);

CATEGORY 3 — Report card regime and top_score text:
  In the rcard render section of _render_index_html(),
  find where r.get('regime') is rendered as secondary
  text and where top_score appears as 'Top conf: X/100'.
  Add or update their inline style to include:
  font-size:11px;color:var(--fog);

Use only existing CSS variables. No new colors.
No new CSS classes.

--------------------------------------------------------------
SECTION 2 VERIFICATION
--------------------------------------------------------------

V9:
  python3 -c "import reports.dashboard_builder"
  Must complete with zero errors.

V10:
  grep -n 'stopPropagation' reports/dashboard_builder.py
  Must return at least 2 matches.

V11:
  grep -n 'Copy AI Prompt' reports/dashboard_builder.py
  Must return matches showing ticker prefix.

V12:
  grep -n '39e8a0\|ff4d6d\|ff9a3c' \
  reports/dashboard_builder.py
  Must return matches inside _build_idx_data().

V13:
  grep -n 'bg_color' reports/dashboard_builder.py
  Must return matches in both _build_idx_data()
  and the JS dataset block.

V14:
  python3 -c "
  import json
  json.load(open('docs/assets/data/rank.json'))
  print('rank.json still valid — OK')
  "

==============================================================
# MRE DELTA PROMPT — visual fixes
# Target: Claude Sonnet 4.6 in Antigravity IDE
# Engine: Python 3.11, Linux Ubuntu, GitHub Actions
# Scope: Two targeted fixes only

==============================================================
CONSTRAINTS — READ FIRST, NEVER VIOLATE
==============================================================

- Do not perform any edits until the target file has
  been read into context in full
- Do not touch any file not explicitly named below
- Do not rename or remove any existing CSS rules
  other than the one explicitly identified below
- All file writes use encoding='utf-8' and os.replace()
  atomic pattern

==============================================================
TASK 1 — Fix duplicate .est-k rule in style.css
==============================================================

Read docs/assets/style.css in full before editing.

There are currently TWO .est-k rules in the file:

RULE A — line ~574 (original):
  .est-k { font-size: 8px; letter-spacing: 0.16em;
    text-transform: uppercase; color: var(--mist);
    margin-bottom: 5px; }

RULE B — appended at the end of the file:
  .est-k {
      font-size: 11px;
      color: var(--mist);
  }

ACTION:
Delete Rule B entirely (the appended block at the end).
Then replace Rule A with this exact single-line rule:
  .est-k { font-size: 11px; letter-spacing: 0.16em; text-transform: uppercase; color: var(--mist); margin-bottom: 5px; }

Result: exactly ONE .est-k rule in the file, with
font-size raised to 11px and all other properties
from the original preserved.

VERIFICATION:
  grep -c 'est-k' docs/assets/style.css
  Must return exactly 1.

  grep 'est-k' docs/assets/style.css
  Must show font-size:11px and letter-spacing and
  text-transform and margin-bottom all present.

==============================================================
TASK 2 — Restore copy symbol on AI Prompt button
==============================================================

Read reports/dashboard_builder.py in full before editing.

Search for the string: Copy AI Prompt
It appears in TWO locations (index page and archive page).

In BOTH locations find this pattern:
  copy-prompt-btn" data-ref="{uid}">{_esc(...)} Copy AI Prompt</button>

The text before "Copy AI Prompt" is the ticker prefix
added in the previous agent run. Keep it exactly as is.

Insert the symbol ⧉ and a space between the ticker
and the word Copy, so the result reads:
  {ticker} ⧉ Copy AI Prompt

Exact replacement — for the index page location
(run dict named r):
  Find:
    {_esc((r.get("tickers") or [""])[0])} Copy AI Prompt</button>
  Replace with:
    {_esc((r.get("tickers") or [""])[0])} ⧉ Copy AI Prompt</button>

Exact replacement — for the archive page location
(run dict named run):
  Find:
    {_esc((run.get("tickers") or [""])[0])} Copy AI Prompt</button>
  Replace with:
    {_esc((run.get("tickers") or [""])[0])} ⧉ Copy AI Prompt</button>

Note: these replacements are inside f-strings. Ensure
the surrounding f-string quotes are preserved.
Do not touch any other part of the button definition.

VERIFICATION:
  grep -n 'Copy AI Prompt' reports/dashboard_builder.py
  Must return exactly 2 matches, both containing ⧉.

==============================================================
FINAL VERIFICATION
==============================================================

V1:
  python3 -c "import reports.dashboard_builder"
  Must complete with zero errors.

V2:
  grep -c 'est-k' docs/assets/style.css
  Must return 1.

V3:
  grep -n '⧉' reports/dashboard_builder.py
  Must return 2 matches.

==============================================================
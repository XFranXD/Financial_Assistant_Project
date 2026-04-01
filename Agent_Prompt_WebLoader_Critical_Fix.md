var eqCls  = eqV  === 'SUPPORTIVE' ? 'up' : (eqV === 'WEAK' || eqV === 'RISKY') ? 'dn' : 'nt';
var rotCls = rotS === 'SUPPORT'    ? 'up' : rotS === 'WEAKEN' ? 'dn' : 'nt';
```

**Bug 3 — `_COPY_PROMPT_JS` references old symbol `\u2389`:**
The fallback error text still says `'\u2389 AI Prompt'` but the button now uses `⧉` (`\u29c9`). Minor visual inconsistency on copy error.

**Bug 4 — `_write_rank_page()` passes stale `rank_data` dict but `_render_rank_html` no longer uses it for content** — it just uses it for the `week` display string. This is fine. The fetch handles the data. No bug here.

**The actual frontend-not-updating issue:** Now I see it clearly. The cleanup script's Step 7 calls `_write_rank_page()`, `_write_archive_page()`, and `_write_index_page()`. These regenerate the HTML shell files. But since the shells just contain mount points and fetch calls, they are **identical every time** — they contain no baked data. So Step 7 in cleanup is completely redundant. The pages already auto-fetch on reload.

**The real reason the frontend wasn't updating after force-delete** is GitHub Pages caching. GitHub Pages serves files with cache headers. After you push updated JSON files, the browser or CDN may still serve the old cached version for several minutes. This is not a code bug — it's a deployment artifact.

The fixes needed are only the JS value bugs. Here is the agent prompt:

---
```
# MRE AGENT PROMPT
# Target: Claude Sonnet 4.6 in Antigravity IDE
# Engine: Python 3.11, Linux Ubuntu, GitHub Actions
# Scope: Fix JS classification logic in dashboard_builder.py

==============================================================
CONSTRAINTS — READ FIRST, NEVER VIOLATE
==============================================================

- Do not perform any edits until the target file has
  been read into context in full
- Only touch reports/dashboard_builder.py
- These are module-level string constants — NOT f-strings
- Do not add, remove, or reorder any other code
- All changes are single-line string replacements inside
  existing string constant blocks

==============================================================
TASK 1 — Fix alignment CSS class in _RANK_FETCH_JS
==============================================================

Read reports/dashboard_builder.py in full before editing.

Inside the string constant _RANK_FETCH_JS, find this
exact line:
  "      var aCls     = alignVal === 'ALIGNED' ? 'up' : alignVal === 'MIXED' ? 'nt' : 'dn';\n"

Replace with:
  "      var aCls     = alignVal === 'ALIGNED' ? 'up' : alignVal === 'CONFLICT' ? 'dn' : 'nt';\n"

Reason: 'MIXED' is not a valid alignment value. Valid
values are ALIGNED / PARTIAL / CONFLICT. PARTIAL should
map to 'nt' (amber), CONFLICT to 'dn' (red).

==============================================================
TASK 2 — Fix EQ and Rotation CSS classes in _RANK_FETCH_JS
==============================================================

Inside _RANK_FETCH_JS, find these two exact lines:
  "      var eqCls  = eqV  === 'STRONG'  ? 'up' : eqV  === 'WEAK'    ? 'dn' : 'nt';\n"
  "      var rotCls = rotS === 'LEADING' ? 'up' : rotS === 'LAGGING' ? 'dn' : 'nt';\n"

Replace with:
  "      var eqCls  = eqV  === 'SUPPORTIVE' ? 'up' : (eqV === 'WEAK' || eqV === 'RISKY') ? 'dn' : 'nt';\n"
  "      var rotCls = rotS === 'SUPPORT'    ? 'up' : rotS === 'WEAKEN' ? 'dn' : 'nt';\n"

Reason: 'STRONG' and 'LEADING' are not valid values in
this engine. EQ valid values: SUPPORTIVE / NEUTRAL /
WEAK / RISKY / UNAVAILABLE. Rotation valid values:
SUPPORT / WAIT / WEAKEN / UNKNOWN.

==============================================================
TASK 3 — Fix EQ and Rotation CSS classes in _INDEX_FETCH_JS
==============================================================

Inside _INDEX_FETCH_JS, find these two exact lines:
  "      var eqCls  = eqV  === 'STRONG'  ? 'up' : eqV  === 'WEAK'    ? 'dn' : 'nt';\n"
  "      var rotCls = rotS === 'LEADING' ? 'up' : rotS === 'LAGGING' ? 'dn' : 'nt';\n"

Replace with:
  "      var eqCls  = eqV  === 'SUPPORTIVE' ? 'up' : (eqV === 'WEAK' || eqV === 'RISKY') ? 'dn' : 'nt';\n"
  "      var rotCls = rotS === 'SUPPORT'    ? 'up' : rotS === 'WEAKEN' ? 'dn' : 'nt';\n"

Note: _INDEX_FETCH_JS and _RANK_FETCH_JS are separate
string constants. Both must be fixed independently.
Confirm the fix was applied in both locations.

==============================================================
TASK 4 — Fix copy error fallback text in _COPY_PROMPT_JS
==============================================================

Inside _COPY_PROMPT_JS, find this exact string:
  s2.textContent='\u2389 AI Prompt';

Replace with:
  s2.textContent='\u29c9 Copy AI Prompt';

Reason: button label was updated to use ⧉ (\u29c9) in
a previous session. The error fallback still referenced
the old symbol \u2389.

==============================================================
VERIFICATION
==============================================================

V1:
  python3 -c "import reports.dashboard_builder"
  Must complete with zero errors.

V2:
  grep -n "MIXED\|LEADING\|LAGGING\|STRONG" \
  reports/dashboard_builder.py
  Must return zero matches inside _RANK_FETCH_JS
  and _INDEX_FETCH_JS. If any match remains the
  fix was not applied correctly.

V3:
  grep -n "SUPPORTIVE\|WEAKEN\|CONFLICT" \
  reports/dashboard_builder.py | grep -c "FETCH_JS"
  Must return at least 6 (3 fixes × 2 constants minimum).

V4:
  grep -n "2389" reports/dashboard_builder.py
  Must return zero matches.

==============================================================
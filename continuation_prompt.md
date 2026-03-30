# MRE FRONTEND UPDATE — CONTINUATION PROMPT
# Previous agent stopped after completing Tasks 1–7 and 10–13.
# This prompt covers the two remaining tasks only.
# Read everything before touching any file.

---

## WHAT HAS ALREADY BEEN DONE — DO NOT REDO

The following is complete and must not be touched:

- `docs/assets/style.css` — full new design system
- `reports/dashboard_builder.py` — fully rewritten: `_nav_html()`, `_render_index_html()`, `_render_rank_html()`, `_render_archive_html()`, `_write_news_page()`, `_write_news_json()`, `build_dashboard()` wiring, all module-level JS constants, all helper functions
- `docs/guide.html` — rewritten static file
- `collectors/news_collector.py` — `SectorSignalAccumulator` extended
- `collectors/market_collector.py` — `get_index_history()` added
- `financial_parser.py` — `price_history` fetch added
- `main.py` — two additions already wired

---

## WHAT REMAINS — ONLY THESE TWO TASKS

### TASK 8 — Update Jinja2 full report templates

Files to update:
- `reports/templates/intraday_full.html`
- `reports/templates/closing_full.html`

**Scope: color palette and fonts only. Zero layout changes. Zero structural changes. Zero JS additions.**

Both files currently use old colors (`#0a0a0f`, `#0f0f1a`, `#e8e8f0`, `#8888aa`, `#00ff88`, `#ff3355`, `#ffcc00`, `#00aaff`, `#aa55ff`, `#444466`) and old font (`Courier New`). Confirm by reading each file before editing.

Make exactly these changes and nothing else:

1. Add Google Fonts `<link>` in `<head>` before the closing `</head>` tag:
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=Share+Tech+Mono&display=swap" rel="stylesheet">
```

2. Add the CSS variables `:root` block at the very top of the existing inline `<style>` block (before any existing rules):
```css
:root {
  --void:    #0a0610;
  --l1:      #130f22;
  --l2:      #1a1430;
  --l3:      #221a3e;
  --l4:      #2c224e;
  --pu:      #9b59ff;
  --pu-lt:   #c084ff;
  --pu-dk:   #5e2ba8;
  --mg:      #ff6eb4;
  --sun:     #ff9a3c;
  --cyan:    #00e5ff;
  --up:      #39e8a0;
  --dn:      #ff4d6d;
  --nt:      #ff9a3c;
  --snow:    #f0eaff;
  --slate:   #8878b8;
  --mist:    #4a3d72;
  --ghost:   #2a2248;
  --rim:     rgba(155,89,255,0.12);
  --rim2:    rgba(155,89,255,0.25);
  --ff-head: 'Orbitron', sans-serif;
  --ff-mono: 'Share Tech Mono', monospace;
}
```

3. Replace font family declaration. Find any occurrence of:
- `'Courier New', Courier, monospace`
- `'JetBrains Mono', 'Fira Code', 'Courier New', monospace`
- `monospace` (standalone in font-family rules)

Replace all with: `var(--ff-mono)`

4. Replace all old color hex values with their CSS variable equivalents:
- `#0a0a0f` → `var(--void)`
- `#0f0f1a` → `var(--l1)`
- `#141428` → `var(--l2)`
- `#1a1a35` → `var(--l3)`
- `#e8e8f0` → `var(--snow)`
- `#8888aa` → `var(--slate)`
- `#444466` → `var(--mist)`
- `#00ff88` → `var(--up)`
- `#ff3355` → `var(--dn)`
- `#ffcc00` → `var(--nt)`
- `#00aaff` → `var(--cyan)`
- `#aa55ff` → `var(--pu)`
- `#ffffff` (white text) → `var(--snow)`
- `#1e1e3a` (border color) → `var(--rim)`

**DO NOT change:**
- Any HTML structure
- Any Jinja2 template variables: `{{ variable }}`, `{% for %}`, `{% if %}`, `{% endif %}`, `{% endfor %}`
- Any class names
- Any layout, padding, margin, grid, or flexbox rules
- Any color values that appear inside Jinja2 expressions or Python-injected inline styles — leave those untouched

---

### TASK 9 — Update Jinja2 email templates

Files to update:
- `reports/templates/intraday_email.html`
- `reports/templates/closing_email.html`

**Scope: color hex values only, replaced inline. No CSS variables. No Google Fonts. No JS. No layout changes.**

Email clients do not support CSS custom properties or external fonts. All replacements must use literal hex values — no `var(--X)` references.

Make exactly these changes and nothing else:

1. Replace all old color hex values with new hex values directly:
- `#0a0a0f` → `#0a0610`
- `#0f0f1a` → `#130f22`
- `#141428` → `#1a1430`
- `#1a1a35` → `#221a3e`
- `#1e1e3a` (borders) → `#2c224e`
- `#e8e8f0` → `#f0eaff`
- `#8888aa` → `#8878b8`
- `#444466` → `#4a3d72`
- `#00ff88` → `#39e8a0`
- `#ff3355` → `#ff4d6d`
- `#ffcc00` → `#ff9a3c`
- `#00aaff` → `#00e5ff`
- `#aa55ff` → `#9b59ff`
- `#ffffff` (white text) → `#f0eaff`

**DO NOT:**
- Add any `<link>` tags
- Add any `<script>` tags
- Add any CSS variable references (`var(--X)`)
- Change any HTML structure
- Change any Jinja2 template variables
- Change any layout or structural CSS rules

---

## MINOR CLEANUP — OPTIONAL BUT RECOMMENDED

In `reports/dashboard_builder.py`, around line 1170, there is a dead code variable in `_render_rank_html()`:

```python
js_block = f'<script>{_DAYS_JS}{_EXP_T_JS}{_RAF_COLLAPSE_JS}</script>{_CHARTJS}<script>{_COPY_PROMPT_JS}</script>'
```

This variable is defined but never used — the return statement already inlines the scripts directly. It does not break anything. If you have time after Tasks 8 and 9, remove this line. If not, leave it.

---

## HARD CONSTRAINTS — SAME AS BEFORE

- Never use `print()` — always use the logger
- Never use `datetime.now()` — always `datetime.now(pytz.utc)`
- Do not touch any file not listed in this prompt
- Do not touch `main.py`, `dashboard_builder.py`, or any already-completed file

---

## VERIFICATION AFTER COMPLETING

After updating all four template files, confirm:

- [ ] `intraday_full.html` contains `var(--void)`, `var(--snow)`, `Share Tech Mono`, Google Fonts `<link>`, and `:root` block
- [ ] `closing_full.html` contains the same
- [ ] `intraday_email.html` contains `#0a0610`, `#f0eaff`, `#39e8a0` and NO `var(--X)` references
- [ ] `closing_email.html` contains the same
- [ ] No Jinja2 variables (`{{ }}` or `{% %}`) were modified in any file
- [ ] No HTML structure changed in any file

---

## WHEN DONE

The frontend update is complete. No further tasks remain.

If quota runs out mid-task, write at the bottom of the last file edited:
```
<!-- AGENT STOP — completed Task N mid-way -->
<!-- Last file: filename -->
<!-- Remaining: what still needs to be done -->
```

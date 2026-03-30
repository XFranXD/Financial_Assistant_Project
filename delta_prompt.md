# MRE FRONTEND UPDATE — DELTA PROMPT
# Three targeted fixes only. Read everything before touching any file.
# Do not touch any file not explicitly listed below.

---

## CONTEXT

The frontend update is otherwise complete. This prompt covers three remaining
issues only:

1. Email templates still use `Courier New` font family
2. `build_dashboard()` is missing the `rotation` parameter from the v6.2 spec
3. Dead `js_block` variable in `_render_rank_html()`

---

## FIX 1 — Email template font family

Files: `reports/templates/intraday_email.html` and `reports/templates/closing_email.html`

Email clients do not load Google Fonts. Do not add any `<link>` tags.
Replace the font family declarations with a safe fallback stack that
de-prioritises Courier New in favour of Share Tech Mono first.

**In `reports/templates/intraday_email.html`:**

Line 12: replace
```
font-family: 'Courier New', Courier, monospace;
```
with
```
font-family: 'Share Tech Mono', 'Courier New', monospace;
```

Line 63: replace
```
font-family: 'Courier New', Courier, monospace;
```
with
```
font-family: 'Share Tech Mono', 'Courier New', monospace;
```

Line 455 contains `font-family:monospace` inline — leave it unchanged.

**In `reports/templates/closing_email.html`:**

Line 8: replace
```
font-family:'Courier New',Courier,monospace;
```
with
```
font-family:'Share Tech Mono','Courier New',monospace;
```

Line 19: replace
```
font-family:'Courier New',Courier,monospace;
```
with
```
font-family:'Share Tech Mono','Courier New',monospace;
```

Do not change anything else in either file — no colors, no structure,
no Jinja2 variables, no other CSS rules.

---

## FIX 2 — Restore `rotation` parameter to `build_dashboard()`

File: `reports/dashboard_builder.py`

The v6.2 spec defines `rotation: dict` as a positional parameter in
`build_dashboard()`. The agent dropped it during implementation. Restore it.

Find `def build_dashboard(` at line 1375. The current signature is:

```python
def build_dashboard(
    companies,
    slot,
    indices,
    breadth,
    regime,
    *,
    full_url='',
    prompt_text='',
    is_debug=False,
    index_history=None,
    confirmed_sectors=None,
):
```

Replace with:

```python
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
    index_history=None,
    confirmed_sectors=None,
):
```

`rotation` is added as a positional parameter with default `None` placed
after `regime` and before the `*` separator, exactly matching the v6.2 spec
order. The call sites in `main.py` currently do not pass `rotation` so the
default `None` keeps them fully compatible — do not touch `main.py`.

Do not add any logic that uses `rotation` inside `build_dashboard()`.
It is accepted for spec compliance and future use only.

---

## FIX 3 — Remove dead `js_block` variable in `_render_rank_html()`

File: `reports/dashboard_builder.py`

Around line 1170, inside `_render_rank_html()`, there is a variable that is
defined but never used. The return statement already inlines the scripts
directly. Remove this single line:

```python
js_block = f'<script>{_DAYS_JS}{_EXP_T_JS}{_RAF_COLLAPSE_JS}</script>{_CHARTJS}<script>{_COPY_PROMPT_JS}</script>'
```

Do not change anything else in the function.

---

## VERIFICATION

After making all three changes, confirm:

- [ ] `intraday_email.html` lines 12 and 63 use `'Share Tech Mono', 'Courier New', monospace`
- [ ] `closing_email.html` lines 8 and 19 use `'Share Tech Mono','Courier New',monospace`
- [ ] No `<link>` tags added to either email template
- [ ] No colors changed in either email template
- [ ] No Jinja2 variables touched in either email template
- [ ] `build_dashboard()` signature includes `rotation=None` between `regime` and `*`
- [ ] `main.py` is unchanged
- [ ] Dead `js_block` line removed from `_render_rank_html()`
- [ ] No other lines changed in `dashboard_builder.py`

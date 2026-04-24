# Portal design system

This document defines the visual language for every portal and admin page. **Colors are not changed** — the existing palette is preserved and assigned to roles. Tokens are CSS custom properties declared once in `static/css/portal/tokens.css` and consumed everywhere.

---

## 1. Color roles (existing palette, redistributed)

```css
/* static/css/portal/tokens.css */
:root {
  /* Brand — used for topbar gradient, active nav, hero accents */
  --brand-blue:        #3D7EAA;
  --brand-blue-dark:   #275d81;  /* borders / hover / focus ring */
  --brand-yellow:      #FFE47A;  /* primary action bg, accent highlight */
  --brand-yellow-alt:  #FFE47E;  /* button hover, subtle accent */
  --brand-blue-bright: #1E90FF;  /* link hover, focus glow */

  /* Surfaces */
  --surface-page:      #F5F7FA;  /* NEW ROLE for existing #fff siblings */
  --surface-card:      #FFFFFF;
  --surface-muted:     #EEF2F7;

  /* Text */
  --text-primary:      #111827;
  --text-secondary:    #6B7280;
  --text-on-brand:     #FFFFFF;
  --text-on-accent:    #111827;  /* black on yellow buttons — existing choice */

  /* Semantic (bootstrap-aligned neutrals; introduce only if missing) */
  --state-success:     #1F9D55;
  --state-warning:     #D97706;
  --state-danger:      #DC2626;
  --state-info:        var(--brand-blue);

  /* Borders & dividers */
  --border-default:    #E5E7EB;
  --border-strong:     #D1D5DB;
  --border-brand:      var(--brand-blue-dark);
}
```

**Rule**: no hex literal outside `tokens.css`. If a new role is needed, add a token — don't sprinkle.

---

## 2. Spacing scale

Single 4 px unit. Use these only:

| Token | Value | Typical use |
| --- | --- | --- |
| `--space-1` | 4 px  | tight icon padding |
| `--space-2` | 8 px  | label to input |
| `--space-3` | 12 px | inline form-group |
| `--space-4` | 16 px | card inner gutter, row gap |
| `--space-5` | 24 px | section gap inside a card |
| `--space-6` | 32 px | gap between cards |
| `--space-7` | 48 px | page section gap |
| `--space-8` | 64 px | hero / empty-state vertical |

```css
:root {
  --space-1: 0.25rem;  --space-2: 0.5rem;  --space-3: 0.75rem;
  --space-4: 1rem;     --space-5: 1.5rem;  --space-6: 2rem;
  --space-7: 3rem;     --space-8: 4rem;
}
```

Bootstrap's `p-*` / `m-*` already emit similar spacing; treat these tokens as the canonical list and prefer them in new CSS.

---

## 3. Typography scale

```css
:root {
  --font-sans: "Inter", "Segoe UI", Arial, sans-serif;   /* Inter via Google Fonts, Arial fallback */
  --font-mono: "JetBrains Mono", Menlo, monospace;

  --text-xs:  0.75rem;   /* 12 — badges, captions */
  --text-sm:  0.875rem;  /* 14 — secondary copy, table cells */
  --text-base: 1rem;     /* 16 — body */
  --text-lg:  1.125rem;  /* 18 — card titles */
  --text-xl:  1.25rem;   /* 20 — section titles */
  --text-2xl: 1.5rem;    /* 24 — page h1 inside card */
  --text-3xl: 1.875rem;  /* 30 — page h1 hero */
  --text-4xl: 2.25rem;   /* 36 — brand moments */

  --leading-tight: 1.2;
  --leading-normal: 1.5;

  --weight-regular: 400;
  --weight-medium:  500;
  --weight-semibold: 600;
  --weight-bold: 700;
}

h1 { font-size: var(--text-3xl); font-weight: var(--weight-bold);     line-height: var(--leading-tight); }
h2 { font-size: var(--text-2xl); font-weight: var(--weight-semibold); line-height: var(--leading-tight); }
h3 { font-size: var(--text-xl);  font-weight: var(--weight-semibold); line-height: var(--leading-tight); }
h4 { font-size: var(--text-lg);  font-weight: var(--weight-semibold); line-height: var(--leading-normal); }
p, li, td { font-size: var(--text-base); line-height: var(--leading-normal); color: var(--text-primary); }
small, .small { font-size: var(--text-sm); color: var(--text-secondary); }
code { font-family: var(--font-mono); font-size: var(--text-sm); }
```

Existing `font-family: Arial, sans-serif` stays as the fallback chain — Inter layers on top. If Google Fonts is undesirable, drop the `"Inter"` token and the scale still works with Arial.

---

## 4. Shell layout

Both portal and admin use the same shell. One CSS file (`portal_layout.css` rewritten) powers both.

```
┌────────────────────────────────────────────────────────────────┐
│ TOPBAR 64px                                                     │ fixed
├────────┬───────────────────────────────────────────────────────┤
│        │ BREADCRUMB / SECTION TITLE BAR 48px                    │
│ SIDE   ├───────────────────────────────────────────────────────┤
│ NAV    │                                                        │
│ 240px  │                                                        │
│ fixed  │  CONTENT  max-width 1280px, centered                   │
│        │  padding: var(--space-6)                               │
│        │                                                        │
└────────┴───────────────────────────────────────────────────────┘
```

CSS (abridged):

```css
.app-shell { min-height: 100vh; background: var(--surface-page); }

.topbar {
  position: fixed; top: 0; left: 0; right: 0; height: 64px;
  background: linear-gradient(to right, var(--brand-blue), var(--brand-yellow));
  display: flex; align-items: center; padding: 0 var(--space-5);
  z-index: 1000;
}

.sidebar {
  position: fixed; top: 64px; left: 0; bottom: 0; width: 240px;
  background: var(--surface-card); border-right: 1px solid var(--border-default);
  padding: var(--space-4) var(--space-3); overflow-y: auto;
}

.content {
  margin-left: 240px; padding-top: 64px;
}

.content__inner {
  max-width: 1280px; margin: 0 auto;
  padding: var(--space-6);
}

@media (max-width: 768px) {
  .sidebar { transform: translateX(-100%); transition: transform .2s; }
  .sidebar.open { transform: translateX(0); }
  .content { margin-left: 0; }
}
```

---

## 5. Cards

```css
.card-ui {
  background: var(--surface-card);
  border: 1px solid var(--border-default);
  border-radius: 12px;
  box-shadow: 0 1px 2px rgba(17, 24, 39, 0.04);
}
.card-ui__header {
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-default);
  display: flex; align-items: center; justify-content: space-between;
}
.card-ui__body    { padding: var(--space-5); }
.card-ui__footer  { padding: var(--space-4) var(--space-5); border-top: 1px solid var(--border-default); }
```

Keep Bootstrap's `.card` available as a fallback, but new templates use `.card-ui` so the tokenised styles apply.

---

## 6. Buttons

Existing choice: primary button is yellow with black text. Preserved.

```css
.btn-ui {
  display: inline-flex; align-items: center; gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  border-radius: 8px; border: 1px solid transparent;
  font-weight: var(--weight-semibold); font-size: var(--text-sm);
  transition: transform .08s, box-shadow .15s, background .15s;
  cursor: pointer;
}
.btn-ui:focus-visible {
  outline: 2px solid var(--brand-blue-dark);
  outline-offset: 2px;
}
.btn-ui[disabled] { opacity: .55; cursor: not-allowed; }

.btn-ui--primary {
  background: var(--brand-yellow);
  color: var(--text-on-accent);
}
.btn-ui--primary:hover { background: var(--brand-yellow-alt); }

.btn-ui--secondary {
  background: var(--surface-card);
  color: var(--brand-blue-dark);
  border-color: var(--border-strong);
}
.btn-ui--secondary:hover { background: var(--surface-muted); }

.btn-ui--ghost {
  background: transparent; color: var(--brand-blue-dark);
}
.btn-ui--ghost:hover { background: var(--surface-muted); }

.btn-ui--danger {
  background: var(--state-danger); color: #fff;
}
.btn-ui--danger:hover { filter: brightness(.95); }

.btn-ui--sm  { padding: var(--space-1) var(--space-3); font-size: var(--text-xs); }
.btn-ui--lg  { padding: var(--space-3) var(--space-5); font-size: var(--text-base); }
.btn-ui--icon-only { padding: var(--space-2); }
```

---

## 7. Forms

```css
.field        { display: flex; flex-direction: column; gap: var(--space-2); }
.field-label  { font-size: var(--text-sm); font-weight: var(--weight-medium); color: var(--text-primary); }
.field-input  {
  height: 40px; padding: 0 var(--space-3);
  border: 1px solid var(--border-strong); border-radius: 8px;
  background: var(--surface-card); color: var(--text-primary);
  font-size: var(--text-base);
}
.field-input:focus-visible {
  outline: 2px solid var(--brand-blue-dark); outline-offset: 1px;
  border-color: var(--brand-blue-dark);
}
.field-hint   { font-size: var(--text-xs); color: var(--text-secondary); }
.field-error  { font-size: var(--text-xs); color: var(--state-danger); }

textarea.field-input { min-height: 96px; padding: var(--space-3); resize: vertical; }

.field--inline     { flex-direction: row; align-items: center; gap: var(--space-3); }
.field--horizontal { display: grid; grid-template-columns: 200px 1fr; align-items: center; gap: var(--space-4); }
```

Django forms: use a small `{% include 'portal/components/_field.html' with field=form.email %}` partial — definition in `components/components.md`.

---

## 8. Tables

```css
.table-ui          { width: 100%; border-collapse: collapse; background: var(--surface-card); }
.table-ui thead th {
  text-align: left; font-size: var(--text-xs); font-weight: var(--weight-semibold);
  text-transform: uppercase; letter-spacing: .04em; color: var(--text-secondary);
  padding: var(--space-3) var(--space-4); border-bottom: 1px solid var(--border-default);
  background: var(--surface-muted);
}
.table-ui tbody td {
  padding: var(--space-4); border-bottom: 1px solid var(--border-default);
  font-size: var(--text-sm); color: var(--text-primary); vertical-align: middle;
}
.table-ui tbody tr:hover { background: var(--surface-muted); }

.table-ui tbody tr.is-clickable { cursor: pointer; }

.table-ui__row-link { display: contents; color: inherit; text-decoration: none; }
```

For clickable rows, wrap the first cell's content in an `<a>`; the whole row becomes keyboard-navigable because tab-focus lands on the `<a>`. No `onclick=window.location`.

---

## 9. Badges / pills

```css
.badge-ui {
  display: inline-flex; align-items: center; gap: var(--space-1);
  padding: 2px var(--space-2); border-radius: 999px;
  font-size: var(--text-xs); font-weight: var(--weight-semibold);
  line-height: 1.4; letter-spacing: .02em;
}
.badge-ui--info    { background: #E0F2FE; color: #075985; }
.badge-ui--primary { background: #DBEAFE; color: #1E40AF; }
.badge-ui--success { background: #DCFCE7; color: #166534; }
.badge-ui--warning { background: #FEF3C7; color: #92400E; }
.badge-ui--danger  { background: #FEE2E2; color: #991B1B; }
.badge-ui--muted   { background: var(--surface-muted); color: var(--text-secondary); }
.badge-ui--accent  { background: var(--brand-yellow); color: var(--text-on-accent); }
```

State → badge mapping (used across Tournament / Match / Invite):

| State | Variant | Label |
| --- | --- | --- |
| `created` | `info` | Upcoming |
| `inprogress` | `primary` | In Progress |
| `completed` | `success` | Completed |
| `aborted` | `danger` | Aborted |
| `sent` | `muted` | Invite sent |
| `accepted` | `success` | Accepted |
| `declined` | `danger` | Declined |
| `expired` | `warning` | Expired |

Mapping lives in a template filter `state_badge` (see `components/components.md`).

---

## 10. Icons

Use a single icon set. Existing templates mix **Font Awesome** and **Bootstrap Icons** — pick Bootstrap Icons because the portal already loads that CSS (`base_portal.html:25`) and it has better SaaS-neutral coverage. Drop Font Awesome from `base_portal.html` to save one request.

Standard pattern: `<i class="bi bi-bell" aria-hidden="true"></i>` with visually hidden text for screen readers.

---

## 11. Motion

```css
:root {
  --motion-fast: 120ms;
  --motion-base: 200ms;
  --motion-slow: 320ms;
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
}
```

Rules:
- Hover / focus: `--motion-fast`.
- Open / close (modal, offcanvas): `--motion-base`.
- Bracket layout transitions (Phase 3): `--motion-slow` with stagger.
- `prefers-reduced-motion` disables all non-essential transitions — add a single `@media` block in `tokens.css`.

---

## 12. Accessibility defaults

- All focusable elements must show a visible ring: default outline = `2px solid var(--brand-blue-dark)`.
- Minimum contrast: body text on `--surface-page` passes AA (black on #F5F7FA ≈ 19:1).
- Buttons have an accessible label: icon-only buttons use `<button aria-label="Copy code">`.
- Every `<img>` has `alt` — avatar fallbacks use initials rendered as SVG, not `robohash.org`.

---

## 13. Naming conventions for CSS classes

- `.card-ui`, `.btn-ui`, `.table-ui` — redesigned components. Mixing these with unscoped Bootstrap class names is fine during migration.
- `.is-*` — state modifiers (`.is-clickable`, `.is-open`).
- `.has-*` — content modifiers (`.has-badge`, `.has-icon`).
- Avoid utility classes — Bootstrap 5 ships plenty; don't invent custom `mt-4-5` forks.

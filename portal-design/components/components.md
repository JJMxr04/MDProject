# Reusable components

All partials live under `core/portal/templates/portal/components/`. Prefix private partials with an underscore (`_card.html`) so it's obvious they're never extended.

Each component entry below gives:

- **Path** — where the file lives.
- **Purpose** — one line.
- **Context** — variables the template expects.
- **Usage** — how to include it.
- **Template** — the actual implementation (abridged but working).

---

## Shell

### `portal/base_app.html` (new — replaces both `base_portal.html` and `base_admin.html`)

**Purpose**: single shell layout used by portal and admin. Accepts a `section_nav` block for per-section sub-navigation.

```django
{# core/portal/templates/portal/base_app.html #}
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  {% load static %}
  <link rel="stylesheet" href="{% static 'css/portal/tokens.css' %}">
  <link rel="stylesheet" href="{% static 'css/portal/portal_main.css' %}">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css">
  <title>{% block title %}Portal{% endblock %}</title>
  {% block head_extra %}{% endblock %}
</head>
<body class="app-shell">
  <a class="skip-link" href="#main">Skip to content</a>
  {% include "portal/components/_topbar.html" %}
  <aside class="sidebar" aria-label="Primary">
    {% include "portal/components/_sidebar.html" %}
  </aside>
  <div class="content">
    {% block section_nav %}{% endblock %}
    <main id="main" class="content__inner">
      {% block content %}{% endblock %}
    </main>
  </div>
  {% include "portal/components/_toast_host.html" %}
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js"></script>
  {% block scripts %}{% endblock %}
</body>
</html>
```

---

### `portal/components/_topbar.html`

**Purpose**: branded gradient bar with logo, search, notification bell, avatar dropdown.

**Context**: uses `request.user` directly, plus `{% unread_invite_count %}` filter.

```django
{% load static %}
<header class="topbar" role="banner">
  <button class="sidebar-toggle btn-ui btn-ui--ghost btn-ui--icon-only d-lg-none"
          aria-label="Open navigation" data-action="toggle-sidebar">
    <i class="bi bi-list"></i>
  </button>

  <a class="topbar__brand" href="{% url 'core-portal:portal-dashboard' %}">
    <img src="{% static 'assets/Logo/paradise_logo_2_normal.png' %}" alt="Paradise" height="32">
  </a>

  <div class="topbar__spacer"></div>

  <a class="topbar__bell btn-ui btn-ui--ghost btn-ui--icon-only" href="{% url 'core-portal:invite-list' %}"
     aria-label="Invites">
    <i class="bi bi-bell"></i>
    {% if request.user.is_authenticated %}
      {% with unread=request.user.invite_set.count %}
        {% if unread %}<span class="topbar__bell-dot" aria-hidden="true"></span>{% endif %}
      {% endwith %}
    {% endif %}
  </a>

  {% include "portal/components/_avatar_menu.html" %}
</header>
```

---

### `portal/components/_sidebar.html`

**Purpose**: primary navigation. Highlights the active section by URL prefix.

```django
{% load portal_nav %}
<nav class="sidenav">
  <ul class="sidenav__list">
    {% sidenav_item url="core-portal:portal-dashboard" icon="house"  label="Dashboard" %}
    {% sidenav_item url="core-portal:upcoming-events"  icon="calendar-event" label="Events" %}
    {% sidenav_item url="core-portal:portal-my-match-list" icon="controller" label="Matches" prefix="/web/portal/match/" %}
    {% sidenav_item url="core-portal:core-portal-tournament:portal-my-tournaments" icon="trophy" label="Tournaments" prefix="/web/portal/tournament/" %}
    {% sidenav_item url="core-portal:friend_search"    icon="people" label="Friends" %}
    {% sidenav_item url="core-portal:invite-list"      icon="envelope" label="Invites" %}
  </ul>
</nav>
```

The `sidenav_item` tag lives in `core/portal/templatetags/portal_nav.py` and returns an `<li>` with `aria-current="page"` if the current request path starts with the item's URL.

---

## Primitives

### `portal/components/_page_header.html`

**Purpose**: consistent page title + subtitle + actions row.

**Context**: `title`, `subtitle?`, `actions?` (block).

**Usage**:
```django
{% include "portal/components/_page_header.html" with title="My Matches" subtitle="All matches you've played or created" %}
```

**Template**:
```django
<header class="page-header">
  <div>
    <h1 class="page-header__title">{{ title }}</h1>
    {% if subtitle %}<p class="page-header__subtitle">{{ subtitle }}</p>{% endif %}
  </div>
  <div class="page-header__actions">
    {% block page_actions %}{% endblock %}
  </div>
</header>
```

When a page needs action buttons, it passes them via the `page_actions` block rather than a variable:

```django
{% with title="My Matches" subtitle="Your match history" %}
  {% include "portal/components/_page_header.html" %}
{% endwith %}
{# or the inherit form when multiple actions are needed #}
```

Because blocks can't cross `{% include %}` boundaries cleanly, in practice the component is implemented as an `{% include %}` variant that takes an `actions_include` context variable:

```django
{% include "portal/components/_page_header.html" with title="My Matches" actions_include="portal/match/_my_matches_actions.html" %}
```

And the header renders it with `{% include actions_include %}` when the variable is set.

---

### `portal/components/_stat_card.html`

**Purpose**: one of the 4 dashboard stat cards.

**Context**: `label`, `value`, `icon?`, `trend?` (signed number or `None`), `href?`.

**Usage**:
```django
{% include "portal/components/_stat_card.html" with label="Active matches" value=stats.active_match_count icon="controller" href=match_list_url %}
```

**Template**:
```django
<a class="stat-card {% if not href %}stat-card--static{% endif %}"
   {% if href %}href="{{ href }}"{% endif %}>
  <div class="stat-card__icon"><i class="bi bi-{{ icon|default:'bar-chart' }}"></i></div>
  <div class="stat-card__body">
    <div class="stat-card__label">{{ label }}</div>
    <div class="stat-card__value">{{ value }}</div>
    {% if trend is not None %}
      <div class="stat-card__trend {% if trend > 0 %}is-up{% elif trend < 0 %}is-down{% endif %}">
        {% if trend > 0 %}+{% endif %}{{ trend }}
      </div>
    {% endif %}
  </div>
</a>
```

---

### `portal/components/_badge.html`

**Purpose**: pill for a state enum.

**Context**: `state` (raw string) **or** `variant` + `label`.

**Usage**:
```django
{% include "portal/components/_badge.html" with state=tournament.state %}
```

**Template**:
```django
{% load portal_state %}
{% with mapping=state|state_badge %}
  <span class="badge-ui badge-ui--{{ mapping.variant }}">{{ mapping.label }}</span>
{% endwith %}
```

The `state_badge` filter is a dict lookup defined in `core/portal/templatetags/portal_state.py`:

```python
from django import template
register = template.Library()

STATE_MAP = {
  "created":    {"variant": "info",    "label": "Upcoming"},
  "inprogress": {"variant": "primary", "label": "In Progress"},
  "completed":  {"variant": "success", "label": "Completed"},
  "aborted":    {"variant": "danger",  "label": "Aborted"},
  "sent":       {"variant": "muted",   "label": "Invite sent"},
  "accepted":   {"variant": "success", "label": "Accepted"},
  "declined":   {"variant": "danger",  "label": "Declined"},
  "expired":    {"variant": "warning", "label": "Expired"},
}

@register.filter
def state_badge(state):
    return STATE_MAP.get(state, {"variant": "muted", "label": state})
```

---

### `portal/components/_field.html`

**Purpose**: standard Django form field render (label + input + hint + errors).

**Context**: `field` (a bound form field).

**Usage**:
```django
{% include "portal/components/_field.html" with field=form.email %}
{% include "portal/components/_field.html" with field=form.bio hint="Up to 280 chars." %}
```

**Template**:
```django
<div class="field {% if field.errors %}has-error{% endif %}">
  <label for="{{ field.id_for_label }}" class="field-label">
    {{ field.label }}{% if field.field.required %}<span aria-hidden="true"> *</span>{% endif %}
  </label>
  {{ field|add_class:"field-input" }}
  {% if hint and not field.errors %}<div class="field-hint">{{ hint }}</div>{% endif %}
  {% for error in field.errors %}<div class="field-error">{{ error }}</div>{% endfor %}
</div>
```

Requires `django-widget-tweaks` for `|add_class` — lightweight, worth adding.

---

### `portal/components/_empty_state.html`

**Purpose**: the *only* empty-state template. Use it everywhere something could have no rows.

**Context**: `title`, `body?`, `icon?`, `action_label?`, `action_href?`.

**Usage**:
```django
{% include "portal/components/_empty_state.html" with title="No matches yet" body="Create a public match or accept a friend's invite." icon="controller" action_label="New match" action_href=new_match_url %}
```

**Template**:
```django
<div class="empty-state">
  <div class="empty-state__icon"><i class="bi bi-{{ icon|default:'inbox' }}"></i></div>
  <h2 class="empty-state__title">{{ title }}</h2>
  {% if body %}<p class="empty-state__body">{{ body }}</p>{% endif %}
  {% if action_label %}
    <a class="btn-ui btn-ui--primary" href="{{ action_href }}">{{ action_label }}</a>
  {% endif %}
</div>
```

---

### `portal/components/_skeleton.html`

**Purpose**: placeholder row / block for loading states.

**Context**: `rows` (int, default 3), `cols` (int, default 4).

**Template**:
```django
<div class="skeleton" aria-hidden="true" role="presentation">
  {% for _ in rows|default:3|make_list %}
    <div class="skeleton__row">
      {% for _ in cols|default:4|make_list %}
        <span class="skeleton__cell"></span>
      {% endfor %}
    </div>
  {% endfor %}
</div>
```

Usage: render initially as server-side HTML for fetch-driven tabs; replaced by real markup after fetch resolves. Non-SSR pages never need it.

---

### `portal/components/_toast_host.html` + JS helper

**Purpose**: lightweight toast replacement for `alert()`.

**Template**:
```django
<div class="toast-host" aria-live="polite" aria-atomic="true"></div>
```

**JS** (in `static/js/portal/toast.js`):
```js
export function toast(message, { variant = "info", timeout = 4000 } = {}) {
  const host = document.querySelector(".toast-host");
  const el = Object.assign(document.createElement("div"), {
    className: `toast-ui toast-ui--${variant}`,
    textContent: message,
    role: "status",
  });
  host.appendChild(el);
  setTimeout(() => el.remove(), timeout);
}
window.toast = toast;
```

Use everywhere a `fetch()` resolves/fails.

---

### `portal/components/_modal.html`

**Purpose**: Bootstrap-backed modal with consistent header/body/footer.

**Context**: `modal_id`, `title`, `body_include` (template path to render as body), `confirm_label?`, `confirm_action?`, `cancel_label?` (default "Cancel").

**Template**:
```django
<div class="modal fade" id="{{ modal_id }}" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content">
      <div class="modal-header">
        <h2 class="modal-title">{{ title }}</h2>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>
      <div class="modal-body">{% include body_include %}</div>
      <div class="modal-footer">
        <button type="button" class="btn-ui btn-ui--secondary" data-bs-dismiss="modal">{{ cancel_label|default:"Cancel" }}</button>
        {% if confirm_label %}
          <button type="button" class="btn-ui btn-ui--primary" data-action="{{ confirm_action }}">
            {{ confirm_label }}
          </button>
        {% endif %}
      </div>
    </div>
  </div>
</div>
```

This replaces both the hand-rolled modal in `public_match_list.html` and the one in `friend_search.html`.

---

### `portal/components/_loading_overlay.html`

**Purpose**: shared spinner overlay for in-flight actions.

```django
<div class="loading-overlay" data-loading-overlay hidden>
  <div class="loading-overlay__spinner"></div>
  <p class="loading-overlay__label">Processing…</p>
</div>
```

Toggle with `document.querySelector('[data-loading-overlay]').hidden = false`.

---

### `portal/components/_avatar.html`

**Purpose**: consistent avatar rendering with initial-based SVG fallback.

**Context**: `user`, `size?` (px, default 40).

**Template**:
```django
<span class="avatar" style="--avatar-size: {{ size|default:40 }}px;">
  {% if user.avatar %}
    <img src="{{ user.avatar.url }}" alt="{{ user.username }}">
  {% else %}
    <span class="avatar__initials" aria-hidden="true">
      {{ user.first_name|default:user.username|slice:":1"|upper }}
    </span>
  {% endif %}
</span>
```

No more `robohash.org` links, no more broken `placeholder.jpg`.

---

### `portal/components/_breadcrumbs.html`

**Purpose**: consistent breadcrumb row.

**Context**: `crumbs` — list of `{"label": ..., "href": ...}` dicts. Last one has no `href`.

**Template**:
```django
<nav aria-label="Breadcrumb" class="breadcrumbs">
  <ol>
    {% for c in crumbs %}
      <li>
        {% if c.href %}<a href="{{ c.href }}">{{ c.label }}</a>
        {% else %}<span aria-current="page">{{ c.label }}</span>{% endif %}
      </li>
    {% endfor %}
  </ol>
</nav>
```

---

### `portal/components/_filter_bar.html`

**Purpose**: horizontal filter bar that replaces the vertical filter sidebars currently on matches and tournaments.

**Context**: `form` (Django `FilterForm`), `quick_filters` (list of `{"label", "value", "is_active"}` for status chips).

**Template**:
```django
<form method="get" class="filter-bar" data-debounce>
  <div class="filter-bar__tabs" role="tablist">
    {% for f in quick_filters %}
      <button type="submit" name="status" value="{{ f.value }}"
              class="filter-bar__tab {% if f.is_active %}is-active{% endif %}"
              role="tab" aria-selected="{{ f.is_active|yesno:'true,false' }}">
        {{ f.label }}
      </button>
    {% endfor %}
  </div>
  <div class="filter-bar__controls">
    {% include "portal/components/_field.html" with field=form.q %}
    {% include "portal/components/_field.html" with field=form.start_date %}
    {% include "portal/components/_field.html" with field=form.end_date %}
  </div>
</form>
```

---

### `portal/components/_pagination.html`

**Purpose**: one pagination template for every table. Replaces the three divergent copies currently in `my_match_list.html`, `public_match_list.html`, `my_tournaments.html`.

**Context**: `page_obj`, `querystring` (preserved GET params without `page=`).

**Template**:
```django
{% if page_obj.paginator.num_pages > 1 %}
<nav class="pager" aria-label="Pagination">
  <a class="pager__btn" {% if page_obj.has_previous %}href="?{{ querystring }}&page={{ page_obj.previous_page_number }}"{% else %}aria-disabled="true"{% endif %}>
    <i class="bi bi-chevron-left"></i> Prev
  </a>
  <span class="pager__pages">
    Page {{ page_obj.number }} of {{ page_obj.paginator.num_pages }}
  </span>
  <a class="pager__btn" {% if page_obj.has_next %}href="?{{ querystring }}&page={{ page_obj.next_page_number }}"{% else %}aria-disabled="true"{% endif %}>
    Next <i class="bi bi-chevron-right"></i>
  </a>
</nav>
{% endif %}
```

A `querystring` helper filter strips `page` from `request.GET.urlencode()`:

```python
# core/portal/templatetags/portal_qs.py
from django import template
register = template.Library()

@register.simple_tag(takes_context=True)
def querystring_without_page(context):
    qd = context["request"].GET.copy()
    qd.pop("page", None)
    return qd.urlencode()
```

---

### `portal/components/_game_card.html` (keep, revise)

File already exists in `core/match/templates/portal/match/_game_card.html`. Revise its CSS to use tokens; keep the context contract (`game`, `is_active`, etc.).

---

## Summary of new partials to create

| Path | Purpose |
| --- | --- |
| `_topbar.html` | Shared top bar |
| `_sidebar.html` | Shared left nav |
| `_avatar_menu.html` | Avatar dropdown in topbar |
| `_page_header.html` | Title + actions |
| `_stat_card.html` | Dashboard stat tile |
| `_badge.html` | State pill |
| `_field.html` | Form field |
| `_empty_state.html` | Empty state |
| `_skeleton.html` | Loading skeleton |
| `_toast_host.html` | Toast host |
| `_modal.html` | Modal shell |
| `_loading_overlay.html` | Spinner overlay |
| `_avatar.html` | Avatar (image or initials) |
| `_breadcrumbs.html` | Breadcrumb trail |
| `_filter_bar.html` | Filter bar |
| `_pagination.html` | Pagination |

Plus two template-tag libraries: `portal_nav` and `portal_state`.

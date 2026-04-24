# Template — Profile / Account settings

**URL**: `/web/portal/user/profile/`
**Template**: `core/user/templates/portal/user/user_profile_form.html`
**View**: `core.user.views.UserProfileUpdateView`

Replaces the bare single-column form with a SaaS-style settings page — left rail of sections, right panel with the active section's form.

---

## Layout

```
┌────────────────────────────────────────────────────────────────┐
│ breadcrumbs:  Profile                                          │
├────────────────────────────────────────────────────────────────┤
│ page-header:  {{ full_name }}           [View public profile]  │
├──────────────────┬─────────────────────────────────────────────┤
│ nav rail         │  section panel                              │
│ Profile   ✓      │  ┌─ Profile ──────────────────────────────┐ │
│ Security         │  │  Avatar                                 │ │
│ Notifications    │  │  Display name                           │ │
│ Account          │  │  Username                               │ │
│                  │  │  Email                                  │ │
│                  │  │  Bio                                    │ │
│                  │  │  [Save]    [Cancel]                    │ │
│                  │  └─────────────────────────────────────────┘ │
└──────────────────┴─────────────────────────────────────────────┘
```

Rail sticks to top; panel scrolls. On mobile (< 768 px) rail collapses to a `select` at the top of the content area.

---

## Sections (delivery order)

| Section | Ship in | Fields |
| --- | --- | --- |
| **Profile** | Phase 1 | avatar, first name, last name, username, email, bio |
| **Friends** (view-only mirror of `/web/portal/user/friends/search/`) | Phase 2 | friend code, regenerate, search + list |
| **Security** | Phase 2 | change password (Django's PasswordChangeForm) |
| **Notifications** | Phase 3 | email opt-ins (match reminders, tournament reminders) — requires `UserNotificationPrefs` model |
| **Account** | Phase 3 | deactivate account (soft delete), export my data |

Only ship what you have data for. Hide unbuilt tabs rather than greying them out.

---

## URL routing

Single view per section, one URL each:

```python
# core/user/urls.py
path('profile/',                 ProfileSectionView.as_view(),         name='profile'),
path('profile/security/',        SecuritySectionView.as_view(),        name='profile-security'),
path('profile/notifications/',   NotificationsSectionView.as_view(),   name='profile-notifications'),
path('profile/account/',         AccountSectionView.as_view(),         name='profile-account'),
```

Each section is its own page. Rail items mark active via URL match.

Benefits over tabs: server renders only the active form, bookmarks work, Django's form-handling (POST/redirect/GET) fits naturally.

---

## Template

```django
{% extends "portal/base_app.html" %}
{% load static %}

{% block title %}Profile{% endblock %}

{% block content %}
  {% include "portal/components/_breadcrumbs.html" with crumbs=crumbs %}
  {% include "portal/components/_page_header.html" with title=request.user.name|default:request.user.username subtitle=request.user.email actions_include="portal/user/_profile_header_actions.html" %}

  <div class="settings-layout">
    <aside class="settings-rail" aria-label="Settings sections">
      <ul>
        <li><a href="{% url 'core-portal:profile' %}"               class="{% if section == 'profile' %}is-active{% endif %}" {% if section == 'profile' %}aria-current="page"{% endif %}><i class="bi bi-person"></i> Profile</a></li>
        <li><a href="{% url 'core-portal:profile-security' %}"      class="{% if section == 'security' %}is-active{% endif %}"><i class="bi bi-shield-lock"></i> Security</a></li>
        <li><a href="{% url 'core-portal:profile-notifications' %}" class="{% if section == 'notifications' %}is-active{% endif %}"><i class="bi bi-bell"></i> Notifications</a></li>
        <li><a href="{% url 'core-portal:profile-account' %}"       class="{% if section == 'account' %}is-active{% endif %}"><i class="bi bi-gear"></i> Account</a></li>
      </ul>
    </aside>

    <section class="settings-panel card-ui">
      {% block section_content %}{% endblock %}
    </section>
  </div>
{% endblock %}
```

### Profile section template

```django
{% extends "portal/user/profile_base.html" %}
{% load widget_tweaks %}

{% block section_content %}
  <header class="card-ui__header">
    <h2>Profile</h2>
    <p class="small">Public info other players can see.</p>
  </header>

  <form method="post" enctype="multipart/form-data" class="profile-form">
    {% csrf_token %}

    <div class="profile-form__avatar">
      {% include "portal/components/_avatar.html" with user=request.user size=96 %}
      <div>
        <label class="field-label" for="{{ form.avatar.id_for_label }}">Avatar</label>
        {{ form.avatar|add_class:"field-input" }}
        <p class="field-hint">PNG or JPG, up to 2 MB.</p>
      </div>
    </div>

    <div class="grid-columns-2 gap-5">
      {% include "portal/components/_field.html" with field=form.first_name %}
      {% include "portal/components/_field.html" with field=form.last_name %}
    </div>

    {% include "portal/components/_field.html" with field=form.username hint="Others find you by this name." %}
    {% include "portal/components/_field.html" with field=form.email %}
    {% include "portal/components/_field.html" with field=form.bio hint="Up to 280 characters." %}

    <div class="form-actions">
      <button type="submit" class="btn-ui btn-ui--primary">Save changes</button>
      <a class="btn-ui btn-ui--ghost" href="{% url 'core-portal:profile' %}">Cancel</a>
    </div>
  </form>
{% endblock %}
```

### Security section template (Phase 2)

```django
{% extends "portal/user/profile_base.html" %}

{% block section_content %}
  <header class="card-ui__header">
    <h2>Security</h2>
    <p class="small">Protect your account.</p>
  </header>

  <form method="post">
    {% csrf_token %}
    {% include "portal/components/_field.html" with field=form.old_password %}
    {% include "portal/components/_field.html" with field=form.new_password1 %}
    {% include "portal/components/_field.html" with field=form.new_password2 %}
    <div class="form-actions">
      <button type="submit" class="btn-ui btn-ui--primary">Change password</button>
    </div>
  </form>
{% endblock %}
```

---

## Avatar live preview (vanilla JS, no framework)

```html
<script>
  const input = document.querySelector('input[name="avatar"]');
  const preview = document.querySelector('.avatar img');
  if (input && preview) {
    input.addEventListener('change', (e) => {
      const [file] = e.target.files;
      if (!file) return;
      preview.src = URL.createObjectURL(file);
    });
  }
</script>
```

6 lines. No "drag-drop dropzone" until we need it.

---

## CSS

```css
.settings-layout {
  display: grid; grid-template-columns: 220px 1fr; gap: var(--space-6);
}
.settings-rail ul { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: var(--space-1); }
.settings-rail a  {
  display: flex; align-items: center; gap: var(--space-2);
  padding: var(--space-2) var(--space-3); border-radius: 8px;
  color: var(--text-primary); text-decoration: none;
}
.settings-rail a:hover         { background: var(--surface-muted); }
.settings-rail a.is-active     { background: var(--brand-yellow); color: var(--text-on-accent); font-weight: var(--weight-semibold); }

.profile-form          { padding: var(--space-5); display: flex; flex-direction: column; gap: var(--space-5); }
.profile-form__avatar  { display: grid; grid-template-columns: 96px 1fr; gap: var(--space-4); align-items: center; }
.form-actions          { display: flex; gap: var(--space-3); margin-top: var(--space-4); }
.grid-columns-2        { display: grid; grid-template-columns: 1fr 1fr; }

@media (max-width: 768px) {
  .settings-layout       { grid-template-columns: 1fr; }
  .profile-form__avatar  { grid-template-columns: 1fr; text-align: center; }
}
```

---

## Validation / error UX

- Field-level errors render inside `_field.html` via `.field-error`.
- Form-level non-field errors render above the form in a `.alert-banner--danger` partial.
- Successful save: redirect back to the same section URL with `?saved=1`; template shows a green dismissable toast via `_toast_host.html`.

---

## Accessibility

- Rail is `<nav aria-label="Settings sections">`; active link has `aria-current="page"`.
- Avatar label is associated with input via `for` attribute (via `{{ field.id_for_label }}` in `_field.html`).
- Password field errors announce via `aria-live="polite"` on the form actions region.

---

## Done criteria

- [ ] Four sections route to four URLs.
- [ ] Avatar preview updates before save.
- [ ] Form errors render per-field, not as a raw `{{ form.non_field_errors }}` blob.
- [ ] Rail collapses correctly at 768 px.
- [ ] Cancel link returns to the section URL without state.

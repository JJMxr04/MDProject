"""Form-rendering template tags.

`add_class` mirrors django-widget-tweaks' `add_class` — lets us inject a CSS
class onto a bound form field from the template layer without pulling in a new
dependency.
"""
from django import template

register = template.Library()


@register.filter(name="add_class")
def add_class(field, css):
    """Return the bound field rendered with `css` appended to its class attr."""
    existing = field.field.widget.attrs.get("class", "")
    classes = f"{existing} {css}".strip()
    return field.as_widget(attrs={**field.field.widget.attrs, "class": classes})

from django import template
from django.utils.timesince import timesince as django_timesince

from reader import services

register = template.Library()


@register.filter
def short_timesince(value):
    """'4 months, 1 week' -> '4 tháng trước' (keeps only the first unit,
    matching the compact 'X ago' style used in chapter lists)."""
    if not value:
        return ""
    full = django_timesince(value)
    first_unit = full.split(",")[0]
    return f"{first_unit} trước"


@register.filter
def format_count(value):
    """103245 -> '103k', None -> 'N/A' — for follow/comment counts."""
    return services.format_count(value)
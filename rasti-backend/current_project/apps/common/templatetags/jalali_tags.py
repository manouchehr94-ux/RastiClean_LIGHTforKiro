from django import template

from apps.common.jalali import format_jalali, format_jalali_datetime, parse_jalali_date

register = template.Library()


@register.filter
def jalali_date(value):
    return format_jalali(value, include_time=False)


@register.filter
def jalali_datetime(value):
    return format_jalali_datetime(value)


@register.filter
def to_jalali(value):
    return format_jalali(value, include_time=True)


@register.filter
def dict_get(value, key):
    try:
        return value.get(key, "")
    except Exception:
        return ""

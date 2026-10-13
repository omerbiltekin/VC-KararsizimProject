from datetime import timedelta

from django import template
from django.utils import timezone
from django.utils.timesince import timesince

register = template.Library()


@register.filter
def relative_time(value):
    now = timezone.now()
    if now - value < timedelta(minutes=1):
        return "az önce"
    return f"{timesince(value, now, depth=1)} önce"

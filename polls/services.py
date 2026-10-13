from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Option, Poll

DAILY_POLL_LIMIT = 10


class DailyLimitExceeded(Exception):
    pass


def create_poll(*, author, question, description, option_texts):
    since = timezone.now() - timedelta(hours=24)
    with transaction.atomic():
        if Poll.objects.filter(author=author, created_at__gte=since).count() >= DAILY_POLL_LIMIT:
            raise DailyLimitExceeded
        poll = Poll.objects.create(author=author, question=question, description=description)
        Option.objects.bulk_create(
            [Option(poll=poll, text=text, position=index) for index, text in enumerate(option_texts)]
        )
    return poll

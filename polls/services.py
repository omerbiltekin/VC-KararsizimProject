from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from .models import Option, Poll, Vote

DAILY_POLL_LIMIT = 10


class DailyLimitExceeded(Exception):
    pass


class PollClosed(Exception):
    pass


class InvalidOption(Exception):
    pass


class AlreadyVoted(Exception):
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


def has_voted(poll, user, voter_key):
    votes = Vote.objects.filter(poll=poll)
    if user is not None:
        return votes.filter(user=user).exists()
    return votes.filter(user__isnull=True, voter_key=voter_key).exists()


def cast_vote(*, poll, option_id, user, voter_key):
    if not poll.is_open:
        raise PollClosed

    try:
        option = Option.objects.get(pk=int(option_id), poll=poll)
    except (TypeError, ValueError, Option.DoesNotExist):
        raise InvalidOption

    if has_voted(poll, user, voter_key):
        raise AlreadyVoted

    # Yarış durumunda ikinci istek veritabanı kısıtına takılır.
    try:
        with transaction.atomic():
            Vote.objects.create(poll=poll, option=option, user=user, voter_key=voter_key)
            Option.objects.filter(pk=option.pk).update(vote_count=F("vote_count") + 1)
            Poll.objects.filter(pk=poll.pk).update(total_votes=F("total_votes") + 1)
    except IntegrityError:
        raise AlreadyVoted
    return option


def close_poll(poll):
    poll.status = Poll.Status.CLOSED
    poll.save(update_fields=["status"])

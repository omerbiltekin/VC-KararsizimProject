from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.utils import timezone

from .models import Poll

FEED_PAGE_SIZE = 20
MAX_PAGE = 50

TAB_NEW = "yeni"
TAB_POPULAR = "populer"
TAB_CLOSED = "kapananlar"
TABS = (
    (TAB_NEW, "Yeni"),
    (TAB_POPULAR, "Popüler"),
    (TAB_CLOSED, "Kapananlar"),
)


def _with_related(queryset):
    return queryset.select_related("author").prefetch_related("options")


def _open_filter(now):
    return Q(status=Poll.Status.ACTIVE) & (Q(closes_at__isnull=True) | Q(closes_at__gt=now))


def feed_queryset(tab):
    now = timezone.now()
    polls = _with_related(Poll.objects.all())
    if tab == TAB_CLOSED:
        return polls.exclude(_open_filter(now))
    polls = polls.filter(_open_filter(now))
    if tab == TAB_POPULAR:
        week_ago = now - timedelta(days=7)
        polls = polls.annotate(
            recent_votes=Count("votes", filter=Q(votes__created_at__gte=week_ago))
        ).order_by("-recent_votes", "-created_at")
    return polls


def user_polls(user):
    return _with_related(Poll.objects.filter(author=user))


def user_stats(user):
    stats = Poll.objects.filter(author=user).aggregate(
        poll_count=Count("id"), votes_received=Sum("total_votes")
    )
    return {
        "poll_count": stats["poll_count"],
        "votes_received": stats["votes_received"] or 0,
    }


def get_user_by_username(username):
    return get_user_model().objects.filter(username__iexact=username).first()


def paginate_cumulative(queryset, page):
    """?page=N ilk N*20 kaydı döner; JS olmadan da çalışan 'Daha fazla göster' için."""
    limit = page * FEED_PAGE_SIZE
    items = list(queryset[: limit + 1])
    return items[:limit], len(items) > limit

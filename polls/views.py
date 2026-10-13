from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from . import selectors, services
from .forms import PollForm
from .models import Poll
from .results import attach_results, build_results


def _page_number(request):
    try:
        page = int(request.GET.get("page", 1))
    except ValueError:
        return 1
    return min(max(page, 1), selectors.MAX_PAGE)


def _more_url(base_path, params, page, has_more):
    if not has_more:
        return None
    return f"{base_path}?{urlencode({**params, 'page': page + 1})}"


def index(request):
    tab = request.GET.get("tab", selectors.TAB_NEW)
    if tab not in dict(selectors.TABS):
        tab = selectors.TAB_NEW
    page = _page_number(request)

    polls, has_more = selectors.paginate_cumulative(selectors.feed_queryset(tab), page)
    tabs = [
        {"url": f"{reverse('polls:index')}?tab={slug}", "label": label, "active": slug == tab}
        for slug, label in selectors.TABS
    ]
    context = {
        "polls": attach_results(polls),
        "tabs": tabs,
        "more_url": _more_url(reverse("polls:index"), {"tab": tab}, page, has_more),
        "show_create_cta": True,
    }
    return render(request, "polls/index.html", context)


def detail(request, public_id):
    poll = get_object_or_404(
        Poll.objects.select_related("author").prefetch_related("options"), public_id=public_id
    )
    return render(request, "polls/detail.html", {"poll": poll, "results": build_results(poll)})


@login_required
def create(request):
    if request.method == "POST":
        form = PollForm(request.POST)
        if form.is_valid():
            try:
                poll = services.create_poll(
                    author=request.user,
                    question=form.cleaned_data["question"],
                    description=form.cleaned_data["description"],
                    option_texts=form.cleaned_data["options"],
                )
            except services.DailyLimitExceeded:
                form.add_error(
                    None, f"Bugün en fazla {services.DAILY_POLL_LIMIT} anket açabilirsin."
                )
            else:
                messages.success(request, "Anketin yayında.")
                return redirect(poll.get_absolute_url())
    else:
        form = PollForm()
    return render(request, "polls/create.html", {"form": form})


def profile(request, username):
    profile_user = selectors.get_user_by_username(username)
    if profile_user is None:
        raise Http404
    page = _page_number(request)
    polls, has_more = selectors.paginate_cumulative(selectors.user_polls(profile_user), page)
    path = reverse("polls:profile", args=[profile_user.username])
    context = {
        "profile_user": profile_user,
        "stats": selectors.user_stats(profile_user),
        "polls": attach_results(polls),
        "more_url": _more_url(path, {}, page, has_more),
        "show_create_cta": False,
    }
    return render(request, "polls/profile.html", context)

from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from . import selectors, services, utils
from .forms import PollForm
from .models import Poll
from .results import attach_results, build_results, can_see_results, results_payload

MESSAGE_CLOSED = "Bu anket kapandı."
MESSAGE_INVALID_OPTION = "Geçersiz seçenek. Sayfayı yenileyip tekrar dene."
MESSAGE_ALREADY_VOTED = "Bu ankete zaten oy verdin."
MESSAGE_VOTED = "Oyun kaydedildi."


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


def _viewer(request):
    return request.user if request.user.is_authenticated else None


def _attach_for_viewer(request, polls):
    user = _viewer(request)
    voted_ids = selectors.voted_poll_ids(
        [poll.id for poll in polls], user, utils.existing_voter_key(request)
    )
    return attach_results(
        polls, viewer_id=user.id if user else None, voted_poll_ids=voted_ids
    )


def _wants_json(request):
    return (
        "application/json" in request.headers.get("Accept", "")
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    )


def _remember_vote(request, poll_id):
    voted = request.session.get("voted_polls", [])
    if poll_id not in voted:
        request.session["voted_polls"] = voted + [poll_id]


def _get_poll_or_404(public_id):
    poll = selectors.get_poll(public_id)
    if poll is None:
        raise Http404
    return poll


def _owned_poll_or_403(request, public_id):
    poll = _get_poll_or_404(public_id)
    if poll.author_id != request.user.id:
        raise PermissionDenied
    return poll


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
        "polls": _attach_for_viewer(request, polls),
        "tabs": tabs,
        "more_url": _more_url(reverse("polls:index"), {"tab": tab}, page, has_more),
        "show_create_cta": True,
    }
    return render(request, "polls/index.html", context)


def detail(request, public_id):
    poll = _get_poll_or_404(public_id)
    user = _viewer(request)
    vote = selectors.find_vote(poll, user, utils.existing_voter_key(request))
    voted_option_id = vote.option_id if vote else None
    reveal = can_see_results(poll, viewer_id=user.id if user else None, voted=vote is not None)
    context = {
        "poll": poll,
        "results": build_results(poll, reveal=reveal),
        "voted_option_id": voted_option_id,
        "can_vote": poll.is_open and vote is None,
        "is_author": user is not None and poll.author_id == user.id,
    }
    return render(request, "polls/detail.html", context)


@require_POST
def vote(request, public_id):
    poll = _get_poll_or_404(public_id)
    user = _viewer(request)
    voter_key = utils.get_voter_key(request)

    status, message, voted_option_id = 200, MESSAGE_VOTED, None
    try:
        option = services.cast_vote(
            poll=poll,
            option_id=request.POST.get("option_id"),
            user=user,
            voter_key=voter_key,
        )
        voted_option_id = option.id
        _remember_vote(request, poll.id)
    except services.PollClosed:
        status, message = 403, MESSAGE_CLOSED
    except services.InvalidOption:
        status, message = 400, MESSAGE_INVALID_OPTION
    except services.AlreadyVoted:
        status, message = 409, MESSAGE_ALREADY_VOTED
        existing = selectors.find_vote(poll, user, voter_key)
        voted_option_id = existing.option_id if existing else None
        _remember_vote(request, poll.id)

    if _wants_json(request):
        body = {"ok": status == 200, "message": message, "results": None}
        if status != 400:
            fresh = _get_poll_or_404(public_id)
            body["results"] = results_payload(
                fresh, voted_option_id=voted_option_id, reveal=True
            )
        return JsonResponse(body, status=status)

    if status == 200:
        messages.success(request, message)
    else:
        messages.error(request, message)
    return redirect(poll.get_absolute_url())


@require_GET
@never_cache
def results(request, public_id):
    poll = _get_poll_or_404(public_id)
    user = _viewer(request)
    vote = selectors.find_vote(poll, user, utils.existing_voter_key(request))
    reveal = can_see_results(poll, viewer_id=user.id if user else None, voted=vote is not None)
    payload = results_payload(
        poll, voted_option_id=vote.option_id if vote else None, reveal=reveal
    )
    return JsonResponse(payload)


@login_required
@require_POST
def close(request, public_id):
    poll = _owned_poll_or_403(request, public_id)
    services.close_poll(poll)
    messages.success(request, "Anket kapatıldı.")
    return redirect(poll.get_absolute_url())


@login_required
def delete(request, public_id):
    poll = _owned_poll_or_403(request, public_id)
    if request.method == "POST":
        poll.delete()
        messages.success(request, "Anket silindi.")
        return redirect("polls:index")
    return render(request, "polls/confirm_delete.html", {"poll": poll})


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
        "polls": _attach_for_viewer(request, polls),
        "more_url": _more_url(path, {}, page, has_more),
        "show_create_cta": False,
    }
    return render(request, "polls/profile.html", context)

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver


@receiver(user_logged_in)
def link_session_votes_to_user(sender, request, user, **kwargs):
    if not request:
        return
    voted_ids = request.session.get("voted_polls", [])
    if not voted_ids:
        return

    from polls.models import Vote
    from polls.utils import existing_voter_key

    user_voted_poll_ids = set(
        Vote.objects.filter(user=user, poll_id__in=voted_ids).values_list("poll_id", flat=True)
    )
    claimable_poll_ids = [pid for pid in voted_ids if pid not in user_voted_poll_ids]
    if not claimable_poll_ids:
        return

    voter_key = existing_voter_key(request)
    for poll_id in claimable_poll_ids:
        qs = Vote.objects.filter(poll_id=poll_id, user__isnull=True)
        anon_vote = None
        if voter_key:
            anon_vote = qs.filter(voter_key=voter_key).first()
        if not anon_vote:
            anon_vote = qs.order_by("-created_at").first()
        if anon_vote:
            anon_vote.user = user
            anon_vote.save(update_fields=["user"])

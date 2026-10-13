from datetime import timedelta
from unittest import mock

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from accounts.models import User

from .models import Option, Poll, Vote
from .results import build_results, calculate_percentages
from .services import DAILY_POLL_LIMIT


def make_poll(author, question="Bugün sinemaya mı gitsem?", options=("Sinema", "Restoran"), **extra):
    poll = Poll.objects.create(author=author, question=question, **extra)
    for position, text in enumerate(options):
        Option.objects.create(poll=poll, text=text, position=position)
    return poll


class CreatePollTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("yazar", "yazar@example.com", "guclu-parola-123")

    def submit(self, options, question="Bugün sinemaya mı gitsem?"):
        self.client.force_login(self.user)
        return self.client.post(
            reverse("polls:create"),
            {"question": question, "description": "", "option": options},
        )

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse("polls:create"))
        self.assertRedirects(
            response, "/giris/?next=/anket/olustur/", fetch_redirect_response=False
        )

    def test_one_option_rejected(self):
        response = self.submit(["Sadece biri", ""])
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "En az 2 seçenek gerekli.")
        self.assertEqual(Poll.objects.count(), 0)

    def test_six_options_rejected(self):
        response = self.submit(["1", "2", "3", "4", "5", "6"])
        self.assertContains(response, "En fazla 5 seçenek")
        self.assertEqual(Poll.objects.count(), 0)

    def test_duplicate_options_rejected_case_insensitive(self):
        response = self.submit(["Sinema", "sinema"])
        self.assertContains(response, "Aynı seçeneği iki kez")
        self.assertEqual(Poll.objects.count(), 0)

    def test_short_question_rejected(self):
        response = self.submit(["A", "B"], question="Kısa")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Poll.objects.count(), 0)

    def test_blank_option_rows_are_ignored(self):
        response = self.submit(["Sinema", "", "Restoran", ""])
        poll = Poll.objects.get()
        self.assertRedirects(response, poll.get_absolute_url())
        self.assertEqual(
            list(poll.options.values_list("text", "position")), [("Sinema", 0), ("Restoran", 1)]
        )

    def test_daily_limit(self):
        for _ in range(DAILY_POLL_LIMIT):
            make_poll(self.user)
        response = self.submit(["A", "B"])
        self.assertContains(response, "Bugün en fazla 10 anket")
        self.assertEqual(Poll.objects.count(), DAILY_POLL_LIMIT)

    def test_form_works_without_js_with_two_inputs(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("polls:create"))
        self.assertContains(response, 'name="option"', count=3)  # 2 satır + şablon


class FeedTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("yazar", "yazar@example.com", "guclu-parola-123")

    def test_first_page_has_20_and_load_more_shows_rest(self):
        for _ in range(25):
            make_poll(self.user)
        first = self.client.get("/")
        self.assertContains(first, 'class="card poll-card"', count=20)
        self.assertContains(first, "Daha fazla göster")
        second = self.client.get("/?page=2")
        self.assertContains(second, 'class="card poll-card"', count=25)
        self.assertNotContains(second, "Daha fazla göster")

    def test_query_count_does_not_grow_with_poll_count(self):
        def count_queries(url):
            with CaptureQueriesContext(connection) as ctx:
                self.client.get(url)
            return len(ctx)

        for _ in range(3):
            make_poll(self.user)
        baselines = {url: count_queries(url) for url in ["/", "/?tab=populer", "/kullanici/yazar/"]}
        for _ in range(17):
            make_poll(self.user, options=("A", "B", "C"))
        for url, baseline in baselines.items():
            self.assertEqual(count_queries(url), baseline, url)

    def test_tabs(self):
        open_poll = make_poll(self.user, question="Açık anket sorusu burada")
        closed_poll = make_poll(self.user, question="Kapalı anket sorusu burada", status="closed")
        expired = make_poll(
            self.user,
            question="Süresi dolan anket sorusu",
            closes_at=timezone.now() - timedelta(hours=1),
        )
        new_page = self.client.get("/?tab=yeni").content.decode()
        self.assertIn(open_poll.question, new_page)
        self.assertNotIn(closed_poll.question, new_page)
        closed_page = self.client.get("/?tab=kapananlar").content.decode()
        self.assertIn(closed_poll.question, closed_page)
        self.assertIn(expired.question, closed_page)
        self.assertNotIn(open_poll.question, closed_page)

    def test_popular_orders_by_votes_in_last_7_days(self):
        old_favorite = make_poll(self.user, question="Eski favori anket sorusu")
        recent_favorite = make_poll(self.user, question="Yeni favori anket sorusu")
        for index in range(3):
            vote = Vote.objects.create(
                poll=old_favorite, option=old_favorite.options.first(), voter_key=f"o{index}"
            )
            Vote.objects.filter(pk=vote.pk).update(created_at=timezone.now() - timedelta(days=10))
        Vote.objects.create(
            poll=recent_favorite, option=recent_favorite.options.first(), voter_key="r"
        )
        page = self.client.get("/?tab=populer").content.decode()
        self.assertLess(page.index(recent_favorite.question), page.index(old_favorite.question))

    def test_invalid_tab_and_page_fall_back(self):
        make_poll(self.user)
        self.assertEqual(self.client.get("/?tab=bilinmeyen&page=abc").status_code, 200)

    def test_empty_state(self):
        response = self.client.get("/")
        self.assertContains(response, "Henüz anket yok. İlk kararsızlığını sen paylaş.")


class ResultsTests(TestCase):
    def test_percentages_always_sum_to_100(self):
        for counts in ([1, 1, 1], [3, 7], [1, 1, 1, 1, 1, 0][:5], [2, 1], [5, 5, 5, 5, 3]):
            self.assertEqual(sum(calculate_percentages(counts)), 100, counts)
        self.assertEqual(calculate_percentages([0, 0]), [0, 0])

    def test_badge_levels(self):
        user = User.objects.create_user("u", "u@example.com", "guclu-parola-123")
        poll = make_poll(user)
        self.assertEqual(build_results(poll)["badge_text"], "İlk oyu sen ver")
        cases = [((50, 50), "Kalabalık da kararsız"), ((60, 40), "Az farkla önde"), ((90, 10), "Karar net")]
        for (a, b), text in cases:
            Option.objects.filter(poll=poll, position=0).update(vote_count=a)
            Option.objects.filter(poll=poll, position=1).update(vote_count=b)
            poll = Poll.objects.prefetch_related("options").get(pk=poll.pk)
            self.assertEqual(build_results(poll)["badge_text"], text)


class DetailAndProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("yazar", "gizli@example.com", "guclu-parola-123")
        self.poll = make_poll(self.user, options=("A", "B", "C"))

    def test_detail_renders_and_hides_email(self):
        response = self.client.get(self.poll.get_absolute_url())
        self.assertContains(response, self.poll.question)
        self.assertNotContains(response, "gizli@example.com")

    def test_unknown_poll_404(self):
        self.assertEqual(self.client.get("/anket/yokboyle1234/").status_code, 404)

    def test_profile_lists_polls_with_stats_and_hides_email(self):
        Poll.objects.filter(pk=self.poll.pk).update(total_votes=7)
        response = self.client.get("/kullanici/Yazar/")
        self.assertContains(response, self.poll.question)
        self.assertContains(response, "@yazar")
        self.assertNotContains(response, "gizli@example.com")
        self.assertEqual(response.context["stats"], {"poll_count": 1, "votes_received": 7})

    def test_unknown_profile_404(self):
        self.assertEqual(self.client.get("/kullanici/yok/").status_code, 404)

    def test_home_hides_email(self):
        self.assertNotContains(self.client.get("/"), "gizli@example.com")


JSON = {"Accept": "application/json"}


class VotingTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("yazar", "yazar@example.com", "guclu-parola-123")
        self.voter = User.objects.create_user("oyuncu", "oyuncu@example.com", "guclu-parola-123")
        self.poll = make_poll(self.author, options=("Sinema", "Restoran", "Park"))
        self.options = list(self.poll.options.all())
        self.vote_url = reverse("polls:vote", args=[self.poll.public_id])

    def vote(self, option, **kwargs):
        option_id = option.id if hasattr(option, "id") else option
        return self.client.post(self.vote_url, {"option_id": option_id}, headers=JSON, **kwargs)

    def counts(self):
        self.poll.refresh_from_db()
        return self.poll.total_votes, [o.vote_count for o in self.poll.options.all()]

    def test_anonymous_vote_succeeds_and_counters_increase(self):
        response = self.vote(self.options[1])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.counts(), (1, [0, 1, 0]))
        vote = Vote.objects.get()
        self.assertIsNone(vote.user)
        self.assertEqual(len(vote.voter_key), 64)
        self.assertEqual(response.json()["results"]["voted_option_id"], self.options[1].id)

    def test_second_anonymous_vote_same_session_is_409(self):
        self.vote(self.options[0])
        response = self.vote(self.options[1])
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.counts(), (1, [1, 0, 0]))
        self.assertIsNotNone(response.json()["results"])

    def test_second_vote_by_same_user_is_409(self):
        self.client.force_login(self.voter)
        self.assertEqual(self.vote(self.options[0]).status_code, 200)
        self.assertEqual(self.vote(self.options[2]).status_code, 409)
        self.assertEqual(self.counts(), (1, [1, 0, 0]))

    def test_race_hits_database_constraint_and_counts_once(self):
        self.client.force_login(self.voter)
        self.vote(self.options[0])
        with mock.patch("polls.services.has_voted", return_value=False):
            response = self.vote(self.options[1])
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.counts(), (1, [1, 0, 0]))

    def test_option_from_other_poll_is_400(self):
        other = make_poll(self.author, question="Başka bir anketin sorusu")
        response = self.vote(other.options.first())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Vote.objects.count(), 0)

    def test_garbage_option_id_is_400(self):
        for value in ["abc", "", "99999"]:
            self.assertEqual(self.vote(value).status_code, 400, value)

    def test_closed_poll_vote_is_403(self):
        self.poll.status = Poll.Status.CLOSED
        self.poll.save()
        response = self.vote(self.options[0])
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Vote.objects.count(), 0)

    def test_expired_poll_vote_is_403(self):
        Poll.objects.filter(pk=self.poll.pk).update(closes_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self.vote(self.options[0]).status_code, 403)

    def test_vote_requires_post(self):
        self.assertEqual(self.client.get(self.vote_url).status_code, 405)

    def test_form_post_without_js_redirects_to_detail(self):
        response = self.client.post(self.vote_url, {"option_id": self.options[0].id})
        self.assertRedirects(response, self.poll.get_absolute_url())
        self.assertEqual(self.counts()[0], 1)

    def test_author_can_vote_on_own_poll(self):
        self.client.force_login(self.author)
        self.assertEqual(self.vote(self.options[0]).status_code, 200)

    def test_session_remembers_voted_poll(self):
        self.vote(self.options[0])
        self.assertEqual(self.client.session["voted_polls"], [self.poll.id])

    def test_csrf_is_enforced(self):
        from django.test import Client

        strict = Client(enforce_csrf_checks=True)
        response = strict.post(self.vote_url, {"option_id": self.options[0].id})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Vote.objects.count(), 0)


class ResultVisibilityTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("yazar", "yazar@example.com", "guclu-parola-123")
        self.poll = make_poll(self.author, options=("Sinema", "Restoran"))
        Option.objects.filter(poll=self.poll, position=0).update(vote_count=3)
        Option.objects.filter(poll=self.poll, position=1).update(vote_count=7)
        Poll.objects.filter(pk=self.poll.pk).update(total_votes=10)
        self.url = self.poll.get_absolute_url()
        self.results_url = reverse("polls:results", args=[self.poll.public_id])

    def test_percentages_hidden_before_voting_but_total_visible(self):
        response = self.client.get(self.url)
        self.assertContains(response, "10")
        self.assertContains(response, "kişi oy verdi")
        self.assertNotContains(response, "%30")
        self.assertNotContains(response, "%70")
        self.assertContains(response, 'name="option_id"', count=2)

    def test_results_json_hides_numbers_before_voting(self):
        data = self.client.get(self.results_url).json()
        self.assertEqual(data["total"], 10)
        self.assertIsNone(data["voted_option_id"])
        for option in data["options"]:
            self.assertIsNone(option["count"])
            self.assertIsNone(option["percent"])

    def test_feed_card_hides_bar_before_voting_and_shows_after(self):
        before = self.client.get("/").content.decode()
        self.assertNotIn("decision-bar__segment", before)
        self.client.post(
            reverse("polls:vote", args=[self.poll.public_id]),
            {"option_id": self.poll.options.first().id},
        )
        after = self.client.get("/").content.decode()
        self.assertIn("decision-bar__segment", after)

    def test_after_voting_percentages_show_and_no_vote_buttons(self):
        option = self.poll.options.first()
        self.client.post(reverse("polls:vote", args=[self.poll.public_id]), {"option_id": option.id})
        response = self.client.get(self.url)
        self.assertContains(response, "%36")
        self.assertContains(response, "%64")
        self.assertNotContains(response, 'name="option_id"')
        self.assertContains(response, "option-row--mine")

    def test_reload_after_voting_shows_results_and_blocks_revote(self):
        option = self.poll.options.first()
        self.client.post(reverse("polls:vote", args=[self.poll.public_id]), {"option_id": option.id})
        self.assertContains(self.client.get(self.url), "option-row--revealed")
        response = self.client.post(
            reverse("polls:vote", args=[self.poll.public_id]), {"option_id": option.id}, headers=JSON
        )
        self.assertEqual(response.status_code, 409)

    def test_closed_poll_shows_results_and_no_vote_buttons(self):
        self.poll.status = Poll.Status.CLOSED
        self.poll.save()
        response = self.client.get(self.url)
        self.assertContains(response, "%30")
        self.assertContains(response, "%70")
        self.assertContains(response, "Bu anket kapandı.")
        self.assertNotContains(response, 'name="option_id"')

    def test_author_sees_results_without_voting_and_can_still_vote(self):
        self.client.force_login(self.author)
        response = self.client.get(self.url)
        self.assertContains(response, "%30")
        self.assertContains(response, 'name="option_id"', count=2)

    def test_results_json_shape_and_no_leaks(self):
        voter = User.objects.create_user("oyuncu", "gizli-oyuncu@example.com", "guclu-parola-123")
        self.client.force_login(voter)
        option = self.poll.options.first()
        self.client.post(reverse("polls:vote", args=[self.poll.public_id]), {"option_id": option.id})
        response = self.client.get(self.results_url)
        data = response.json()
        self.assertEqual(
            set(data), {"total", "options", "voted_option_id", "is_open", "badge_level", "badge_text"}
        )
        self.assertEqual(data["total"], 11)
        self.assertEqual(data["voted_option_id"], option.id)
        self.assertEqual(sum(o["percent"] for o in data["options"]), 100)
        for option_data in data["options"]:
            self.assertEqual(set(option_data), {"id", "text", "count", "percent"})
        body = response.content.decode()
        self.assertNotIn("@", body)
        self.assertNotIn("user", body.lower())
        self.assertNotIn(voter.username, body)
        self.assertNotIn(voter.email, body)

    def test_feed_query_count_is_constant_for_logged_in_voter(self):
        voter = User.objects.create_user("oyuncu", "o@example.com", "guclu-parola-123")
        self.client.force_login(voter)

        def count_queries():
            with CaptureQueriesContext(connection) as ctx:
                self.client.get("/")
            return len(ctx)

        for _ in range(2):
            make_poll(self.author, question="Ek anket sorusu burada")
        baseline = count_queries()
        for _ in range(15):
            make_poll(self.author, question="Ek anket sorusu burada", options=("A", "B", "C"))
        self.assertEqual(count_queries(), baseline)


class OwnerActionTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("yazar", "yazar@example.com", "guclu-parola-123")
        self.other = User.objects.create_user("baskasi", "baska@example.com", "guclu-parola-123")
        self.poll = make_poll(self.author)
        self.close_url = reverse("polls:close", args=[self.poll.public_id])
        self.delete_url = reverse("polls:delete", args=[self.poll.public_id])

    def test_owner_can_close(self):
        self.client.force_login(self.author)
        response = self.client.post(self.close_url)
        self.assertRedirects(response, self.poll.get_absolute_url())
        self.poll.refresh_from_db()
        self.assertEqual(self.poll.status, Poll.Status.CLOSED)

    def test_non_owner_cannot_close_or_delete(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.close_url).status_code, 403)
        self.assertEqual(self.client.post(self.delete_url).status_code, 403)
        self.assertEqual(self.client.get(self.delete_url).status_code, 403)
        self.poll.refresh_from_db()
        self.assertEqual(self.poll.status, Poll.Status.ACTIVE)

    def test_anonymous_redirected_to_login(self):
        response = self.client.post(self.close_url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("/giris/"))
        self.assertTrue(Poll.objects.filter(pk=self.poll.pk).exists())

    def test_close_requires_post(self):
        self.client.force_login(self.author)
        self.assertEqual(self.client.get(self.close_url).status_code, 405)

    def test_delete_has_confirmation_step_then_deletes(self):
        self.client.force_login(self.author)
        confirm = self.client.get(self.delete_url)
        self.assertContains(confirm, "Evet, anketi sil")
        self.assertTrue(Poll.objects.filter(pk=self.poll.pk).exists())
        response = self.client.post(self.delete_url)
        self.assertRedirects(response, "/")
        self.assertFalse(Poll.objects.filter(pk=self.poll.pk).exists())

    def test_owner_controls_only_visible_to_owner(self):
        url = self.poll.get_absolute_url()
        self.assertNotContains(self.client.get(url), "Anketi kapat")
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(url), "Anketi kapat")
        self.client.force_login(self.author)
        self.assertContains(self.client.get(url), "Anketi kapat")

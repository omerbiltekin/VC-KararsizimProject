from datetime import timedelta

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

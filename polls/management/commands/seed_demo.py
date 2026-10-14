import hashlib
import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from accounts.models import User
from polls.models import Option, Poll, Vote

DEMO_USERS = ["yigitb", "kardelenb", "emree", "ilyaso"]
DEMO_PASSWORD = "demohesap3577!"

QUESTIONS = [
    ("Bugün sinemaya mı gitsem, restorana mı?", ["Sinema", "Restoran"]),
    ("Hafta sonu tatili için hangisi?", ["Deniz", "Dağ", "Şehir turu"]),
    ("Sabah kahvesi mi, çay mı?", ["Kahve", "Çay"]),
    ("Yeni telefon alırken en önemli şey ne?", ["Kamera", "Pil", "Fiyat", "Marka"]),
    ("Akşam yemeğinde ne yesek acaba?", ["Pizza", "Köfte", "Makarna", "Sushi", "Kebap"]),
    ("Kış mı yaz mı daha güzel?", ["Kış", "Yaz"]),
    ("Çalışırken müzik dinlemeli miyim?", ["Evet", "Hayır", "Sadece enstrümantal"]),
    ("Yeni bir dil öğrenmek istiyorum, hangisi?", ["İspanyolca", "Almanca", "Japonca"]),
    ("Evcil hayvan alsam hangisi olsun?", ["Kedi", "Köpek", "Balık", "Kuş"]),
    ("Sabah sporu mu, akşam sporu mu?", ["Sabah", "Akşam"]),
    ("Bu yıl hangi kitabı okumalıyım?", ["Roman", "Bilim kurgu", "Tarih", "Kişisel gelişim"]),
    ("Toplantı için en uygun gün hangisi?", ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma"]),
]


class Command(BaseCommand):
    help = "Demo kullanıcılar, anketler ve rastgele oylar üretir."

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(42)
        now = timezone.now()

        users = []
        for username in DEMO_USERS:
            user, _ = User.objects.get_or_create(
                username=username, defaults={"email": f"{username}@example.com"}
            )
            user.set_password(DEMO_PASSWORD)
            user.save()
            users.append(user)

        Poll.objects.filter(author__in=users).delete()

        for index, (question, option_texts) in enumerate(QUESTIONS):
            poll = Poll.objects.create(
                question=question,
                author=users[index % len(users)],
                status=Poll.Status.CLOSED if index % 6 == 5 else Poll.Status.ACTIVE,
            )
            Poll.objects.filter(pk=poll.pk).update(
                created_at=now - timedelta(hours=index * 7)
            )
            options = [
                Option.objects.create(poll=poll, text=text, position=position)
                for position, text in enumerate(option_texts)
            ]

            voting_users = rng.sample(users, rng.randint(0, len(users)))
            for voter in voting_users:
                self._vote(poll, rng.choice(options), voter, f"user-{voter.pk}")
            for n in range(rng.randint(0, 30)):
                self._vote(poll, rng.choice(options), None, f"anon-{poll.pk}-{n}")

        self.stdout.write(
            self.style.SUCCESS(
                f"{len(users)} kullanıcı, {len(QUESTIONS)} anket hazır. "
                f"Demo parola: {DEMO_PASSWORD}"
            )
        )

    def _vote(self, poll, option, user, key_source):
        Vote.objects.create(
            poll=poll,
            option=option,
            user=user,
            voter_key=hashlib.sha256(key_source.encode()).hexdigest(),
        )
        Option.objects.filter(pk=option.pk).update(vote_count=F("vote_count") + 1)
        Poll.objects.filter(pk=poll.pk).update(total_votes=F("total_votes") + 1)

from django.test import TestCase
from django.urls import reverse

from .models import User


class RegisterTests(TestCase):
    def post_register(self, follow=False, **overrides):
        data = {
            "username": "yeni_kisi",
            "email": "yeni@example.com",
            "password1": "guclu-parola-123",
            "password2": "guclu-parola-123",
        }
        data.update(overrides)
        return self.client.post(reverse("accounts:register"), data, follow=follow)

    def test_duplicate_email_rejected(self):
        User.objects.create_user("ilk", "ayni@example.com", "guclu-parola-123")
        response = self.post_register(email="AYNI@example.com")
        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["form"].errors)
        self.assertEqual(User.objects.count(), 1)

    def test_username_case_insensitive_conflict(self):
        User.objects.create_user("KullaniAdi", "a@example.com", "guclu-parola-123")
        response = self.post_register(username="kullaniadi", email="b@example.com")
        self.assertIn("username", response.context["form"].errors)
        self.assertEqual(User.objects.count(), 1)

    def test_invalid_username_characters_rejected(self):
        for bad in ["ab", "bosluk var", "türkçe", "a" * 21, "nokta.var"]:
            response = self.post_register(username=bad)
            self.assertIn("username", response.context["form"].errors, bad)
        self.assertEqual(User.objects.count(), 0)

    def test_reserved_username_rejected(self):
        response = self.post_register(username="Admin")
        self.assertIn("username", response.context["form"].errors)

    def test_successful_register_logs_in_and_hides_email(self):
        response = self.post_register(follow=True)
        self.assertRedirects(response, "/")
        self.assertContains(response, "@yeni_kisi")
        self.assertContains(response, "Hoş geldin, @yeni_kisi")
        self.assertNotContains(response, "yeni@example.com")

    def test_email_is_lowercased(self):
        self.post_register(email="Buyuk@Example.com")
        self.assertEqual(User.objects.get().email, "buyuk@example.com")


class LoginLogoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("giren", "giren@example.com", "guclu-parola-123")

    def test_login_with_next(self):
        response = self.client.post(
            reverse("accounts:login") + "?next=/anket/olustur/",
            {"username": "giren", "password": "guclu-parola-123", "next": "/anket/olustur/"},
        )
        self.assertRedirects(response, "/anket/olustur/", fetch_redirect_response=False)

    def test_login_page_shows_create_notice(self):
        response = self.client.get("/giris/?next=/anket/olustur/")
        self.assertContains(response, "Anket oluşturmak için giriş yapman gerekiyor")
        self.assertNotContains(self.client.get("/giris/"), "Anket oluşturmak için")

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/cikis/").status_code, 405)
        response = self.client.post("/cikis/")
        self.assertRedirects(response, "/")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_header_state(self):
        anonymous = self.client.get("/")
        self.assertContains(anonymous, "Giriş yap")
        self.assertContains(anonymous, "Kayıt ol")
        self.client.force_login(self.user)
        logged_in = self.client.get("/")
        self.assertContains(logged_in, "Anket oluştur")
        self.assertNotContains(logged_in, "giren@example.com")

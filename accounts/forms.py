from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User

RESERVED_USERNAMES = {
    "admin", "root", "api", "static", "anket", "giris", "kayit", "cikis", "kullanici", "hakkinda",
}


class RegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "email")

    def clean_username(self):
        username = self.cleaned_data["username"]
        if username.lower() in RESERVED_USERNAMES:
            raise forms.ValidationError("Bu kullanıcı adı kullanılamaz.")
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Bu kullanıcı adı alınmış.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Bu e-posta ile zaten bir hesap var.")
        return email

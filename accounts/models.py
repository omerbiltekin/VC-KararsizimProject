from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models

username_validator = RegexValidator(
    regex=r"^[a-zA-Z0-9_]{3,20}$",
    message="Kullanıcı adı 3–20 karakter olmalı; sadece harf, rakam ve alt çizgi içerebilir.",
)


class User(AbstractUser):
    username = models.CharField(
        max_length=20,
        unique=True,
        validators=[username_validator],
        error_messages={"unique": "Bu kullanıcı adı alınmış."},
    )
    email = models.EmailField(
        unique=True,
        error_messages={"unique": "Bu e-posta ile zaten bir hesap var."},
    )

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username

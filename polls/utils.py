import hashlib
import secrets
import string

from django.conf import settings

PUBLIC_ID_ALPHABET = string.ascii_letters + string.digits
PUBLIC_ID_LENGTH = 10


def generate_public_id():
    return "".join(secrets.choice(PUBLIC_ID_ALPHABET) for _ in range(PUBLIC_ID_LENGTH))


def _hash_session_key(session_key):
    return hashlib.sha256((session_key + settings.VOTER_KEY_SALT).encode()).hexdigest()


def existing_voter_key(request):
    """Oturum yoksa oturum oluşturmaz; sadece okuma isteklerinde kullanılır."""
    session_key = request.session.session_key
    return _hash_session_key(session_key) if session_key else None


def get_voter_key(request):
    if not request.session.session_key:
        request.session.save()
    return _hash_session_key(request.session.session_key)

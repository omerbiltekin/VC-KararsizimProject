import time
from django.core.cache import cache


def get_client_ip(request):
    """İstek yapan kullanıcının IP adresini döner."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "127.0.0.1")


def is_rate_limited(key: str, limit: int, period: int) -> bool:
    """
    Belirli bir anahtar için belirli bir zaman diliminde (period saniye)
    istek sayısının limit değerini aşıp aşmadığını denetler.
    Django Cache altyapısını kullanır.
    """
    now = int(time.time())
    cache_key = f"ratelimit:{key}:{now // period}"
    try:
        # Anahtar yoksa 1 ile başlat, varsa artır
        added = cache.add(cache_key, 1, timeout=period + 10)
        if not added:
            count = cache.incr(cache_key)
            if count > limit:
                return True
        return False
    except Exception:
        # Cache backend hatası durumunda kullanıcıyı engelleme (fail open)
        return False

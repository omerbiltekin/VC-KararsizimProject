"""Sonuç gösterimi için saf hesaplamalar (veritabanı sorgusu yapmaz, prefetch'e güvenir)."""

BADGE_EMPTY = "İlk oyu sen ver"
BADGE_TIE = "Kalabalık da kararsız"
BADGE_CLOSE = "Az farkla önde"
BADGE_CLEAR = "Karar net"


def calculate_percentages(counts):
    total = sum(counts)
    if total == 0:
        return [0] * len(counts)
    percents = [round(count * 100 / total) for count in counts]
    difference = 100 - sum(percents)
    if difference:
        percents[counts.index(max(counts))] += difference
    return percents


def _badge(percents, total):
    if total == 0:
        return "empty", BADGE_EMPTY
    ranked = sorted(percents, reverse=True)
    gap = ranked[0] - (ranked[1] if len(ranked) > 1 else 0)
    if gap <= 5:
        return "tie", BADGE_TIE
    if gap <= 20:
        return "close", BADGE_CLOSE
    return "clear", BADGE_CLEAR


def build_results(poll):
    options = list(poll.options.all())
    counts = [option.vote_count for option in options]
    total = sum(counts)
    percents = calculate_percentages(counts)
    level, text = _badge(percents, total)
    return {
        "total": total,
        "options": [
            {
                "id": option.id,
                "text": option.text,
                "position": option.position,
                "count": option.vote_count,
                "percent": percent,
            }
            for option, percent in zip(options, percents)
        ],
        "badge_level": level,
        "badge_text": text,
    }


def attach_results(polls):
    for poll in polls:
        poll.results = build_results(poll)
    return polls

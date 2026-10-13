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


def build_results(poll, reveal=True):
    """reveal=False iken sayı ve yüzde hiç üretilmez; şablona sızamaz."""
    options = list(poll.options.all())
    counts = [option.vote_count for option in options]
    total = sum(counts)
    percents = calculate_percentages(counts)
    level, text = _badge(percents, total)

    rows = []
    for option, percent in zip(options, percents):
        row = {"id": option.id, "text": option.text, "position": option.position}
        if reveal:
            row.update(count=option.vote_count, percent=percent)
        rows.append(row)

    return {
        "total": total,
        "reveal": reveal,
        "options": rows,
        "badge_level": level,
        "badge_text": text,
    }


def can_see_results(poll, *, viewer_id, voted):
    return (not poll.is_open) or voted or poll.author_id == viewer_id


def attach_results(polls, *, viewer_id=None, voted_poll_ids=frozenset()):
    for poll in polls:
        reveal = can_see_results(
            poll, viewer_id=viewer_id, voted=poll.id in voted_poll_ids
        )
        poll.results = build_results(poll, reveal=reveal)
    return polls


def results_payload(poll, *, voted_option_id, reveal):
    results = build_results(poll, reveal=reveal)
    return {
        "total": results["total"],
        "options": [
            {
                "id": row["id"],
                "text": row["text"],
                "count": row.get("count"),
                "percent": row.get("percent"),
            }
            for row in results["options"]
        ],
        "voted_option_id": voted_option_id,
        "is_open": poll.is_open,
        "badge_level": results["badge_level"],
        "badge_text": results["badge_text"],
    }

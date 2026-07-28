"""
Detects new chapters for a user's followed manga and turns them into
Notification rows. There's no background worker/cron in this project, so
this runs lazily — triggered from a context processor, throttled to at
most once every few minutes per user (see context_processors.py).
"""
from . import services
from .services import MangaDexError
from .models import Bookmark, Notification


def _backfill_missing_flags(user, limit=20):
    """One-time self-heal for notifications created before the 'flag'
    field existed — fills in the flag on the most recent unread/flag-less
    rows so old notifications get a flag too, not just future ones."""
    from django.db.models import Q
    stale = Notification.objects.filter(
        Q(user=user) & (Q(flag__isnull=True) | Q(flag=""))
    ).order_by("-created_at")[:limit]
    for notif in stale:
        try:
            info = services.get_chapter_info(notif.chapter_id)
        except MangaDexError:
            continue
        notif.flag = services.LANGUAGE_COUNTRY_CODES.get(info.get("language"), "xx")
        notif.save(update_fields=["flag"])


def check_new_chapters_for_user(user):
    _backfill_missing_flags(user)
    follows = Bookmark.objects.filter(user=user, kind=Bookmark.FOLLOW)

    for bookmark in follows:
        try:
            chapters = services.get_manga_chapters(bookmark.manga_id)
        except MangaDexError:
            continue
        if not chapters:
            continue

        latest = chapters[-1]  # get_manga_chapters() is sorted ascending

        if bookmark.last_known_chapter is None:
            # First time we've checked this follow — just record the
            # current latest chapter as the baseline, don't notify
            # (otherwise every existing chapter would "ping" on first follow).
            bookmark.last_known_chapter = latest["chapter"]
            bookmark.save(update_fields=["last_known_chapter"])
            continue

        if latest["chapter"] != bookmark.last_known_chapter:
            Notification.objects.get_or_create(
                user=user,
                manga_id=bookmark.manga_id,
                chapter_id=latest["id"],
                defaults={
                    "manga_title": bookmark.manga_title,
                    "cover_url": bookmark.cover_url,
                    "chapter_number": latest["chapter"],
                    "flag": services.LANGUAGE_COUNTRY_CODES.get(latest.get("language"), "xx"),
                },
            )
            bookmark.last_known_chapter = latest["chapter"]
            bookmark.save(update_fields=["last_known_chapter"])
from django.core.cache import cache

from . import services


def nav_genres(request):
    """A short slice of MangaDex genre tags for the navbar 'Thể loại' dropdown.
    Full list lives at /the-loai/. Fails silently (empty list) if the
    MangaDex API is unreachable, so it never breaks page rendering.
    """
    try:
        tags = services.get_all_tags()
    except services.MangaDexError:
        return {"nav_genres": []}
    genres_only = [t for t in tags if t["group"] == "genre"]
    return {"nav_genres": genres_only[:14]}


def site_settings(request):
    """Exposes the navbar 'Cài đặt' options (origin country + reader page
    size) and the user's current picks (stored in session) to every
    template, so the dropdown can be built and pre-selected anywhere."""
    return {
        "origin_countries": services.ORIGIN_COUNTRIES,
        "page_size_options": services.PAGE_SIZE_OPTIONS,
        "current_origin_country": request.session.get("origin_country", "all"),
        "current_reader_page_size": request.session.get("reader_page_size", "medium"),
    }


def notifications(request):
    """Exposes unread-notification count + a short recent list to every
    template (navbar bell icon). The actual 'check MangaDex for new
    chapters on followed manga' scan is throttled to at most once every
    10 minutes per user, so it doesn't slow down every page load."""
    if not request.user.is_authenticated:
        return {"unread_notif_count": 0, "recent_notifications": []}

    throttle_key = f"notif_check:{request.user.id}"
    if cache.get(throttle_key) is None:
        from .notifications import check_new_chapters_for_user
        try:
            check_new_chapters_for_user(request.user)
        except Exception:
            pass  # never let a notification-check failure break page rendering
        cache.set(throttle_key, True, 600)

    from .models import Notification
    qs = Notification.objects.filter(user=request.user)
    return {
        "unread_notif_count": qs.filter(is_read=False).count(),
        "recent_notifications": qs[:8],
    }
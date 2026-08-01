from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.db.models import Count
from django.urls import reverse
from urllib.parse import quote
import json
import re
from urllib.parse import urlparse
from django.utils.html import escape
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError as DjangoValidationError

from . import services
from .services import MangaDexError, ORIGIN_COUNTRIES, PAGE_SIZE_OPTIONS
from .models import Bookmark, ReadingHistory, ReadChapter, Notification, DiscussionGroup, GroupMembership, GroupMessage
from .forms import ProfileForm, GroupCreateForm, GroupMessageForm


def _origin_lang(request):
    return request.session.get("origin_country", "all")


def _build_hero_columns(covers, num_columns=9, tile_repeats=3):
    """Splits cover URLs round-robin into N vertical columns for the hero
    background, then duplicates each column's content (so translateY(-50%)
    loops back to an identical starting point — a seamless infinite
    vertical scroll instead of a visible jump/reset)."""
    urls = [m["cover_url"] for m in covers if m.get("cover_url")]
    if not urls:
        return []

    columns = [[] for _ in range(num_columns)]
    for i, url in enumerate(urls):
        columns[i % num_columns].append(url)
    for col in columns:
        if not col:
            col.extend(urls[:3])

    return [(col * tile_repeats) * 2 for col in columns if col]


def home(request):
    error = None
    trending, latest, popular_new = [], [], []
    hero_columns = []
    origin = _origin_lang(request)
    try:
        trending = services.get_popular_manga(limit=18, origin_language=origin)["items"]
        latest = services.get_latest_updates(limit=12, origin_language=origin)
        popular_new = services.get_popular_new_titles(limit=10, origin_language=origin)
        hero_pool = services.get_popular_manga(limit=40, origin_language=origin)["items"]
        hero_columns = _build_hero_columns(hero_pool, num_columns=9, tile_repeats=3)
    except MangaDexError as exc:
        error = str(exc)

    context = {
        "trending": trending,
        "latest": latest,
        "popular_new": popular_new,
        "error": error,
        "hero_columns": hero_columns,
    }
    return render(request, "reader/home.html", context)


PAGE_LIMIT = 24


def hot(request):
    """Paginated grid of the most-followed manga on MangaDex right now."""
    error = None
    results, total_pages, page = [], 1, 1
    try:
        page = max(1, int(request.GET.get("page", 1)))
    except ValueError:
        page = 1
    try:
        data = services.get_popular_manga(
            limit=PAGE_LIMIT, origin_language=_origin_lang(request), offset=(page - 1) * PAGE_LIMIT
        )
        results = data["items"]
        total_pages = max(1, -(-data["total"] // PAGE_LIMIT))  # ceil division
        page = min(page, total_pages)
    except MangaDexError as exc:
        error = str(exc)

    return render(request, "reader/manga_list.html", {
        "title": "🔥 Truyện Hot",
        "results": results,
        "error": error,
        "current_page": page,
        "total_pages": total_pages,
        "page_range": services.build_page_range(page, total_pages),
    })


def search_suggest(request):
    """JSON endpoint powering the live search-as-you-type dropdown in the
    navbar. Returns a handful of matches — the full results page is still
    /tim-kiem/?q=... for anything beyond a quick peek."""
    query = request.GET.get("q", "").strip()
    if len(query) < 2:
        return JsonResponse({"results": [], "total": 0})

    try:
        data = services.search_manga(query, limit=6, origin_language=_origin_lang(request))
    except MangaDexError:
        return JsonResponse({"results": [], "total": 0})

    results = [{
        "id": m["id"],
        "title": m["title"],
        "cover_url": m["cover_url"],
        "authors": m["authors"][:2],
        "tags": [t["name"] for t in m["tags"][:4]],
        "url": reverse("reader:manga_detail", args=[m["id"]]),
    } for m in data["items"]]

    return JsonResponse({"results": results, "total": data["total"]})


def search(request):
    query = request.GET.get("q", "").strip()
    results, error = [], None
    total_pages, page = 1, 1
    has_restricted = False
    try:
        page = max(1, int(request.GET.get("page", 1)))
    except ValueError:
        page = 1
    if query:
        try:
            data = services.search_manga(
                query, limit=PAGE_LIMIT, origin_language=_origin_lang(request), offset=(page - 1) * PAGE_LIMIT
            )
            results = data["items"]
            total_pages = max(1, -(-data["total"] // PAGE_LIMIT))
            page = min(page, total_pages)
            if not results:
                has_restricted = services.has_restricted_matches(query)
        except MangaDexError as exc:
            error = str(exc)
    return render(request, "reader/search.html", {
        "query": query,
        "results": results,
        "error": error,
        "current_page": page,
        "total_pages": total_pages,
        "page_range": services.build_page_range(page, total_pages),
        "query_prefix": f"q={quote(query)}&" if query else "",
        "has_restricted": has_restricted,
    })


STATUS_OPTIONS = [
    {"code": "ongoing", "label": "Đang tiến hành"},
    {"code": "completed", "label": "Hoàn thành"},
    {"code": "hiatus", "label": "Tạm ngưng"},
    {"code": "cancelled", "label": "Đã hủy"},
]
DEMOGRAPHIC_OPTIONS = [
    {"code": "shounen", "label": "Shounen"},
    {"code": "shoujo", "label": "Shoujo"},
    {"code": "seinen", "label": "Seinen"},
    {"code": "josei", "label": "Josei"},
    {"code": "none", "label": "Không xác định"},
]
SORT_OPTIONS = [
    {"code": "relevance", "label": "Mức độ liên quan"},
    {"code": "latestUploadedChapter", "label": "Mới cập nhật"},
    {"code": "title", "label": "Tên (A-Z)"},
    {"code": "followedCount", "label": "Lượt theo dõi"},
    {"code": "createdAt", "label": "Ngày thêm"},
    {"code": "rating", "label": "Đánh giá"},
]


def advanced_search(request):
    error = None
    tags = []
    try:
        tags = services.get_all_tags()
    except MangaDexError as exc:
        error = str(exc)
    grouped_tags = {}
    for t in tags:
        grouped_tags.setdefault(t["group"], []).append(t)

    title = request.GET.get("title", "").strip()
    statuses = request.GET.getlist("status")
    demographics = request.GET.getlist("demographic")
    content_ratings = request.GET.getlist("content_rating") or ["safe", "suggestive"]
    included_tags = request.GET.getlist("include_tag")
    excluded_tags = request.GET.getlist("exclude_tag")
    included_mode = request.GET.get("include_mode", "AND")
    excluded_mode = request.GET.get("exclude_mode", "OR")
    order_by = request.GET.get("order_by") or ("relevance" if title else "followedCount")
    order_dir = request.GET.get("order_dir", "desc")

    try:
        page = max(1, int(request.GET.get("page", 1)))
    except ValueError:
        page = 1

    has_filters = bool(title or statuses or demographics or included_tags or excluded_tags)
    results, total_pages = [], 1

    if has_filters:
        try:
            data = services.advanced_search({
                "title": title,
                "statuses": statuses,
                "demographics": demographics,
                "content_ratings": content_ratings,
                "included_tags": included_tags,
                "excluded_tags": excluded_tags,
                "included_mode": included_mode,
                "excluded_mode": excluded_mode,
                "order_by": order_by,
                "order_dir": order_dir,
            }, limit=PAGE_LIMIT, offset=(page - 1) * PAGE_LIMIT)
            results = data["items"]
            total_pages = max(1, -(-data["total"] // PAGE_LIMIT))
            page = min(page, total_pages)
        except MangaDexError as exc:
            error = str(exc)

    # Preserve every current filter (except 'page') when building
    # pagination links, without having to name each field individually.
    query_params = request.GET.copy()
    query_params.pop("page", None)
    query_prefix = f"{query_params.urlencode()}&" if query_params else ""

    return render(request, "reader/advanced_search.html", {
        "grouped_tags": grouped_tags,
        "status_options": STATUS_OPTIONS,
        "demographic_options": DEMOGRAPHIC_OPTIONS,
        "sort_options": SORT_OPTIONS,
        "title": title,
        "selected_statuses": statuses,
        "selected_demographics": demographics,
        "selected_content_ratings": content_ratings,
        "included_tags": included_tags,
        "excluded_tags": excluded_tags,
        "included_mode": included_mode,
        "excluded_mode": excluded_mode,
        "order_by": order_by,
        "order_dir": order_dir,
        "results": results,
        "has_filters": has_filters,
        "error": error,
        "current_page": page,
        "total_pages": total_pages,
        "page_range": services.build_page_range(page, total_pages),
        "query_prefix": query_prefix,
    })


def genre_list(request):
    error = None
    tags = []
    try:
        tags = services.get_all_tags()
    except MangaDexError as exc:
        error = str(exc)
    grouped = {}
    for t in tags:
        grouped.setdefault(t["group"], []).append(t)
    return render(request, "reader/genre_list.html", {
        "grouped": grouped,
        "error": error,
    })


def genre_detail(request, tag_id):
    error = None
    results, tag_name = [], None
    total_pages, page = 1, 1
    try:
        page = max(1, int(request.GET.get("page", 1)))
    except ValueError:
        page = 1
    try:
        tag_name = services.get_tag_name(tag_id)
        data = services.browse_manga_by_tag(
            tag_id, limit=PAGE_LIMIT, offset=(page - 1) * PAGE_LIMIT, origin_language=_origin_lang(request)
        )
        results = data["items"]
        total_pages = max(1, -(-data["total"] // PAGE_LIMIT))
        page = min(page, total_pages)
    except MangaDexError as exc:
        error = str(exc)
    return render(request, "reader/manga_list.html", {
        "title": f"📂 Thể loại: {tag_name or ''}",
        "results": results,
        "error": error,
        "current_page": page,
        "total_pages": total_pages,
        "page_range": services.build_page_range(page, total_pages),
    })


def manga_detail(request, manga_id):
    error = None
    manga, chapters, chapter_groups = None, [], []
    try:
        manga = services.get_manga_detail(manga_id)
        chapters = services.get_manga_chapters(manga_id)
        chapter_groups = services.get_manga_chapters_grouped(manga_id)
    except MangaDexError as exc:
        error = str(exc)

    if manga is None and not error:
        messages.error(request, "Không tìm thấy truyện này.")
        return redirect("reader:home")

    if manga:
        try:
            manga["stats"] = services.get_manga_statistics(manga_id)
        except MangaDexError:
            manga["stats"] = None

    recommendations = []
    if manga and manga.get("tags"):
        try:
            top_tag_id = manga["tags"][0]["id"]
            rec_data = services.browse_manga_by_tag(top_tag_id, limit=7)
            recommendations = [m for m in rec_data["items"] if m["id"] != manga_id][:6]
        except MangaDexError:
            pass

    volume_index = services.build_volume_index(chapter_groups)

    is_following = is_favorited = False
    continue_reading = None
    read_chapter_ids = set()
    if request.user.is_authenticated and manga:
        is_following = Bookmark.objects.filter(user=request.user, kind=Bookmark.FOLLOW, manga_id=manga_id).exists()
        is_favorited = Bookmark.objects.filter(user=request.user, kind=Bookmark.FAVORITE, manga_id=manga_id).exists()
        continue_reading = ReadingHistory.objects.filter(user=request.user, manga_id=manga_id).first()
        read_chapter_ids = set(
            ReadChapter.objects.filter(user=request.user, manga_id=manga_id).values_list("chapter_id", flat=True)
        )
        for group in chapter_groups:
            entry_ids = [e["id"] for e in group["entries"]]
            group["any_read"] = any(eid in read_chapter_ids for eid in entry_ids)
            group["all_read"] = bool(entry_ids) and all(eid in read_chapter_ids for eid in entry_ids)

    return render(request, "reader/manga_detail.html", {
        "manga": manga,
        "chapters": chapters,
        "chapter_groups": chapter_groups,
        "error": error,
        "is_following": is_following,
        "is_favorited": is_favorited,
        "continue_reading": continue_reading,
        "recommendations": recommendations,
        "read_chapter_ids": read_chapter_ids,
        "volume_index": volume_index,
    })


def chapter_read(request, manga_id, chapter_id):
    error = None
    pages, manga, chapters = [], None, []
    current_chapter = None

    try:
        manga = services.get_manga_detail(manga_id)
        pages = services.get_chapter_pages(chapter_id)
    except MangaDexError as exc:
        error = str(exc)

    # Find out which language THIS chapter is in first — so the
    # navigation list we build next can prioritize that same language,
    # and 'next/prev chapter' stays on the translation track the reader
    # is actually on (English stays English, Vietnamese stays Vietnamese)
    # instead of always defaulting to Vietnamese.
    try:
        current_chapter = services.get_chapter_info(chapter_id)
    except MangaDexError as exc:
        error = error or str(exc)

    preferred_language = current_chapter["language"] if current_chapter else None
    languages = services.build_language_priority(preferred_language)

    try:
        chapters = services.get_manga_chapters(manga_id, languages=languages)
    except MangaDexError as exc:
        error = error or str(exc)

    # If the currently-viewed chapter is exactly the preferred-language
    # pick for its number, use that richer entry (has group/pages info)
    # instead of the bare lookup from get_chapter_info().
    matched = next((c for c in chapters if c["id"] == chapter_id), None)
    if matched:
        current_chapter = matched

    prev_chapter, next_chapter = None, None
    if current_chapter:
        chapter_numbers = [c["chapter"] for c in chapters]
        if current_chapter["chapter"] in chapter_numbers:
            idx = chapter_numbers.index(current_chapter["chapter"])
            if idx > 0:
                prev_chapter = chapters[idx - 1]
            if idx < len(chapters) - 1:
                next_chapter = chapters[idx + 1]

    if request.user.is_authenticated and manga and current_chapter and not error:
        ReadingHistory.objects.update_or_create(
            user=request.user,
            manga_id=manga_id,
            defaults={
                "manga_title": manga["title"],
                "cover_url": manga["cover_url"],
                "chapter_id": chapter_id,
                "chapter_number": current_chapter["chapter"],
            },
        )
        ReadChapter.objects.get_or_create(user=request.user, chapter_id=chapter_id, defaults={"manga_id": manga_id})
        Notification.objects.filter(user=request.user, chapter_id=chapter_id, is_read=False).update(is_read=True)

    return render(request, "reader/chapter_read.html", {
        "manga": manga,
        "manga_id": manga_id,
        "pages": pages,
        "chapters": chapters,
        "current_chapter": current_chapter,
        "prev_chapter": prev_chapter,
        "next_chapter": next_chapter,
        "error": error,
        "reader_page_size": request.session.get("reader_page_size", "medium"),
    })


@login_required
@require_POST
def toggle_bookmark(request, manga_id, kind):
    """AJAX-or-plain-POST endpoint to follow/unfollow or favorite/unfavorite a manga."""
    if kind not in (Bookmark.FOLLOW, Bookmark.FAVORITE):
        return JsonResponse({"error": "invalid kind"}, status=400)

    existing = Bookmark.objects.filter(user=request.user, kind=kind, manga_id=manga_id).first()
    if existing:
        existing.delete()
        active = False
    else:
        try:
            manga = services.get_manga_detail(manga_id)
        except MangaDexError:
            manga = None
        Bookmark.objects.create(
            user=request.user,
            kind=kind,
            manga_id=manga_id,
            manga_title=(manga or {}).get("title", ""),
            cover_url=(manga or {}).get("cover_url"),
        )
        active = True

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"active": active})
    return redirect(request.POST.get("next") or reverse("reader:manga_detail", args=[manga_id]))


@require_POST
def save_settings(request):
    """Persist 'origin_country' and 'reader_page_size' into the session.
    No login required — these are per-browser display preferences, not
    account data. Redirects back to wherever the form was submitted from."""
    origin = request.POST.get("origin_country")
    if origin in [c["code"] for c in ORIGIN_COUNTRIES]:
        request.session["origin_country"] = origin

    page_size = request.POST.get("reader_page_size")
    if page_size in [p["code"] for p in PAGE_SIZE_OPTIONS]:
        request.session["reader_page_size"] = page_size

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or reverse("reader:home")
    return redirect(next_url)


_chat_url_validator = URLValidator(schemes=["http", "https"])
_CHAT_TOKEN_RE = re.compile(r'(https?://[^\s<]+)|#(\w+)')
_URL_TRAILING_PUNCT = ").,;:!?]}'\""


def _shorten_url_for_display(url, max_len=45):
    parsed = urlparse(url)
    display = (parsed.netloc + parsed.path) or url
    if parsed.query:
        display += "?…"
    if len(display) > max_len:
        display = display[:max_len - 1] + "…"
    return display


def _render_url_card(raw_url):
    """Validates a detected URL's format and, if it looks well-formed,
    renders it as a rounded 'link card' with a shortened display and a
    new-tab open icon. Malformed links are left as plain (escaped) text
    instead of being turned into a clickable card."""
    trailing = ""
    while raw_url and raw_url[-1] in _URL_TRAILING_PUNCT:
        trailing = raw_url[-1] + trailing
        raw_url = raw_url[:-1]
    if not raw_url:
        return escape(trailing)

    try:
        _chat_url_validator(raw_url)
    except DjangoValidationError:
        return escape(raw_url) + escape(trailing)

    safe_href = escape(raw_url)
    safe_display = escape(_shorten_url_for_display(raw_url))
    card = (
        f'<a href="{safe_href}" target="_blank" rel="noopener noreferrer nofollow" class="chat-link-card">'
        f'<i class="fa-solid fa-link"></i>'
        f'<span class="chat-link-card-text">{safe_display}</span>'
        f'<i class="fa-solid fa-arrow-up-right-from-square chat-link-card-icon"></i>'
        f'</a>'
    )
    return card + escape(trailing)


def _linkify_content(text):
    """Renders message text with URLs turned into link-preview cards and
    #hashtags turned into filter links — replaces the old hashtag-only
    _linkify_content()."""
    if not text:
        return ""
    result = []
    last_end = 0
    for m in _CHAT_TOKEN_RE.finditer(text):
        result.append(escape(text[last_end:m.start()]))
        if m.group(1):
            result.append(_render_url_card(m.group(1)))
        else:
            tag = m.group(2)
            result.append(f'<a href="?tag={escape(tag)}" class="chat-hashtag">#{escape(tag)}</a>')
        last_end = m.end()
    result.append(escape(text[last_end:]))
    return "".join(result)


def _is_group_moderator(user, group):
    """Owner or a promoted admin — allowed to delete anyone's message."""
    if not user.is_authenticated:
        return False
    if group.created_by_id == user.id:
        return True
    return GroupMembership.objects.filter(group=group, user=user, is_admin=True).exists()


@login_required
@require_POST
def discussion_message_pin(request, slug, message_id):
    group = get_object_or_404(DiscussionGroup, slug=slug)
    msg = get_object_or_404(GroupMessage, pk=message_id, group=group)
    msg.is_pinned = not msg.is_pinned
    msg.save(update_fields=["is_pinned"])
    return JsonResponse({"ok": True, "is_pinned": msg.is_pinned})


@login_required
@require_POST
def discussion_message_edit(request, slug, message_id):
    group = get_object_or_404(DiscussionGroup, slug=slug)
    msg = get_object_or_404(GroupMessage, pk=message_id, group=group)
    if msg.user_id != request.user.id:
        return JsonResponse({"ok": False, "error": "Bạn chỉ có thể sửa tin nhắn của chính mình."}, status=403)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        payload = {}
    content = (payload.get("content") or "").strip()
    if not content:
        return JsonResponse({"ok": False, "error": "Nội dung không được để trống."}, status=400)

    msg.content = content
    msg.is_edited = True
    msg.save(update_fields=["content", "is_edited"])
    return JsonResponse({"ok": True, "content_html": _linkify_content(msg.content)})


@login_required
@require_POST
def discussion_message_delete(request, slug, message_id):
    group = get_object_or_404(DiscussionGroup, slug=slug)
    msg = get_object_or_404(GroupMessage, pk=message_id, group=group)
    if msg.user_id != request.user.id and not _is_group_moderator(request.user, group):
        return JsonResponse({"ok": False, "error": "Bạn không có quyền xoá tin nhắn này."}, status=403)
    msg.delete()
    return JsonResponse({"ok": True})


def discussion_list(request):
    query = request.GET.get("q", "").strip()
    groups = DiscussionGroup.objects.annotate(
        member_count=Count("memberships", distinct=True),
        message_count=Count("messages", distinct=True),
    )
    if query:
        groups = groups.filter(name__icontains=query)
    return render(request, "reader/discussion_list.html", {"groups": groups, "query": query})


@login_required
def discussion_create(request):
    if request.method == "POST":
        form = GroupCreateForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            group.created_by = request.user
            group.save()
            GroupMembership.objects.get_or_create(group=group, user=request.user)
            messages.success(request, "Đã tạo nhóm thảo luận.")
            return redirect("reader:discussion_room", slug=group.slug)
    else:
        form = GroupCreateForm()
    return render(request, "reader/discussion_create.html", {"form": form})


@login_required
def discussion_join(request, slug):
    group = get_object_or_404(DiscussionGroup, slug=slug)
    GroupMembership.objects.get_or_create(group=group, user=request.user)
    return redirect("reader:discussion_room", slug=slug)


def discussion_room(request, slug):
    group = get_object_or_404(DiscussionGroup, slug=slug)
    is_member = request.user.is_authenticated and GroupMembership.objects.filter(group=group, user=request.user).exists()
    is_moderator = _is_group_moderator(request.user, group)

    tag = request.GET.get("tag", "").strip()
    msgs = group.messages.select_related("user")
    if tag:
        msgs = msgs.filter(content__icontains=f"#{tag}")
    msgs = list(msgs[:200])
    for m in msgs:
        m.rendered_content = _linkify_content(m.content) if m.content else ""
        m.can_edit = request.user.is_authenticated and m.user_id == request.user.id
        m.can_delete = m.can_edit or is_moderator

    pinned_msgs = [m for m in msgs if m.is_pinned]

    form = None
    if request.user.is_authenticated:
        if request.method == "POST":
            form = GroupMessageForm(request.POST, request.FILES)
            if form.is_valid():
                msg = form.save(commit=False)
                msg.group = group
                msg.user = request.user
                msg.save()
                GroupMembership.objects.get_or_create(group=group, user=request.user)
                return redirect("reader:discussion_room", slug=slug)
        else:
            form = GroupMessageForm()

    member_count = GroupMembership.objects.filter(group=group).count()

    return render(request, "reader/discussion_room.html", {
        "group": group,
        "messages_list": msgs,
        "pinned_messages": pinned_msgs,
        "form": form,
        "is_member": is_member,
        "is_moderator": is_moderator,
        "member_count": member_count,
        "tag": tag,
        "last_id": msgs[-1].id if msgs else 0,
    })


def discussion_messages_poll(request, slug):
    """JSON endpoint: returns any messages newer than ?after=<id>, for the
    chat room's periodic polling (near-real-time without WebSockets)."""
    group = get_object_or_404(DiscussionGroup, slug=slug)
    is_moderator = _is_group_moderator(request.user, group)
    try:
        after_id = int(request.GET.get("after", 0))
    except ValueError:
        after_id = 0

    new_msgs = group.messages.select_related("user").filter(id__gt=after_id)[:50]
    results = []
    for m in new_msgs:
        can_edit = request.user.is_authenticated and m.user_id == request.user.id
        results.append({
            "id": m.id,
            "username": m.user.username,
            "content_html": _linkify_content(m.content) if m.content else "",
            "image_url": m.image.url if m.image else None,
            "video_url": m.video.url if m.video else None,
            "created_at": m.created_at.strftime("%H:%M"),
            "is_me": can_edit,
            "can_edit": can_edit,
            "can_delete": can_edit or is_moderator,
            "is_pinned": m.is_pinned,
        })
    return JsonResponse({"messages": results})


def profile(request):
    follow_count = Bookmark.objects.filter(user=request.user, kind=Bookmark.FOLLOW).count()
    favorite_count = Bookmark.objects.filter(user=request.user, kind=Bookmark.FAVORITE).count()
    history_qs = ReadingHistory.objects.filter(user=request.user)
    return render(request, "reader/profile.html", {
        "follow_count": follow_count,
        "favorite_count": favorite_count,
        "history_count": history_qs.count(),
        "recent_history": history_qs[:6],
    })


@login_required
def profile_edit(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Đã cập nhật hồ sơ.")
            return redirect("reader:profile")
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "reader/profile_edit.html", {"form": form})


@login_required
def notifications_list(request):
    items = Notification.objects.filter(user=request.user)
    return render(request, "reader/notifications.html", {"items": items})


@login_required
def notification_open(request, pk):
    """Marks one notification as read, then sends the reader into the chapter."""
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    if not notif.is_read:
        notif.is_read = True
        notif.save(update_fields=["is_read"])
    return redirect("reader:chapter_read", manga_id=notif.manga_id, chapter_id=notif.chapter_id)


@login_required
@require_POST
def notifications_mark_all_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    next_url = request.POST.get("next") or reverse("reader:notifications")
    return redirect(next_url)


@login_required
@require_POST
def mark_chapters_read(request, manga_id):
    """Bulk-marks a batch of chapter ids as read for the current user —
    powers the 'Đánh dấu đã đọc tất cả trên trang' button (only the
    chapters currently visible on the page, sent from the client)."""
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        payload = {}
    chapter_ids = [c for c in (payload.get("chapter_ids") or []) if c][:100]
    for cid in chapter_ids:
        ReadChapter.objects.get_or_create(user=request.user, chapter_id=cid, defaults={"manga_id": manga_id})
    return JsonResponse({"marked": len(chapter_ids)})


@login_required
def following(request):
    items = Bookmark.objects.filter(user=request.user, kind=Bookmark.FOLLOW)
    return render(request, "reader/bookmark_list.html", {
        "title": "📌 Truyện đang theo dõi",
        "items": items,
    })


@login_required
def favorites(request):
    items = Bookmark.objects.filter(user=request.user, kind=Bookmark.FAVORITE)
    return render(request, "reader/bookmark_list.html", {
        "title": "❤️ Truyện yêu thích",
        "items": items,
    })


@login_required
def history(request):
    items = ReadingHistory.objects.filter(user=request.user)
    return render(request, "reader/history.html", {"items": items})
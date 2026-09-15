"""
Thin wrapper around the public MangaDex API (https://api.mangadex.org).

All functions here return plain Python dicts/lists that are already
"flattened" for easy use in Django templates (title, cover_url, description,
status, tags, etc.) instead of raw MangaDex JSON:API shapes.
"""
import requests
from django.conf import settings
from django.core.cache import cache

API_BASE = settings.MANGADEX_API_BASE
UPLOADS_BASE = settings.MANGADEX_UPLOADS_BASE
CACHE_TTL = settings.MANGADEX_CACHE_TTL

DEFAULT_HEADERS = {
    "User-Agent": "MangaWebDjangoDemo/1.0 (+https://mangadex.org)"
}

# Chế độ nội dung MangaDex cho phép lọc manga theo mức độ gợi cảm/18+ hay không. MangaDex's own API docs:
# https://api.mangadex.org/docs.html#section/Content-Rating-Filter
SAFE_CONTENT_RATINGS = [
    "safe",
    "suggestive",
    "erotica",
    "pornographic",
]

# Countries/origin languages commonly published on MangaDex, used for the
# navbar "Cài đặt → Quốc gia" filter. "all" means no originalLanguage
# filter at all (identical to browsing MangaDex itself).
ORIGIN_COUNTRIES = [
    {"code": "all", "label": "🌏 Tất cả"},
    {"code": "ja", "label": "🇯🇵 Nhật Bản (Manga)"},
    {"code": "ko", "label": "🇰🇷 Hàn Quốc (Manhwa)"},
    {"code": "zh", "label": "🇨🇳 Trung Quốc (Manhua)"},
    {"code": "zh-hk", "label": "🇭🇰 Hồng Kông (Manhua)"},
    {"code": "en", "label": "🇬🇧 Tiếng Anh (gốc)"},
]

# Controls the max-width of chapter page images on the reader screen.
PAGE_SIZE_OPTIONS = [
    {"code": "small", "label": "Nhỏ (600px)"},
    {"code": "medium", "label": "Vừa (900px)"},
    {"code": "large", "label": "Lớn (1200px)"},
    {"code": "full", "label": "Toàn màn hình"},
]


def _origin_params(origin_language):
    """Build the originalLanguage[] query param dict fragment.
    None or 'all' → no filter (show every country, like mangadex.org)."""
    if not origin_language or origin_language == "all":
        return {}
    return {"originalLanguage[]": [origin_language]}


class MangaDexError(Exception):
    """Raised when the MangaDex API can't be reached or returns an error."""
    pass


def _get(path, params=None, timeout=12):
    """GET helper with basic error handling. Raises MangaDexError on failure."""
    url = f"{API_BASE}{path}"
    try:
        resp = requests.get(url, params=params or {}, headers=DEFAULT_HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        raise MangaDexError(f"Không thể kết nối tới MangaDex API: {exc}") from exc


def _pick_title(title_dict, alt_titles=None):
    """MangaDex titles are {'en': '...', 'ja': '...', ...}. Prefer English."""
    if not title_dict:
        title_dict = {}
    for lang in ("vi", "en", "ja-ro", "ja"):
        if title_dict.get(lang):
            return title_dict[lang]
    if title_dict:
        return next(iter(title_dict.values()))
    # fall back to alt titles
    for alt in (alt_titles or []):
        for lang in ("en", "ja-ro"):
            if alt.get(lang):
                return alt[lang]
    return "Không rõ tên"


def _pick_description(desc_dict):
    if not desc_dict:
        return ""
    for lang in ("vi", "en"):
        if desc_dict.get(lang):
            return desc_dict[lang]
    if desc_dict:
        return next(iter(desc_dict.values()))
    return ""


def _cover_filename(relationships):
    for rel in relationships or []:
        if rel.get("type") == "cover_art":
            attrs = rel.get("attributes") or {}
            return attrs.get("fileName")
    return None


def _author_names(relationships):
    names = []
    for rel in relationships or []:
        if rel.get("type") in ("author", "artist"):
            attrs = rel.get("attributes") or {}
            name = attrs.get("name")
            if name and name not in names:
                names.append(name)
    return names


def normalize_manga(item):
    """Turn one raw MangaDex 'manga' resource object into a flat dict."""
    attrs = item.get("attributes", {})
    manga_id = item.get("id")
    relationships = item.get("relationships", [])
    cover_file = _cover_filename(relationships)
    cover_url = (
        f"{UPLOADS_BASE}/covers/{manga_id}/{cover_file}.512.jpg"
        if cover_file else None
    )
    tags = [
        {
            "id": t.get("id"),
            "name": t["attributes"]["name"].get("en") or next(iter(t["attributes"]["name"].values()), ""),
        }
        for t in attrs.get("tags", [])
        if t.get("attributes", {}).get("name")
    ]
    alt_titles = [
        {"language": lang, "title": text, "flag": LANGUAGE_COUNTRY_CODES.get(lang, "xx")}
        for entry in (attrs.get("altTitles") or [])
        for lang, text in entry.items()
        if text
    ]
    return {
        "id": manga_id,
        "title": _pick_title(attrs.get("title"), attrs.get("altTitles")),
        "description": _pick_description(attrs.get("description")),
        "cover_url": cover_url,
        "status": attrs.get("status", ""),
        "year": attrs.get("year"),
        "tags": tags[:5],
        "authors": _author_names(relationships),
        "content_rating": attrs.get("contentRating", "safe"),
        "original_language": attrs.get("originalLanguage"),
        "links": attrs.get("links") or {},
        "alt_titles": alt_titles,
    }


def get_popular_manga(limit=18, origin_language=None, offset=0):
    """Most-followed manga overall — used for the hero grid / trending row
    (offset=0) and the paginated 'Hot' page (offset > 0)."""
    cache_key = f"mdx:popular:{limit}:{origin_language or 'all'}:{offset}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    params = {
        "limit": limit,
        "offset": offset,
        "includes[]": "cover_art",
        "order[followedCount]": "desc",
        "contentRating[]": SAFE_CONTENT_RATINGS,
        "hasAvailableChapters": "true",
    }
    params.update(_origin_params(origin_language))
    data = _get("/manga", params=params)
    results = [normalize_manga(item) for item in data.get("data", [])]
    payload = {"items": results, "total": data.get("total", len(results))}
    cache.set(cache_key, payload, CACHE_TTL)
    return payload


def get_latest_updates(limit=18, origin_language=None):
    """Manga with the most recently uploaded chapters."""
    cache_key = f"mdx:latest:{limit}:{origin_language or 'all'}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    params = {
        "limit": limit,
        "includes[]": "cover_art",
        "order[latestUploadedChapter]": "desc",
        "contentRating[]": SAFE_CONTENT_RATINGS,
        "hasAvailableChapters": "true",
    }
    params.update(_origin_params(origin_language))
    data = _get("/manga", params=params)
    results = [normalize_manga(item) for item in data.get("data", [])]
    cache.set(cache_key, results, CACHE_TTL)
    return results


def has_restricted_matches(query):
    """Checks (count only, no content fetched) whether the search query
    matches any manga rated erotica/pornographic on MangaDex. Used only
    to show a content-warning notice pointing people to MangaDex's own
    site — this app never fetches or displays that content itself."""
    if not query:
        return False
    params = {"title": query, "limit": 1, "contentRating[]": ["erotica", "pornographic"]}
    try:
        data = _get("/manga", params=params)
    except MangaDexError:
        return False
    return data.get("total", 0) > 0


def search_manga(query, limit=24, origin_language=None, offset=0):
    """Search manga by title."""
    if not query:
        return {"items": [], "total": 0}
    params = {
        "title": query,
        "limit": limit,
        "offset": offset,
        "includes[]": "cover_art",
        "contentRating[]": SAFE_CONTENT_RATINGS,
        "order[relevance]": "desc",
    }
    params.update(_origin_params(origin_language))
    data = _get("/manga", params=params)
    results = [normalize_manga(item) for item in data.get("data", [])]
    return {"items": results, "total": data.get("total", len(results))}


ORIGIN_LANGUAGE_NAMES = {
    "ja": "Nhật Bản", "ko": "Hàn Quốc", "zh": "Trung Quốc", "zh-hk": "Hồng Kông",
    "en": "Tiếng Anh", "fr": "Pháp", "vi": "Việt Nam", "th": "Thái Lan",
    "id": "Indonesia", "es": "Tây Ban Nha", "de": "Đức", "it": "Ý",
    "ru": "Nga", "pl": "Ba Lan", "pt-br": "Brazil", "tr": "Thổ Nhĩ Kỳ",
}

CONTENT_RATING_LABELS = {
    "safe": "An toàn",
    "suggestive": "Gợi cảm",
    "erotica": "Erotica",
    "pornographic": "Pornographic",
}

# MangaDex stores external tracker/source links as {key: value} where value
# is sometimes a full URL and sometimes just an id/slug that needs a
# template. Maps each key to (display name, URL template).
EXTERNAL_LINK_MAP = {
    "al": ("AniList", "https://anilist.co/manga/{}"),
    "ap": ("Anime-Planet", "https://www.anime-planet.com/manga/{}"),
    "bw": ("BookWalker", "https://bookwalker.jp/{}"),
    "mu": ("MangaUpdates", "https://www.mangaupdates.com/series.html?id={}"),
    "nu": ("NovelUpdates", "https://www.novelupdates.com/series/{}"),
    "kt": ("Kitsu", "https://kitsu.io/manga/{}"),
    "mal": ("MyAnimeList", "https://myanimelist.net/manga/{}"),
    "amz": ("Amazon", "{}"),
    "ebj": ("eBookJapan", "{}"),
    "cdj": ("CDJapan", "{}"),
    "raw": ("Bản gốc (raw)", "{}"),
    "engtl": ("Bản dịch chính thức", "{}"),
}


def build_source_links(manga_id, links_dict):
    """MangaDex's own page for this title, plus any external tracker/source
    links MangaDex has on file for it — ready to render as clickable
    'Nguồn: MangaDex, MangaUpdates, ...' links."""
    sources = [{"name": "MangaDex", "url": f"https://mangadex.org/title/{manga_id}"}]
    for key, value in (links_dict or {}).items():
        if not value:
            continue
        mapped = EXTERNAL_LINK_MAP.get(key)
        if not mapped:
            continue
        label, template = mapped
        url = value if value.startswith("http") else template.format(value)
        sources.append({"name": label, "url": url})
    return sources


def get_manga_detail(manga_id):
    cache_key = f"mdx:manga:{manga_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    params = {"includes[]": ["cover_art", "author", "artist"]}
    data = _get(f"/manga/{manga_id}", params=params)
    item = data.get("data")
    if not item:
        return None
    result = normalize_manga(item)
    result["origin_language_name"] = ORIGIN_LANGUAGE_NAMES.get(
        result.get("original_language"), result.get("original_language") or "Không rõ"
    )
    result["content_rating_label"] = CONTENT_RATING_LABELS.get(
        result.get("content_rating"), result.get("content_rating") or "Không rõ"
    )
    result["source_links"] = build_source_links(manga_id, result.get("links"))
    cache.set(cache_key, result, CACHE_TTL)
    return result


LANGUAGE_COUNTRY_CODES = {
    "en": "gb", "vi": "vn", "ja": "jp", "ko": "kr",
    "zh": "cn", "zh-hk": "hk", "pt-br": "br", "es": "es",
    "es-la": "mx", "fr": "fr", "ru": "ru", "id": "id",
    "th": "th", "de": "de", "it": "it", "pl": "pl",
    "tr": "tr", "ar": "sa", "uk": "ua", "nl": "nl",
}


def get_manga_chapters_grouped(manga_id, limit=300):
    """All-language chapter feed, grouped by chapter number — powers the
    MangaDex-style chapter list (flag + group + time + comment count per
    translation). Separate from get_manga_chapters(), which stays
    single-language and drives 'next/prev chapter' reading navigation."""
    from django.utils.dateparse import parse_datetime

    cache_key = f"mdx:chaptersgrouped:{manga_id}:{limit}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    params = {
        "order[chapter]": "asc",
        "limit": limit,
        "includes[]": "scanlation_group",
        "contentRating[]": SAFE_CONTENT_RATINGS,
    }
    data = _get(f"/manga/{manga_id}/feed", params=params)

    flat = []
    for item in data.get("data", []):
        attrs = item.get("attributes", {})
        group_name = None
        for rel in item.get("relationships", []):
            if rel.get("type") == "scanlation_group":
                group_name = (rel.get("attributes") or {}).get("name")
        lang = attrs.get("translatedLanguage")
        publish_raw = attrs.get("publishAt")
        flat.append({
            "id": item.get("id"),
            "chapter": attrs.get("chapter") or "?",
            "volume": attrs.get("volume"),
            "title": attrs.get("title") or "",
            "language": lang,
            "flag": LANGUAGE_COUNTRY_CODES.get(lang, "xx"),
            "pages": attrs.get("pages", 0),
            "group": group_name or "No Group",
            "publish_at": parse_datetime(publish_raw) if publish_raw else None,
        })

    # Best-effort comment counts — never let a stats failure break the page.
    try:
        ids = [c["id"] for c in flat]
        stats = {}
        for i in range(0, len(ids), 100):
            batch = ids[i:i + 100]
            sdata = _get("/statistics/chapter", params={"chapter[]": batch})
            stats.update(sdata.get("statistics", {}))
        for c in flat:
            s = stats.get(c["id"]) or {}
            comments = (s.get("comments") or {}) if s else {}
            c["comments"] = comments.get("repliesCount") if comments else None
    except MangaDexError:
        for c in flat:
            c["comments"] = None

    groups = {}
    order = []
    for c in flat:
        key = c["chapter"]
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(c)

    grouped = [{"chapter": k, "entries": groups[k]} for k in order]
    cache.set(cache_key, grouped, CACHE_TTL)
    return grouped


def build_language_priority(preferred_language):
    """Ordered, de-duplicated language priority list with `preferred_language`
    first (if given) — used so 'next/prev chapter' stays on whichever
    translation the reader is currently on, falling back to vi/en for
    chapter numbers that don't have that language."""
    base = [preferred_language, "vi", "en"] if preferred_language else ["vi", "en"]
    return tuple(dict.fromkeys(lang for lang in base if lang))


def get_manga_chapters(manga_id, languages=("vi", "en"), limit=200):
    """Chapter feed for one manga. When both Vietnamese and English (or
    whichever languages are requested) have a translation for the same
    chapter number, only ONE is kept per number — preferring the first
    language in `languages` (Vietnamese by default). This keeps
    'next/prev chapter' on a single consistent translation track instead
    of randomly hopping between scanlation groups/languages."""
    cache_key = f"mdx:chapters:{manga_id}:{','.join(languages)}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    params = {
        "translatedLanguage[]": list(languages),
        "order[chapter]": "asc",
        "limit": limit,
        "includes[]": "scanlation_group",
        "contentRating[]": SAFE_CONTENT_RATINGS,
    }
    data = _get(f"/manga/{manga_id}/feed", params=params)

    flat = []
    for item in data.get("data", []):
        attrs = item.get("attributes", {})
        group_name = None
        for rel in item.get("relationships", []):
            if rel.get("type") == "scanlation_group":
                group_name = (rel.get("attributes") or {}).get("name")
        flat.append({
            "id": item.get("id"),
            "chapter": attrs.get("chapter") or "?",
            "volume": attrs.get("volume"),
            "title": attrs.get("title") or "",
            "language": attrs.get("translatedLanguage"),
            "pages": attrs.get("pages", 0),
            "group": group_name,
            "publish_at": attrs.get("publishAt"),
        })

    # Keep exactly one entry per chapter number, preferring languages in
    # the order given (Vietnamese first by default).
    priority = {lang: i for i, lang in enumerate(languages)}
    best = {}
    order = []
    for c in flat:
        key = c["chapter"]
        rank = priority.get(c["language"], len(languages))
        if key not in best:
            order.append(key)
            best[key] = (rank, c)
        elif rank < best[key][0]:
            best[key] = (rank, c)

    chapters = [best[k][1] for k in order]
    cache.set(cache_key, chapters, CACHE_TTL)
    return chapters


def get_all_tags():
    """Full genre/tag list from MangaDex (used for the 'Thể loại' dropdown).
    This list changes extremely rarely, so it's cached for hours.
    Returns a list of {id, name, group} sorted by name, group in
    ('genre', 'theme', 'format', 'content').
    """
    cache_key = "mdx:tags"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    data = _get("/manga/tag")
    tags = []
    for item in data.get("data", []):
        attrs = item.get("attributes", {})
        name_dict = attrs.get("name", {})
        name = name_dict.get("en") or next(iter(name_dict.values()), "?")
        tags.append({
            "id": item.get("id"),
            "name": name,
            "group": attrs.get("group", "genre"),
        })
    tags.sort(key=lambda t: t["name"])
    cache.set(cache_key, tags, settings.MANGADEX_TAGS_CACHE_TTL)
    return tags


def get_tag_name(tag_id):
    for tag in get_all_tags():
        if tag["id"] == tag_id:
            return tag["name"]
    return None


def browse_manga_by_tag(tag_id, limit=24, offset=0, origin_language=None):
    """Manga list filtered to a single genre/tag id."""
    params = {
        "includedTags[]": [tag_id],
        "limit": limit,
        "offset": offset,
        "includes[]": "cover_art",
        "order[followedCount]": "desc",
        "contentRating[]": SAFE_CONTENT_RATINGS,
        "hasAvailableChapters": "true",
    }
    params.update(_origin_params(origin_language))
    data = _get("/manga", params=params)
    results = [normalize_manga(item) for item in data.get("data", [])]
    return {"items": results, "total": data.get("total", len(results))}


def get_popular_new_titles(limit=10, origin_language=None):
    """Recently-added manga ordered by follow count — the
    'Những tựa sách mới được yêu thích' homepage carousel, mirroring
    MangaDex's own 'Popular New Titles' widget. Starts with a 90-day
    window and widens it if that turns up too few titles to rotate
    through, so the carousel never ends up stuck on 1-2 items."""
    import datetime

    cache_key = f"mdx:popularnew:{limit}:{origin_language or 'all'}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    results = []
    for days in (90, 365, None):  # None = no time filter at all, last resort
        params = {
            "limit": limit,
            "includes[]": ["cover_art", "author", "artist"],
            "order[followedCount]": "desc",
            "contentRating[]": SAFE_CONTENT_RATINGS,
            "hasAvailableChapters": "true",
        }
        if days is not None:
            since = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
            params["createdAtSince"] = since
        params.update(_origin_params(origin_language))
        data = _get("/manga", params=params)
        results = [normalize_manga(item) for item in data.get("data", [])]
        if len(results) >= 5:
            break

    cache.set(cache_key, results, CACHE_TTL)
    return results


def build_page_range(current, total_pages, window=2):
    """Builds a compact page list like [1, 2, 3, None, 209] (None = '…'),
    always keeping the first page, last page, and a window around the
    current page — used to render '1 2 3 … 209'-style pagination."""
    if total_pages <= 1:
        return [1]
    keep = {1, total_pages, current}
    for d in range(1, window + 1):
        keep.add(current - d)
        keep.add(current + d)
    pages = sorted(p for p in keep if 1 <= p <= total_pages)

    result = []
    prev = None
    for p in pages:
        if prev is not None and p - prev > 1:
            result.append(None)
        result.append(p)
        prev = p
    return result


SORT_FIELD_MAP = {
    "relevance": "relevance",
    "latestUploadedChapter": "latestUploadedChapter",
    "title": "title",
    "followedCount": "followedCount",
    "createdAt": "createdAt",
    "rating": "rating",
}


def advanced_search(filters, limit=24, offset=0):
    """Full-filter manga search: title, status, demographic, content
    rating, included/excluded tags (with AND/OR mode), and sort order —
    mirrors MangaDex's own 'Advanced Search'."""
    params = {
        "limit": limit,
        "offset": offset,
        "includes[]": "cover_art",
    }
    title = (filters.get("title") or "").strip()
    if title:
        params["title"] = title
    if filters.get("statuses"):
        params["status[]"] = filters["statuses"]
    if filters.get("demographics"):
        params["publicationDemographic[]"] = filters["demographics"]
    params["contentRating[]"] = filters.get("content_ratings") or SAFE_CONTENT_RATINGS
    if filters.get("included_tags"):
        params["includedTags[]"] = filters["included_tags"]
        params["includedTagsMode"] = filters.get("included_mode") or "AND"
    if filters.get("excluded_tags"):
        params["excludedTags[]"] = filters["excluded_tags"]
        params["excludedTagsMode"] = filters.get("excluded_mode") or "OR"

    order_field = filters.get("order_by") or "relevance"
    if order_field == "relevance" and not title:
        # MangaDex only allows ordering by relevance when a title search
        # is present — fall back to most-followed otherwise.
        order_field = "followedCount"
    order_dir = filters.get("order_dir") or "desc"
    params[f"order[{order_field}]"] = order_dir

    data = _get("/manga", params=params)
    results = [normalize_manga(item) for item in data.get("data", [])]
    return {"items": results, "total": data.get("total", len(results))}


def format_count(n):
    """103245 -> '103k', 1_250_000 -> '1.3M', None -> 'N/A'."""
    if n is None:
        return "N/A"
    if n >= 1_000_000:
        s = f"{n / 1_000_000:.1f}M"
    elif n >= 1_000:
        s = f"{n / 1000:.1f}k"
    else:
        return str(n)
    return s.replace(".0M", "M").replace(".0k", "k")


def build_rating_breakdown(distribution):
    """Turns MangaDex's {'1': 280, ..., '10': 4029} rating distribution
    into an ordered (10 -> 1) list with bar-width percentages, for the
    'Phân bố đánh giá' histogram."""
    if not distribution:
        return []
    counts = {int(k): v for k, v in distribution.items()}
    max_count = max(max(counts.values()), 1)
    return [
        {"score": s, "count": counts.get(s, 0), "percent": round((counts.get(s, 0) / max_count) * 100, 1)}
        for s in range(10, 0, -1)
    ]


def get_manga_statistics(manga_id):
    """Rating (average/bayesian/distribution), follow count, and total
    comment count for one manga — from MangaDex's public Statistics API."""
    cache_key = f"mdx:mangastats:{manga_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    data = _get(f"/statistics/manga/{manga_id}")
    stats = (data.get("statistics") or {}).get(manga_id) or {}
    rating = stats.get("rating") or {}
    result = {
        "average": rating.get("average"),
        "bayesian": rating.get("bayesian"),
        "follows": stats.get("follows"),
        "comments": (stats.get("comments") or {}).get("repliesCount"),
        "rating_breakdown": build_rating_breakdown(rating.get("distribution")),
    }
    cache.set(cache_key, result, CACHE_TTL)
    return result


def build_volume_index(chapter_groups):
    """Groups the multi-language chapter_groups structure (from
    get_manga_chapters_grouped) by volume — powers the 'Index' quick-jump
    modal. Each volume keeps its chapters, and each chapter keeps every
    translation/group entry, matching MangaDex's own Index feature."""
    groups = []
    for cg in chapter_groups:
        vol = cg["entries"][0].get("volume") if cg["entries"] else None
        if not groups or groups[-1]["volume"] != vol:
            groups.append({"volume": vol, "chapter_groups": []})
        groups[-1]["chapter_groups"].append(cg)

    result = []
    for g in groups:
        nums = [cg["chapter"] for cg in g["chapter_groups"]]
        result.append({
            "label": f"Tập {g['volume']}" if g["volume"] else "Không có tập",
            "start": nums[0] if nums else "?",
            "end": nums[-1] if nums else "?",
            "count": len(nums),
            "chapter_groups": g["chapter_groups"],
        })
    return result


def get_chapter_info(chapter_id):
    """Fetch one chapter's own attributes directly (chapter number, title,
    language) — used as a fallback when the reader opened a translation
    that isn't the 'preferred language' pick in get_manga_chapters(), so
    prev/next navigation can still be resolved for it."""
    cache_key = f"mdx:chapterinfo:{chapter_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    data = _get(f"/chapter/{chapter_id}")
    attrs = (data.get("data") or {}).get("attributes", {})
    info = {
        "id": chapter_id,
        "chapter": attrs.get("chapter") or "?",
        "title": attrs.get("title") or "",
        "language": attrs.get("translatedLanguage"),
        "group": None,
        "pages": attrs.get("pages", 0),
        "publish_at": attrs.get("publishAt"),
    }
    cache.set(cache_key, info, CACHE_TTL)
    return info


def get_chapter_pages(chapter_id, data_saver=False):
    """Resolve a chapter id into a list of ready-to-display image URLs."""
    data = _get(f"/at-home/server/{chapter_id}")
    base_url = data.get("baseUrl")
    chapter = data.get("chapter", {})
    chapter_hash = chapter.get("hash")
    filenames = chapter.get("dataSaver" if data_saver else "data", [])
    quality = "data-saver" if data_saver else "data"
    return [
        f"{base_url}/{quality}/{chapter_hash}/{fname}"
        for fname in filenames
    ]
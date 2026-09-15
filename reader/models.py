import os
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.utils.text import slugify

chat_image_storage = FileSystemStorage(
    location=settings.CHAT_MEDIA_ROOT_IMG,
    base_url=settings.STATIC_URL + "reader/img_group/",
)
chat_video_storage = FileSystemStorage(
    location=settings.CHAT_MEDIA_ROOT_VIDEO,
    base_url=settings.STATIC_URL + "reader/video_group/",
)


class Bookmark(models.Model):
    """One row = one user following OR favoriting one manga.
    kind distinguishes the two so 'Theo dõi' and 'Yêu thích' can share a table.
    """
    FOLLOW = "follow"
    FAVORITE = "favorite"
    KIND_CHOICES = [(FOLLOW, "Theo dõi"), (FAVORITE, "Yêu thích")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookmarks")
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    manga_id = models.CharField(max_length=64)
    manga_title = models.CharField(max_length=255)
    cover_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Only meaningful for kind=FOLLOW: the newest chapter number we last
    # saw for this manga. Used to detect "a new chapter came out" so we
    # only notify on genuinely new releases, not on every check.
    last_known_chapter = models.CharField(max_length=32, blank=True, null=True)

    class Meta:
        unique_together = ("user", "kind", "manga_id")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} {self.kind} {self.manga_title}"


class Notification(models.Model):
    """A 'this followed manga has a new chapter' alert for one user."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    manga_id = models.CharField(max_length=64)
    manga_title = models.CharField(max_length=255)
    cover_url = models.URLField(blank=True, null=True)
    chapter_id = models.CharField(max_length=64)
    chapter_number = models.CharField(max_length=32, blank=True)
    flag = models.CharField(max_length=8, blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} — {self.manga_title} ch.{self.chapter_number}"


class Badge(models.Model):
    """A custom badge (Mod, VIP, Fan cứng, ...) admins can grant to users —
    shown next to their name in Thảo luận messages."""
    name = models.CharField(max_length=40, unique=True)
    icon = models.CharField(max_length=10, blank=True, help_text="1 emoji, ví dụ 🛡️")
    color = models.CharField(max_length=7, default="#7c6bf2", help_text="Mã màu hex, ví dụ #7c6bf2")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class UserBadge(models.Model):
    """One badge granted to one user, by an admin."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="badges")
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name="holders")
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="badges_granted")
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "badge")
        ordering = ["-granted_at"]

    def __str__(self):
        return f"{self.user} — {self.badge}"


class DiscussionGroup(models.Model):
    """A discussion group ('Thảo luận') — public group chat rooms."""
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="created_chat_groups")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:120] or "nhom"
            slug = base
            i = 1
            while DiscussionGroup.objects.filter(slug=slug).exists():
                i += 1
                slug = f"{base}-{i}"
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class GroupMembership(models.Model):
    """Tracks who has joined which discussion group, and who moderates it."""
    group = models.ForeignKey(DiscussionGroup, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_memberships")
    is_admin = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("group", "user")

    def __str__(self):
        return f"{self.user} in {self.group}"


class GroupMessage(models.Model):
    """One message in a discussion group — text and/or one image/video."""
    group = models.ForeignKey(DiscussionGroup, on_delete=models.CASCADE, related_name="messages")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_messages")
    content = models.TextField(blank=True)
    image = models.ImageField(storage=chat_image_storage, upload_to="", blank=True, null=True)
    video = models.FileField(storage=chat_video_storage, upload_to="", blank=True, null=True)
    is_pinned = models.BooleanField(default=False)
    is_edited = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.user} in {self.group} @ {self.created_at}"


class ReadChapter(models.Model):
    """One row = one specific chapter (by id) a user has opened. Unlike
    ReadingHistory (which only keeps the single latest chapter per manga,
    for the 'Lịch sử' page), this tracks every chapter ever opened so the
    chapter list can show a read/unread eye icon per row — including
    distinguishing between different scanlation groups' versions of the
    same chapter number."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="read_chapters")
    manga_id = models.CharField(max_length=64)
    chapter_id = models.CharField(max_length=64)
    read_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "chapter_id")

    def __str__(self):
        return f"{self.user} read chapter {self.chapter_id}"


class ReadingHistory(models.Model):
    """Tracks the last time a user read a given chapter, for the 'Lịch sử' page."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reading_history")
    manga_id = models.CharField(max_length=64)
    manga_title = models.CharField(max_length=255)
    cover_url = models.URLField(blank=True, null=True)
    chapter_id = models.CharField(max_length=64)
    chapter_number = models.CharField(max_length=32, blank=True)
    read_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "manga_id")  # keep only latest chapter per manga
        ordering = ["-read_at"]

    def __str__(self):
        return f"{self.user} @ {self.manga_title} ch.{self.chapter_number}"
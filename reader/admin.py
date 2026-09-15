from django.contrib import admin
from .models import Bookmark, ReadingHistory, ReadChapter, Notification, DiscussionGroup, GroupMembership, GroupMessage, Badge, UserBadge


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ("user", "kind", "manga_title", "last_known_chapter", "created_at")
    list_filter = ("kind",)
    search_fields = ("manga_title", "user__username")


@admin.register(ReadingHistory)
class ReadingHistoryAdmin(admin.ModelAdmin):
    list_display = ("user", "manga_title", "chapter_number", "read_at")
    search_fields = ("manga_title", "user__username")


@admin.register(ReadChapter)
class ReadChapterAdmin(admin.ModelAdmin):
    list_display = ("user", "manga_id", "chapter_id", "read_at")
    search_fields = ("user__username", "manga_id", "chapter_id")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "manga_title", "chapter_number", "is_read", "created_at")
    list_filter = ("is_read",)
    search_fields = ("manga_title", "user__username")


@admin.register(DiscussionGroup)
class DiscussionGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "created_by", "created_at")
    search_fields = ("name",)


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "group", "joined_at")


@admin.register(GroupMessage)
class GroupMessageAdmin(admin.ModelAdmin):
    list_display = ("user", "group", "created_at")
    search_fields = ("content", "user__username", "group__name")


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ("name", "icon", "color", "created_at")


@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ("user", "badge", "granted_by", "granted_at")
    search_fields = ("user__username", "badge__name")
from django.urls import path
from . import views

app_name = "reader"

urlpatterns = [
    path("", views.home, name="home"),
    path("hot/", views.hot, name="hot"),
    path("tim-kiem/", views.search, name="search"),
    path("api/tim-kiem-goi-y/", views.search_suggest, name="search_suggest"),
    path("tim-kiem-nang-cao/", views.advanced_search, name="advanced_search"),
    path("the-loai/", views.genre_list, name="genre_list"),
    path("the-loai/<str:tag_id>/", views.genre_detail, name="genre_detail"),

    path("theo-doi/", views.following, name="following"),
    path("yeu-thich/", views.favorites, name="favorites"),
    path("lich-su/", views.history, name="history"),
    path("cai-dat/", views.save_settings, name="save_settings"),
    path("ho-so/", views.profile, name="profile"),
    path("ho-so/sua/", views.profile_edit, name="profile_edit"),

    path("chinh-sach-bao-mat/", views.privacy_policy, name="privacy_policy"),
    path("dieu-khoan-su-dung/", views.terms_of_service, name="terms_of_service"),

    path("thao-luan/", views.discussion_list, name="discussion_list"),
    path("thao-luan/tao-nhom/", views.discussion_create, name="discussion_create"),
    path("thao-luan/<slug:slug>/", views.discussion_room, name="discussion_room"),
    path("thao-luan/<slug:slug>/tham-gia/", views.discussion_join, name="discussion_join"),
    path("thao-luan/<slug:slug>/tin-nhan-moi/", views.discussion_messages_poll, name="discussion_messages_poll"),
    path("thao-luan/<slug:slug>/tin-nhan/<int:message_id>/ghim/", views.discussion_message_pin, name="discussion_message_pin"),
    path("thao-luan/<slug:slug>/tin-nhan/<int:message_id>/sua/", views.discussion_message_edit, name="discussion_message_edit"),
    path("thao-luan/<slug:slug>/tin-nhan/<int:message_id>/xoa/", views.discussion_message_delete, name="discussion_message_delete"),
    path("thong-bao/", views.notifications_list, name="notifications"),
    path("thong-bao/<int:pk>/", views.notification_open, name="notification_open"),
    path("thong-bao/danh-dau-da-doc/", views.notifications_mark_all_read, name="notifications_mark_all_read"),

    path("truyen/<str:manga_id>/", views.manga_detail, name="manga_detail"),
    path("truyen/<str:manga_id>/danh-dau-da-doc/", views.mark_chapters_read, name="mark_chapters_read"),
    path("truyen/<str:manga_id>/chuong/<str:chapter_id>/", views.chapter_read, name="chapter_read"),
    path("truyen/<str:manga_id>/danh-dau/<str:kind>/", views.toggle_bookmark, name="toggle_bookmark"),
]
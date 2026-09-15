from django import forms
from django.contrib.auth.models import User

from .models import DiscussionGroup, GroupMessage, Badge


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["username", "email"]

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username=username).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Tên người dùng này đã được sử dụng.")
        return username


class GroupCreateForm(forms.ModelForm):
    class Meta:
        model = DiscussionGroup
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Tên nhóm thảo luận..."}),
            "description": forms.TextInput(attrs={"placeholder": "Mô tả ngắn (tuỳ chọn)..."}),
        }


class GroupMessageForm(forms.ModelForm):
    class Meta:
        model = GroupMessage
        fields = ["content", "image", "video"]

    def clean_image(self):
        f = self.cleaned_data.get("image")
        if f:
            if f.size > 8 * 1024 * 1024:
                raise forms.ValidationError("Ảnh tối đa 8MB.")
            ext = f.name.rsplit(".", 1)[-1].lower() if "." in f.name else ""
            if ext not in ("jpg", "jpeg", "png", "gif", "webp"):
                raise forms.ValidationError("Chỉ nhận ảnh JPG, PNG, GIF hoặc WEBP.")
        return f

    def clean_video(self):
        f = self.cleaned_data.get("video")
        if f:
            if f.size > 50 * 1024 * 1024:
                raise forms.ValidationError("Video tối đa 50MB.")
            ext = f.name.rsplit(".", 1)[-1].lower() if "." in f.name else ""
            if ext not in ("mp4", "webm", "mov"):
                raise forms.ValidationError("Chỉ nhận video MP4, WEBM hoặc MOV.")
        return f

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("content") and not cleaned.get("image") and not cleaned.get("video"):
            raise forms.ValidationError("Tin nhắn cần có nội dung, ảnh hoặc video.")
        return cleaned


class BadgeForm(forms.ModelForm):
    class Meta:
        model = Badge
        fields = ["name", "icon", "color"]
        widgets = {
            "color": forms.TextInput(attrs={"type": "color"}),
        }
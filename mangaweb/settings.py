"""
Django settings for mangaweb project.
A simple manga reading site backed by the public MangaDex API.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load variables from a .env file next to manage.py (see .env.example).
# Safe to call even if the file doesn't exist - just does nothing then.
load_dotenv(BASE_DIR / ".env")

# SECURITY WARNING: change this before deploying to production!
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-change-me-before-deploying")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DJANGO_DEBUG", "True") == "True"

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',

    # our app FIRST so its templates/account/*.html override allauth's defaults
    'reader',

    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# ---- django-allauth config ----
ACCOUNT_LOGIN_METHODS = {'username', 'email'}
ACCOUNT_SIGNUP_FIELDS = ['username*', 'email*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = 'none'   # simplify for local/dev use
ACCOUNT_LOGOUT_ON_GET = True
LOGIN_REDIRECT_URL = 'reader:home'
LOGOUT_REDIRECT_URL = 'reader:home'
LOGIN_URL = 'account_login'

GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
        'OAUTH_PKCE_ENABLED': True,
    }
}

# Reading credentials from .env means you do NOT need to create a
# "Social Application" in /admin/ anymore - just fill in .env.
# We only attach APP when both values are actually set, so the login page
# correctly detects "not configured yet" and hides the Google button
# instead of showing a broken one.
if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
    SOCIALACCOUNT_PROVIDERS['google']['APP'] = {
        'client_id': GOOGLE_CLIENT_ID,
        'secret': GOOGLE_CLIENT_SECRET,
        'key': '',
    }

SOCIALACCOUNT_LOGIN_ON_GET = True  # skip the "confirm" intermediate page

ROOT_URLCONF = 'mangaweb.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'reader.context_processors.nav_genres',
                'reader.context_processors.site_settings',
                'reader.context_processors.notifications',
            ],
        },
    },
]

WSGI_APPLICATION = 'mangaweb.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'vi'
TIME_ZONE = 'Asia/Ho_Chi_Minh'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'reader' / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# ---- Thảo luận (group chat) media storage ----
# Images/videos posted in discussion groups are stored here (inside the
# app's own static tree, as requested) and served back out via STATIC_URL.
CHAT_MEDIA_ROOT_IMG = os.path.join(BASE_DIR, 'reader/static/reader/img_group')
CHAT_MEDIA_ROOT_VIDEO = os.path.join(BASE_DIR, 'reader/static/reader/video_group')
os.makedirs(CHAT_MEDIA_ROOT_IMG, exist_ok=True)
os.makedirs(CHAT_MEDIA_ROOT_VIDEO, exist_ok=True)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---- MangaDex API config ----
MANGADEX_API_BASE = 'https://api.mangadex.org'
MANGADEX_UPLOADS_BASE = 'https://uploads.mangadex.org'
MANGADEX_COVER_BASE = 'https://mangadex.org/covers'

# Simple in-process cache lifetime (seconds) for API responses
MANGADEX_CACHE_TTL = 300
MANGADEX_TAGS_CACHE_TTL = 60 * 60 * 12  # tag list barely changes, cache 12h

# Email: sends real emails via SMTP (e.g. Gmail) when EMAIL_HOST_USER /
# EMAIL_HOST_PASSWORD are set in .env. Falls back to printing emails in
# the terminal (no real email sent) when they're not — handy for local
# dev without needing real email credentials.
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')

if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
    EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
    EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
    DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
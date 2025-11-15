"""
Production Django settings for ovpn_project.
Inherits from base settings.py and overrides with production-specific settings.

Usage:
    export DJANGO_SETTINGS_MODULE=ovpn_project.settings_production
    python manage.py check --deploy
"""

from .settings import *  # noqa: F403, F401

# ============================================================================
# SECURITY SETTINGS
# ============================================================================

# CRITICAL: Set to False in production
DEBUG = False

# CRITICAL: Set your production domain
ALLOWED_HOSTS = env.list(  # noqa: F405
    "ALLOWED_HOSTS",
    default=["yourdomain.com", "www.yourdomain.com"]
)

# CRITICAL: Generate strong secret key (use: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
SECRET_KEY = env("SECRET_KEY")  # noqa: F405  # Must be set in .env file

# ============================================================================
# HTTPS / SSL SETTINGS
# ============================================================================

# Force HTTPS redirect
SECURE_SSL_REDIRECT = True

# HTTP Strict Transport Security (HSTS)
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Secure proxy SSL header (if behind nginx/apache)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ============================================================================
# COOKIE SECURITY
# ============================================================================

# Session cookie security
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
SESSION_COOKIE_AGE = 3600  # 1 hour

# CSRF cookie security
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Strict"

# ============================================================================
# CONTENT SECURITY
# ============================================================================

# Prevent clickjacking
X_FRAME_OPTIONS = "DENY"

# Browser security headers
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True

# ============================================================================
# PASSWORD VALIDATION
# ============================================================================

AUTH_PASSWORD_VALIDATORS = [  # noqa: F405
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 12,  # Increased from 8
        },
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# ============================================================================
# DATABASE SECURITY
# ============================================================================

# Use environment variables for database credentials
# For SQLite (development/testing):
if env.bool("USE_SQLITE", default=False):  # noqa: F405
    DATABASES = {  # noqa: F405
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
        }
    }
else:
    # PostgreSQL (production)
    DATABASES = {  # noqa: F405
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME", default="ovpn_db"),  # noqa: F405
            "USER": env("DB_USER", default="ovpn_user"),  # noqa: F405
            "PASSWORD": env("DB_PASSWORD", default=""),  # noqa: F405  # Set in .env
            "HOST": env("DB_HOST", default="localhost"),  # noqa: F405
            "PORT": env("DB_PORT", default="5432"),  # noqa: F405
            "CONN_MAX_AGE": 600,  # Connection pooling
            "OPTIONS": {
                "connect_timeout": 10,
            },
        }
    }

# ============================================================================
# LOGGING
# ============================================================================

LOGGING = {  # noqa: F405
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "level": "WARNING",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs" / "django.log",  # noqa: F405
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 5,
            "formatter": "verbose",
        },
        "mail_admins": {
            "level": "ERROR",
            "class": "django.utils.log.AdminEmailHandler",
            "filters": ["require_debug_false"],
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
        },
        "django.request": {
            "handlers": ["mail_admins", "file"],
            "level": "ERROR",
            "propagate": False,
        },
        "ovpn_app": {
            "handlers": ["console", "file"],
            "level": "INFO",
        },
    },
}

# ============================================================================
# FILE UPLOAD SECURITY
# ============================================================================

# Maximum upload size: 5 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5 MB

# Allowed file extensions for upload
ALLOWED_UPLOAD_EXTENSIONS = [".ovpn", ".conf", ".crt", ".key", ".pem"]

# ============================================================================
# RATE LIMITING
# ============================================================================

# Rate limiting for authentication (requires django-ratelimit)
RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = "default"

# ============================================================================
# CORS (if using API)
# ============================================================================

# Strict CORS policy
CORS_ALLOWED_ORIGINS = env.list(  # noqa: F405
    "CORS_ALLOWED_ORIGINS",
    default=["https://yourdomain.com"]
)

CORS_ALLOW_CREDENTIALS = True

# ============================================================================
# ADMIN SECURITY
# ============================================================================

# Email for admin notifications
ADMINS = [
    ("Admin", env("ADMIN_EMAIL", default="admin@example.com")),  # noqa: F405
]

# ============================================================================
# STATIC & MEDIA FILES
# ============================================================================

# Static files (collectstatic will put them here)
STATIC_ROOT = BASE_DIR / "staticfiles"  # noqa: F405

# Media files (user uploads) - should be served by nginx in production
MEDIA_ROOT = BASE_DIR / "media"  # noqa: F405

# ============================================================================
# CACHE
# ============================================================================

CACHES = {  # noqa: F405
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://127.0.0.1:6379/1"),  # noqa: F405
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

# ============================================================================
# EMAIL SETTINGS
# ============================================================================

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")  # noqa: F405
EMAIL_PORT = env.int("EMAIL_PORT", default=587)  # noqa: F405
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")  # noqa: F405
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")  # noqa: F405
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@example.com")  # noqa: F405

# ============================================================================
# DEBUG TOOLBAR (disabled in production)
# ============================================================================

if "debug_toolbar" in INSTALLED_APPS:  # noqa: F405
    INSTALLED_APPS.remove("debug_toolbar")  # noqa: F405

# Remove debug middleware if present
MIDDLEWARE = [m for m in MIDDLEWARE if "debug_toolbar" not in m]  # noqa: F405

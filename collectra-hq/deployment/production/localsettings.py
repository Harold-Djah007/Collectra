"""Environment-driven settings for the Collectra production stack."""

import os


def required(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Required environment variable is not set: {name}")
    return value


def integer(name, default):
    return int(os.environ.get(name, default))


COLLECTRA_HOST = required("COLLECTRA_HOST")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "commcarehq")
POSTGRES_PASSWORD = required("POSTGRES_PASSWORD")
COUCHDB_USER = os.environ.get("COUCHDB_USER", "collectra")
COUCHDB_PASSWORD = required("COUCHDB_PASSWORD")
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379")

DEBUG = False
SERVER_ENVIRONMENT = "production"
# Collectra is a self-hosted installation. HQ's enterprise mode uses the
# bundled Enterprise plan for every local project instead of SaaS billing.
ENTERPRISE_MODE = True
SECRET_KEY = required("DJANGO_SECRET_KEY")
BASE_ADDRESS = COLLECTRA_HOST
DEFAULT_PROTOCOL = "https"
ALLOWED_HOSTS = [COLLECTRA_HOST]
CSRF_TRUSTED_ORIGINS = [f"https://{COLLECTRA_HOST}"]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# Caddy is the only public entry point and performs the HTTP-to-HTTPS redirect.
# Keeping the internal web listener on HTTP allows Formplayer callbacks.
SECURE_SSL_REDIRECT = False

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "commcarehq"),
        "USER": POSTGRES_USER,
        "PASSWORD": POSTGRES_PASSWORD,
        "HOST": os.environ.get("POSTGRES_HOST", "postgres"),
        "PORT": integer("POSTGRES_PORT", 5432),
        "CONN_MAX_AGE": 60,
    },
}
USE_PARTITIONED_DATABASE = False

COUCH_DATABASES = {
    "default": {
        "COUCH_HTTPS": False,
        "COUCH_SERVER_ROOT": os.environ.get("COUCHDB_HOST", "couch:5984"),
        "COUCH_USERNAME": COUCHDB_USER,
        "COUCH_PASSWORD": COUCHDB_PASSWORD,
        "COUCH_DATABASE_NAME": os.environ.get("COUCHDB_DATABASE", "commcarehq"),
    },
}
BIGCOUCH = True

redis_cache = {
    "BACKEND": "django_redis.cache.RedisCache",
    "LOCATION": f"{REDIS_URL}/0",
    "REDIS_CLIENT_KWARGS": {"health_check_interval": 15},
    "TEST_LOCATION": f"{REDIS_URL}/2",
}
CACHES = {"default": redis_cache, "redis": redis_cache}
CELERY_BROKER_URL = f"{REDIS_URL}/1"
CELERY_TASK_ALWAYS_EAGER = False
CELERY_EAGER_PROPAGATES_EXCEPTIONS = False

ELASTICSEARCH_HOST = os.environ.get("ELASTICSEARCH_HOST", "elasticsearch6")
ELASTICSEARCH_PORT = integer("ELASTICSEARCH_PORT", 9200)
ELASTICSEARCH_MAJOR_VERSION = 6

MINIO_ROOT_USER = required("MINIO_ROOT_USER")
MINIO_ROOT_PASSWORD = required("MINIO_ROOT_PASSWORD")
S3_BLOB_DB_SETTINGS = {
    "url": os.environ.get("MINIO_URL", "http://minio:9980/"),
    "access_key": MINIO_ROOT_USER,
    "secret_key": MINIO_ROOT_PASSWORD,
    "config": {"connect_timeout": 5, "read_timeout": 30},
}

KAFKA_BROKERS = [os.environ.get("KAFKA_BROKER", "kafka:9092")]
SHARED_DRIVE_ROOT = "/sharedfiles"
LOG_HOME = os.path.join(SHARED_DRIVE_ROOT, "log")
COUCH_LOG_FILE = os.path.join(LOG_HOME, "commcarehq.couch.log")
DJANGO_LOG_FILE = os.path.join(LOG_HOME, "commcarehq.django.log")
ACCOUNTING_LOG_FILE = os.path.join(LOG_HOME, "commcarehq.accounting.log")
ANALYTICS_LOG_FILE = os.path.join(LOG_HOME, "commcarehq.analytics.log")
FORMPLAYER_TIMING_FILE = os.path.join(LOG_HOME, "formplayer.timing.log")
FORMPLAYER_DIFF_FILE = os.path.join(LOG_HOME, "formplayer.diff.log")
SOFT_ASSERTS_LOG_FILE = os.path.join(LOG_HOME, "soft_asserts.log")
MAIN_COUCH_SQL_DATAMIGRATION = os.path.join(LOG_HOME, "main_couch_sql_datamigration.log")

LOCAL_LOGGING_CONFIG = {
    "loggers": {
        "django": {"level": "INFO", "handlers": ["console"], "propagate": False},
        "notify": {"level": "ERROR", "handlers": ["console"], "propagate": False},
        "kafka": {"level": "WARNING", "handlers": ["console"], "propagate": False},
        "commcare_auth": {"level": "INFO", "handlers": ["console"], "propagate": False},
    },
    "root": {"level": "INFO", "handlers": ["console"]},
}

FORMPLAYER_URL = os.environ.get("FORMPLAYER_URL", "http://formplayer:8080")
FORMPLAYER_URL_WEBAPPS = f"https://{COLLECTRA_HOST}/formplayer"
FORMPLAYER_INTERNAL_AUTH_KEY = required("FORMPLAYER_AUTH_KEY")

EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)
EMAIL_LOGIN = os.environ.get("EMAIL_LOGIN", "")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_SMTP_HOST = os.environ.get("EMAIL_SMTP_HOST", "")
EMAIL_SMTP_PORT = integer("EMAIL_SMTP_PORT", 587)
EMAIL_USE_TLS = True
ADMINS = (("Collectra Administrator", required("COLLECTRA_ADMIN_EMAIL")),)

BITLY_OAUTH_TOKEN = None
ENABLE_PRELOGIN_SITE = True
UNIT_TESTING = False
PHONE_TIMEZONES_HAVE_BEEN_PROCESSED = True
PHONE_TIMEZONES_SHOULD_BE_PROCESSED = True
SKIP_TOUCHFORMS_TESTS = True
PILLOWTOP_MACHINE_ID = os.environ.get("PILLOWTOP_MACHINE_ID", "collectra-production")
CACHE_REPORTS = True
COMPRESS_OFFLINE = False
RESTORE_PAYLOAD_DIR_NAME = "restore"
SHARED_TEMP_DIR_NAME = "temp"
INACTIVITY_TIMEOUT = 60 * 24 * 365
REPORTING_DATABASES = {"default": "default", "ucr": "default", "aaa-data": "default"}

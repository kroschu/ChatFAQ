import os
from importlib import metadata

from urllib.parse import quote as urlquote
from model_w.env_manager import EnvManager
from model_w.preset.django import ModelWDjango
from dotenv import load_dotenv

load_dotenv()

MIDDLEWARE = []
INSTALLED_APPS = []
LOGGING = {}
STORAGES_MODE = os.getenv("STORAGES_MODE")
LOCAL_STORAGE = STORAGES_MODE == "local"


def get_package_version() -> str:
    """
    Trying to get the current package version using the metadata module. This
    assumes that the version is indeed set in pyproject.toml and that the
    package was cleanly installed.
    """

    try:
        return metadata.version("back")
    except metadata.PackageNotFoundError:
        return "0.0.0"


class CustomPreset(ModelWDjango):
    """
    We override the default ModelWDjango preset to add some custom logic:
    This project is being deployed in 2 different cloud providers,
    each one of them defines the environment variables for the databases
    (postgreSQL and Redis) in a different way, so we need to add some logic
    to handle this.
    """
    def _redis_url(self, env: EnvManager):
        if (_redis_url := env.get("REDIS_URL", default=None)) is None:
            proto = env.get("REDIS_PROTO", default="redis")
            user = env.get("REDIS_USER", default="")
            password = env.get("REDIS_PASSWORD", default="")
            host = env.get("REDIS_HOST", default="localhost")
            port = int(env.get("REDIS_PORT", default=6379))
            db = env.get("REDIS_DATABASE", default=0)

            if password:
                password = f":{urlquote(password)}"

            _redis_url = f"{proto}://{user}{password}@{host}:{port}/{db}"

        os.environ["REDIS_URL"] = _redis_url

        return _redis_url

    def pre_database(self, env: EnvManager):
        if all([
            (user := env.get("DATABASE_USER", default=None)),
            (password := env.get("DATABASE_PASSWORD", default=None)),
            (host := env.get("DATABASE_HOST", default=None)),
            (db := env.get("DATABASE_NAME", default=None)),
        ]):
            proto = env.get("DATABASE_PROTO", default="postgis" if self.enable_postgis else "postgres")
            port = int(env.get("DATABASE_PORT", default=5432))
            args = env.get("DATABASE_ARGS", default=None)

            password = urlquote(password)
            _url = f"{proto}://{user}:{password}@{host}:{port}/{db}"
            if args:
                _url += f"?{args}"
            os.environ["DATABASE_URL"] = _url
        return super().pre_database(env)

    def pre_channels(self, env: EnvManager):
        if not (channel_layers_config := next(super().pre_channels(env))):
            return channel_layers_config

        channel_layers_config[1]["default"]["BACKEND"] = "channels_redis.pubsub.RedisPubSubChannelLayer"
        channel_layers_config[1]["default"]["CONFIG"]["capacity"] = 1500
        channel_layers_config[1]["default"]["CONFIG"]["expiry"] = 5

        yield channel_layers_config


model_w_django = CustomPreset(enable_storages=not LOCAL_STORAGE, enable_celery=True)

with EnvManager(model_w_django) as env:
    # ---
    # Apps
    # ---

    INSTALLED_APPS += [
        "daphne",
        "django.contrib.admin",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "django.contrib.messages",
        "django.contrib.staticfiles",
        "django_extensions",
        "simple_history",
        "corsheaders",
        "django_better_admin_arrayfield",
        "rest_framework",
        "rest_framework.authtoken",
        "knox",
        "django_filters",
        "drf_spectacular",
        "drf_spectacular_sidecar",
        "back.apps.people",
        "back.apps.broker",
        "back.apps.fsm",
        "back.apps.language_model",
        "back.apps.widget",
    ]
    # if not env.get("REDIS_URL"):
    #     INSTALLED_APPS += [
    #         "channels_postgres",
    #     ]

    MIDDLEWARE += [
        "corsheaders.middleware.CorsMiddleware",
        "whitenoise.middleware.WhiteNoiseMiddleware",
        "simple_history.middleware.HistoryRequestMiddleware",
    ]

    CORS_ALLOW_ALL_ORIGINS = True

    # ---
    # Plumbing
    # ---

    ROOT_URLCONF = "back.config.urls"

    WSGI_APPLICATION = "back.config.wsgi.application"
    ASGI_APPLICATION = "back.config.asgi.application"

    # ---
    # Password validation
    # https://docs.djangoproject.com/en/3.2/ref/settings/#auth-password-validators
    # ---

    AUTH_PASSWORD_VALIDATORS = [
        {
            "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
        },
        {
            "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        },
        {
            "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
        },
        {
            "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
        },
    ]

    # ---
    # Auth
    # ---

    AUTH_USER_MODEL = "people.User"

    # ---
    # i18n
    # ---

    LANGUAGES = [
        ("en", "English"),
    ]

    # ---
    # OpenAPI Schema
    # ---
    REST_FRAMEWORK = {
        "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
        "DEFAULT_AUTHENTICATION_CLASSES": ("knox.auth.TokenAuthentication", "rest_framework.authentication.SessionAuthentication" ),
        'DEFAULT_PERMISSION_CLASSES': [
            'rest_framework.permissions.IsAuthenticated',
        ],
        "DEFAULT_FILTER_BACKENDS": [
            "django_filters.rest_framework.DjangoFilterBackend"
        ],
        'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
        'PAGE_SIZE': 50
    }

    SPECTACULAR_SETTINGS = {
        "TITLE": "ChatFAQ's back-end server",
        "VERSION": get_package_version(),
        "SERVE_INCLUDE_SCHEMA": False,
        "SWAGGER_UI_DIST": "SIDECAR",  # shorthand to use the sidecar instead
        "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
        "REDOC_DIST": "SIDECAR",
        'POSTPROCESSING_HOOKS': [
            'drf_spectacular.hooks.postprocess_schema_enums',
            'back.utils.spectacular_postprocessing_hooks.postprocess_schema_foreign_keys'
        ],
    }

    # ---
    # Django Channels
    # ---
    # For the moment postgres as channel layer is not supported
    """
    if not env.get("REDIS_URL"):
        CHANNEL_LAYERS = {
            "default": {
                "BACKEND": "back.utils.custom_channel_layer.CustomPostgresChannelLayer",
                "CONFIG": {
                    **db_config(conn_max_age=None),
                    "config": {
                        "maxsize": 0,  # unlimited pool size (but it recycles used connections of course)
                    },
                },
            },
        }
    """

    # ---
    # Logging
    # ---
    """
    SIMPLE_LOG = True
    LOGGING_CONFIG = "logging.config.dictConfig"
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {"()": "back.utils.logging_formatters.DjangoJsonFormatter"}
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json",
            },
        },
        "root": {
            "handlers": ["console"],
            "level": "DEBUG" if is_true(preset._debug(env)) else "INFO",
        },
    }
    """

    # ---
    # Telegram
    # ---

    TG_TOKEN = env.get("TG_TOKEN", default=None)
    # SPECTACULAR_SETTINGS = {
    #     "POSTPROCESSING_HOOKS": [
    #         "back.apps.broker.serializers.messages.custom_postprocessing_hook"
    #     ]
    # }

    REST_KNOX = {
        "TOKEN_TTL": None,
    }
    # Celery
    # CELERY_BROKER_URL = f"sqla+{env.get('DATABASE_URL')}"
    # from kombu.common import Broadcast
    # CELERY_QUEUES = (Broadcast('broadcast_tasks'),)
    # CELERY_ROUTES = {
    # }
    CELERY_WORKER_REDIRECT_STDOUTS = False
    CELERY_IMPORTS = ("back.apps.language_model.signals", )

    if LOCAL_STORAGE:
        MEDIA_URL = '/local_storage/'
        MEDIA_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "local_storage")
    else:
        # --------------------------- S3 ---------------------------
        AWS_S3_OBJECT_PARAMETERS = {
            "CacheControl": "max-age=86400",
        }
        DEFAULT_FILE_STORAGE = "back.config.storage_backends.PublicS3MediaStorage"
        PRIVATE_FILE_STORAGE = "back.config.storage_backends.PrivateS3MediaStorage"
        # Link expiration time in seconds
        AWS_QUERYSTRING_EXPIRE = "3600"
        AWS_S3_SIGNATURE_VERSION = env.get("AWS_S3_SIGNATURE_VERSION", default=None)
        AWS_S3_REGION_NAME = env.get("AWS_S3_REGION_NAME", default=None)

    # --------------------------- LLM APIs ---------------------------
    VLLM_ENDPOINT_URL = env.get("VLLM_ENDPOINT_URL", default=None)

    OPENAI_API_KEY = env.get("OPENAI_API_KEY", default=None)
    ANTHROPIC_API_KEY = env.get("ANTHROPIC_API_KEY", default=None)
    HUGGINGFACE_KEY = env.get("HUGGINGFACE_KEY", default=None)
    MISTRAL_API_KEY = env.get("MISTRAL_API_KEY", default=None)

    # --------------------------- RAY ---------------------------
    REMOTE_RAY_CLUSTER_ADDRESS_HEAD = env.get("REMOTE_RAY_CLUSTER_ADDRESS_HEAD", default=None)
    # If no REMOTE_RAY_CLUSTER_ADDRESS_HEAD is provided then
    # REMOTE_RAY_CLUSTER_ADDRESS_SERVE neither and we assume
    # that ray cluster runs locally from Django process (http://localhost:8001)
    RAY_SERVE_PORT = env.get("RAY_SERVE_PORT", default=8001)
    RAY_CLUSTER_HOST = env.get("RAY_CLUSTER_HOST", default="http://localhost")

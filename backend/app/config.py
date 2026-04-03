"""
app/config.py — Uygulama yapılandırma sınıfları.

.env dosyasından değerleri okur ve Flask config dict'ine aktarır.
Farklı ortamlar (geliştirme/üretim) için ayrı config sınıfları içerir.
"""

import os
from datetime import timedelta
from dotenv import load_dotenv

# .env dosyasını en erken aşamada yükle
load_dotenv()


class BaseConfig:
    """
    Tüm ortamlar için ortak temel yapılandırma.
    Kritik bir değer eksikse ValueError fırlatır — sessiz hata olmaz.
    """

    # --- Flask Çekirdeği ---
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "")
    PORT: int = int(os.environ.get("FLASK_PORT", 5000))
    DEBUG: bool = False

    # --- Veritabanı ---
    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "DATABASE_URL",
        "sqlite:///bilgeyolcu.db",
    )
    # Değişiklik izleme sinyalini kapat — performans kazancı
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    # --- JWT ---
    # JWT_SECRET_KEY önce kendi env var'ından, yoksa SECRET_KEY'den okur.
    # .env'de JWT_SECRET_KEY ayrı tanımlandıysa token sign/verify uyumsuzluğu olur.
    # Bu satır her iki durumu da doğru yönetir.
    JWT_SECRET_KEY: str = os.environ.get("JWT_SECRET_KEY") or os.environ.get("SECRET_KEY", "")
    JWT_ACCESS_TOKEN_EXPIRES: timedelta = timedelta(
        minutes=int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRES_MINUTES", 15))
    )
    JWT_REFRESH_TOKEN_EXPIRES: timedelta = timedelta(
        days=int(os.environ.get("JWT_REFRESH_TOKEN_EXPIRES_DAYS", 7))
    )
    # Token'ı header'da taşı (localStorage'da saklanacak)
    JWT_TOKEN_LOCATION: list = ["headers"]
    JWT_HEADER_NAME: str = "Authorization"
    JWT_HEADER_TYPE: str = "Bearer"


    # --- CORS (Vue.js geliştirme sunucusu için) ---
    CORS_ORIGINS: list = ["http://localhost:5173", "http://localhost:3000"]

    # --- Rate Limiting (brute-force koruması) ---
    RATELIMIT_STORAGE_URI: str = os.environ.get("REDIS_URL", "memory://")
    RATELIMIT_DEFAULT: str = "200 per day;50 per hour"

    # --- Maliyet Kontrolü ---
    DAILY_API_BUDGET: float = float(os.environ.get("DAILY_API_BUDGET", 2.00))
    BUDGET_WARNING_THRESHOLD: float = float(
        os.environ.get("BUDGET_WARNING_THRESHOLD", 0.80)
    )

    # --- LLM Modelleri ---
    PRIMARY_MODEL: str = os.environ.get("PRIMARY_MODEL", "gemini-2.5-flash")
    FALLBACK_MODEL_1: str = os.environ.get("FALLBACK_MODEL_1", "claude-haiku-3-5")
    FALLBACK_MODEL_2: str = os.environ.get("FALLBACK_MODEL_2", "gpt-4o-mini")

    # --- XenForo REST API ---
    XENFORO_BASE_URL:       str  = os.environ.get("XENFORO_BASE_URL", "")
    XENFORO_API_KEY:        str  = os.environ.get("XENFORO_API_KEY", "")
    XENFORO_ADMIN_USER_ID:  int  = int(os.environ.get("XENFORO_ADMIN_USER_ID", 1))
    XENFORO_VERIFY_SSL:     bool = os.environ.get("XENFORO_VERIFY_SSL", "True").lower() != "false"
    XENFORO_WEBROOT:        str  = os.environ.get("XENFORO_WEBROOT", "")
    XENFORO_DEFAULT_NODE_ID: int = int(os.environ.get("XENFORO_DEFAULT_NODE_ID", 0))

    # --- Dosya İzin Güvenliği ---
    ALLOWED_EDIT_PATH: str = os.environ.get("ALLOWED_EDIT_PATH", "")

    # --- Telegram ---
    TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.environ.get("TELEGRAM_CHAT_ID", "")

    # --- SSH Sunucu Bağlantısı ---
    SSH_HOST:                  str = os.environ.get("SSH_HOST", "")
    SSH_PORT:                  int = int(os.environ.get("SSH_PORT", 22))
    SSH_USERNAME:              str = os.environ.get("SSH_USERNAME", "root")
    SSH_PASSWORD:              str = os.environ.get("SSH_PASSWORD", "")
    SSH_PRIVATE_KEY_PATH:      str = os.environ.get("SSH_PRIVATE_KEY_PATH", "")
    SSH_PRIVATE_KEY_PASSPHRASE:str = os.environ.get("SSH_PRIVATE_KEY_PASSPHRASE", "")
    SSH_KNOWN_HOSTS_PATH:      str = os.environ.get("SSH_KNOWN_HOSTS_PATH", "")
    # PHP yorumlayıcı yolu (cPanel: /usr/local/bin/ea-php83 vb.)
    SSH_PHP_BIN:               str = os.environ.get("SSH_PHP_BIN", "php")
    # XenForo CLI komut override
    SSH_XF_UPGRADE_CMD:        str = os.environ.get("SSH_XF_UPGRADE_CMD", "")
    SSH_XF_MAINT_ON_CMD:       str = os.environ.get("SSH_XF_MAINT_ON_CMD", "")
    SSH_XF_MAINT_OFF_CMD:      str = os.environ.get("SSH_XF_MAINT_OFF_CMD", "")

    # --- Deploy Webhook ---
    DEPLOY_WEBHOOK_SECRET: str = os.environ.get("DEPLOY_WEBHOOK_SECRET", "")

    # --- MySQL (yedekleme için) ---
    MYSQL_HOST:     str = os.environ.get("MYSQL_HOST",     "localhost")
    MYSQL_USER:     str = os.environ.get("MYSQL_USER",     "")
    MYSQL_PASSWORD: str = os.environ.get("MYSQL_PASSWORD", "")
    MYSQL_DATABASE: str = os.environ.get("MYSQL_DATABASE", "")

    # --- Yedek Dizini ---
    BACKUP_DIR: str = os.environ.get("BACKUP_DIR", "")

    @classmethod
    def validate(cls) -> None:
        """
        Zorunlu ortam değişkenlerinin varlığını doğrular.
        Eksik kritik değişken varsa uygulama başlamaz.
        """
        required = {
            "SECRET_KEY": cls.SECRET_KEY,
        }
        missing = [key for key, val in required.items() if not val]
        if missing:
            raise ValueError(
                f"[CONFIG] Zorunlu ortam değişkenleri eksik: {', '.join(missing)}\n"
                ".env.example dosyasını .env olarak kopyalayıp doldurun."
            )


class DevelopmentConfig(BaseConfig):
    """
    Geliştirme ortamı — Windows'ta Redis, SSH olmadan çalışır.
    FLASK_ENV=development ile aktif olur.
    """
    DEBUG = True

    # Redis gerektirmeyen memory backend (lokalde Redis yoksa)
    RATELIMIT_STORAGE_URI: str = "memory://"

    # Celery görevleri broker olmadan synchronous çalışır
    # (Redis bağlantısı gerektirmez, test için ideal)
    CELERY_TASK_ALWAYS_EAGER:     bool = True
    CELERY_TASK_EAGER_PROPAGATES: bool = True
    CELERY_BROKER_URL:      str = "memory://"
    CELERY_RESULT_BACKEND:  str = "cache+memory://"

    # Veritabanı — platform bağımsız göreli yol (cross-platform)
    # Windows'ta: sqlite:///C:/Users/.../backend/bilgeyolcu.db
    # Linux'ta:   sqlite:////home/.../backend/bilgeyolcu.db
    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "bilgeyolcu.db")
        )
    )

    # SQL sorgularını debug için True yap
    SQLALCHEMY_ECHO: bool = False



class ProductionConfig(BaseConfig):
    """
    Üretim ortamı — cPanel Passenger üzerinde çalışır.

    Redis durumuna göre otomatik fallback:
      - REDIS_URL tanımlıysa → Redis (rate limit + Celery broker)
      - REDIS_URL boşsa     → memory:// + synchronous Celery
    """
    DEBUG = False

    # Üretimde CORS sadece kendi domainimize izin versin
    CORS_ORIGINS: list = [
        "https://bilgeyolcu.com",
        "https://www.bilgeyolcu.com",
    ]

    # ── Rate Limiting ─────────────────────────────────────────
    # Redis varsa Redis'i kullan, yoksa memory (tek process Passenger
    # için yeterli). Birden fazla worker varsa Redis şart.
    RATELIMIT_STORAGE_URI: str = os.environ.get("REDIS_URL", "memory://")

    # ── Celery ────────────────────────────────────────────────
    # Redis varsa async çalışır; yoksa synchronous (eager) mod.
    _redis = os.environ.get("REDIS_URL", "")
    CELERY_BROKER_URL:      str = os.environ.get("CELERY_BROKER_URL", _redis or "memory://")
    CELERY_RESULT_BACKEND:  str = os.environ.get("CELERY_RESULT_BACKEND", _redis or "cache+memory://")
    CELERY_TASK_ALWAYS_EAGER: bool = not bool(_redis)
    CELERY_TASK_EAGER_PROPAGATES: bool = True

    # ── Veritabanı ────────────────────────────────────────────
    # cPanel'de mutlak yol: /home/bilgeyolcu/bilge-panel/backend/bilgeyolcu.db
    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "bilgeyolcu.db")
        )
    )
    SQLALCHEMY_ECHO: bool = False

    # ── Güvenlik Sertleştirmeleri ─────────────────────────────
    # Session cookie sadece HTTPS üzerinden gönder
    SESSION_COOKIE_SECURE: bool = True
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"


# Ortama göre config seçimi
_config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}


def get_config():
    """
    FLASK_ENV ortam değişkenine göre uygun config sınıfını döndürür.
    Varsayılan: ProductionConfig (güvenli taraf)
    """
    env = os.environ.get("FLASK_ENV", "production").lower()
    config_class = _config_map.get(env, ProductionConfig)
    config_class.validate()
    return config_class

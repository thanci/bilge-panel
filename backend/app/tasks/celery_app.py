"""
app/tasks/celery_app.py — Celery fabrikası ve Flask bağlamı entegrasyonu.

Kritik Tasarım: FlaskContextTask
  Her Celery task'ı Flask uygulama bağlamı (app context) içinde çalışmalıdır.
  Aksi hâlde db, current_app, config gibi Flask araçlarına erişilemez.
  Bu sorun FlaskContextTask base class'ı ile çözülür.

Celery Worker Başlatma:
  Geliştirme:
    celery -A celery_worker.celery worker --loglevel=info --concurrency=2

  Üretim (systemd):
    celery -A celery_worker.celery worker \\
        --loglevel=info --concurrency=2 --detach \\
        --logfile=/home/<user>/logs/celery.log \\
        --pidfile=/home/<user>/run/celery.pid

Celery Beat (Zamanlanmış Görevler):
  celery -A celery_worker.celery beat --loglevel=info
"""

import logging
from celery import Celery
from celery.schedules import crontab

logger = logging.getLogger(__name__)

# Celery örneği — Flask app bağlanana kadar yapılandırılmamış
# Bu nesne celery_worker.py tarafından init_celery() ile tam hâle getirilir
celery = Celery(__name__)


def init_celery(flask_app) -> Celery:
    """
    Celery'yi Flask uygulamasına bağlar.
    app/__init__.py'deki create_app() ve celery_worker.py tarafından çağrılır.

    Args:
        flask_app: Flask uygulama örneği (create_app() çıktısı)

    Returns:
        Yapılandırılmış Celery örneği
    """
    # ---- Celery Yapılandırması -------------------------------------------
    celery.conf.update(
        broker_url            = flask_app.config["CELERY_BROKER_URL"],
        result_backend        = flask_app.config["CELERY_RESULT_BACKEND"],

        # Görev serileştirme: JSON (güvenli, okunabilir)
        task_serializer       = "json",
        result_serializer     = "json",
        accept_content        = ["json"],

        # Saat dilimi: Bilge Yolcu Türkiye'de
        timezone              = "Europe/Istanbul",
        enable_utc            = True,

        # Sonuçları Redis'te 24 saat sakla
        result_expires        = 86400,

        # Görev başarısızsa sonucunu sakla (dashboard için)
        task_store_errors_even_if_ignored = True,

        # Çalışan task sayısı — aşırı API çağrısını önler
        # Her worker 2 görev eş zamanlı çalıştırır
        worker_concurrency    = 2,

        # Rate limit: dakikada maksimum 10 LLM görevi
        # Bireysel task'larda task.rate_limit ile ince ayar yapılır
        task_default_rate_limit = "10/m",

        # Zamanlanmış görevler (Celery Beat)
        beat_schedule         = {
            # Her gece 00:01'de bütçeyi sıfırla
            "reset-daily-budget-midnight": {
                "task":     "app.tasks.maintenance.reset_daily_budget_task",
                "schedule": crontab(hour=0, minute=1),
            },
            # Her gece 03:00'da eski blocklist kayıtlarını temizle
            "cleanup-token-blocklist": {
                "task":     "app.tasks.maintenance.cleanup_token_blocklist_task",
                "schedule": crontab(hour=3, minute=0),
            },
        },
    )

    # ---- Flask App Context Entegrasyonu ------------------------------------
    class FlaskContextTask(celery.Task):
        """
        Tüm Celery task'larının base class'ı.
        Her task çağrısını Flask uygulama bağlamına sarar.

        Bu sayede task içinde:
          - current_app.config["PRIMARY_MODEL"] kullanılabilir
          - db.session erişilebilir
          - BudgetGuard veritabanı işlemleri çalışır
        """
        abstract = True

        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return self.run(*args, **kwargs)

        def on_failure(self, exc, task_id, args, kwargs, einfo):
            """
            Task başarısız olduğunda çağrılır.
            TaskLog'u günceller ve Telegram bildirim gönderir.
            """
            with flask_app.app_context():
                try:
                    from app.tasks.helpers import update_task_status
                    update_task_status(task_id, "FAILED", error_msg=str(exc))
                except Exception as update_err:
                    logger.error(f"[CELERY] on_failure güncelleme hatası: {update_err}")

    # Tüm task'lar bu base class'ı kullanacak
    celery.Task = FlaskContextTask

    logger.info(
        f"[CELERY] Celery başlatıldı | "
        f"broker={flask_app.config.get('CELERY_BROKER_URL', 'N/A')[:30]}..."
    )
    return celery

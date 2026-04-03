"""
celery_worker.py — Celery worker başlatma giriş noktası.

Bu dosya, Flask uygulamasını oluşturur ve Celery'ye bağlar.
Celery CLI bu dosyayı kullanarak worker başlatır.

Kullanım:
  Geliştirme:
    celery -A celery_worker.celery worker --loglevel=info --concurrency=2

  Zamanlanmış görevler (Celery Beat):
    celery -A celery_worker.celery beat --loglevel=info

  Hem worker hem beat (sadece geliştirme için — üretimde ayrı çalıştırın):
    celery -A celery_worker.celery worker --beat --loglevel=info

Üretim systemd servisi için:
  /etc/systemd/system/bilgeyolcu-celery.service dosyasına bakın.
"""

from app import create_app
from app.tasks.celery_app import celery, init_celery

# Flask uygulamasını başlat ve Celery'ye bağla
flask_app = create_app()
init_celery(flask_app)

# Task modüllerini import et — Celery'nin görevleri keşfetmesi için
# Bu importlar ContextTask base class'ından faydalanabilmesi için celery_app
# BAŞLATILDIKTAN SONRA yapılmalıdır.
import app.tasks.youtube       # noqa: F401, E402
import app.tasks.ai_writer     # noqa: F401, E402
import app.tasks.maintenance   # noqa: F401, E402

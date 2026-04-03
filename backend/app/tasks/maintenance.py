"""
app/tasks/maintenance.py — Bakım ve temizlik görevleri.
Celery Beat tarafından zamanlanmış olarak çalıştırılır.
"""

import logging
from datetime import datetime, timezone, timedelta

from app.tasks.celery_app import celery
from app.extensions import db
from app.models import TokenBlocklist

logger = logging.getLogger(__name__)


@celery.task(
    name  = "app.tasks.maintenance.reset_daily_budget_task",
    bind  = True,
    max_retries = 2,
)
def reset_daily_budget_task(self):
    """
    Gece 00:01'de çalışır. Günlük bütçeyi sıfırlar ve
    Circuit Breaker'ı CLOSED'a döndürür.
    """
    try:
        from app.budget.guard import BudgetGuard
        result = BudgetGuard.reset_daily()
        logger.info(f"[MAINTENANCE] Bütçe reset: {result}")
        return result
    except Exception as exc:
        logger.error(f"[MAINTENANCE] Bütçe reset hatası: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60)


@celery.task(
    name  = "app.tasks.maintenance.cleanup_token_blocklist_task",
    bind  = True,
    max_retries = 2,
)
def cleanup_token_blocklist_task(self):
    """
    Gece 03:00'da çalışır. 30 günden eski JWT blocklist kayıtlarını temizler.
    Tablo büyümesini önler.
    """
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        deleted = TokenBlocklist.query.filter(
            TokenBlocklist.revoked_at < cutoff
        ).delete()
        db.session.commit()
        logger.info(f"[MAINTENANCE] {deleted} eski JWT blocklist kaydı silindi.")
        return {"deleted": deleted}
    except Exception as exc:
        db.session.rollback()
        logger.error(f"[MAINTENANCE] Blocklist temizleme hatası: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=300)

"""
app/tasks/helpers.py — Celery görev yardımcı fonksiyonları.

Bu modül, tüm task'larda tekrarlayan işlemleri merkezileştirir:
  - TaskLog oluşturma ve durum güncelleme
  - Hata loglama standartları
  - Payload doğrulama yardımcıları
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from app.extensions import db
from app.models import TaskLog

logger = logging.getLogger(__name__)


def create_task_log(
    task_id: str,
    task_type: str,
    payload: Optional[dict] = None,
) -> TaskLog:
    """
    Yeni bir TaskLog kaydı oluşturur ve veritabanına yazar.
    Task başlamadan önce çağrılır (durum: QUEUED).
    """
    try:
        log = TaskLog(
            task_id    = task_id,
            task_type  = task_type,
            status     = "QUEUED",
            payload    = json.dumps(payload or {}, ensure_ascii=False),
            created_at = datetime.now(timezone.utc),
        )
        db.session.add(log)
        db.session.commit()
        return log
    except Exception as e:
        db.session.rollback()
        logger.error(f"[TASKS] TaskLog oluşturma hatası: {e}", exc_info=True)
        # TaskLog oluşturulamazsa task çalışmaya devam etsin
        return None


def update_task_status(
    task_id: str,
    status: str,
    result: Optional[dict] = None,
    error_msg: Optional[str] = None,
    model_used: Optional[str] = None,
    cost_usd: Optional[float] = None,
) -> bool:
    """
    TaskLog'un durumunu günceller. Sadece değişen alanları yazar.

    Args:
        task_id:    Celery task UUID
        status:     "RUNNING" | "SUCCESS" | "FAILED" | "REVOKED"
        result:     Başarı sonucu (dict)
        error_msg:  Hata mesajı
        model_used: Kullanılan LLM modeli
        cost_usd:   Toplam maliyet

    Returns:
        True → güncelleme başarılı, False → kayıt bulunamadı veya hata
    """
    try:
        log = TaskLog.query.filter_by(task_id=task_id).first()
        if not log:
            logger.warning(f"[TASKS] TaskLog bulunamadı: task_id={task_id[:8]}")
            return False

        log.status = status

        if status == "RUNNING" and not log.started_at:
            log.started_at = datetime.now(timezone.utc)

        if status in ("SUCCESS", "FAILED", "REVOKED"):
            log.finished_at = datetime.now(timezone.utc)

        if result is not None:
            log.result = json.dumps(result, ensure_ascii=False)
        if error_msg is not None:
            log.error_msg = error_msg[:2000]   # DB alan sınırı
        if model_used is not None:
            log.model_used = model_used
        if cost_usd is not None:
            log.cost_usd = cost_usd

        db.session.commit()
        return True

    except Exception as e:
        db.session.rollback()
        logger.error(f"[TASKS] TaskLog güncelleme hatası ({task_id[:8]}): {e}")
        return False


def get_task_log(task_id: str) -> Optional[dict]:
    """Bir task'ın detaylarını döndürür (payload + result dahil)."""
    try:
        log = TaskLog.query.filter_by(task_id=task_id).first()
        return log.to_dict(include_content=True) if log else None
    except Exception as e:
        logger.error(f"[TASKS] TaskLog okuma hatası: {e}")
        return None


def list_recent_tasks(limit: int = 20, task_type: Optional[str] = None) -> list:
    """Son N görevi döndürür. Dashboard görev kuyruğu için."""
    try:
        query = TaskLog.query
        if task_type:
            query = query.filter_by(task_type=task_type)
        logs = query.order_by(TaskLog.created_at.desc()).limit(limit).all()
        return [log.to_dict() for log in logs]
    except Exception as e:
        logger.error(f"[TASKS] Task listesi okuma hatası: {e}")
        return []

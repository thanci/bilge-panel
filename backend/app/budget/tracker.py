"""
app/budget/tracker.py — Maliyet okuma ve raporlama yardımcıları.

Bu modül Dashboard'un bütçe bileşenlerine veri sağlar:
  - Son N günlük harcama geçmişi (grafik verisi)
  - Model bazında harcama dağılımı
  - Task tipine göre maliyet analizi
  - Toplam istatistikler

Not: Maliyet YAZMA işlemleri guard.py'dedir.
     Bu modül yalnızca OKUMA/RAPORLAMA içerir.
"""

import logging
from datetime import date, timedelta

from sqlalchemy import func, text

from app.extensions import db
from app.models import ApiCostLog, DailyBudget, TaskLog

logger = logging.getLogger(__name__)


def get_daily_history(days: int = 7) -> list[dict]:
    """
    Son N güne ait günlük harcama geçmişini döndürür.
    Dashboard'daki "7 Günlük Harcama" grafiği için kullanılır.

    Args:
        days: Kaç günlük geçmiş isteniyor (varsayılan: 7)

    Returns:
        Tarih sırasına göre sıralanmış günlük harcama listesi:
        [
            {"date": "2025-03-28", "spent_usd": 0.45, "limit_usd": 2.00, "usage_pct": 22.5},
            {"date": "2025-03-29", "spent_usd": 1.12, ...},
            ...
        ]
    """
    try:
        today = date.today()
        # Tüm istenen günleri listele (veri olmayan günler 0.0 harcama gösterir)
        date_range = [
            (today - timedelta(days=i)).isoformat()
            for i in range(days - 1, -1, -1)
        ]

        # Veritabanından mevcut kayıtları çek
        records = DailyBudget.query.filter(
            DailyBudget.date.in_(date_range)
        ).all()
        records_by_date = {r.date: r for r in records}

        # Eksik günleri sıfırla doldur
        result = []
        for d in date_range:
            if d in records_by_date:
                result.append(records_by_date[d].to_dict())
            else:
                # Bu gün için kayıt yok — sıfır harcama
                result.append({
                    "date":          d,
                    "spent_usd":     0.0,
                    "limit_usd":     2.00,   # Varsayılan
                    "remaining_usd": 2.00,
                    "usage_pct":     0.0,
                    "breaker_state": "N/A",
                })

        return result

    except Exception as e:
        logger.error(f"[TRACKER] get_daily_history hatası: {e}", exc_info=True)
        return []


def get_cost_by_model(days: int = 7) -> list[dict]:
    """
    Son N günde her LLM modeli için toplam harcamayı döndürür.
    Dashboard'daki pasta grafiği için kullanılır.

    Returns:
        [
            {"model": "gemini-2.5-flash", "total_usd": 0.85, "call_count": 12},
            {"model": "claude-haiku-3-5", "total_usd": 0.22, "call_count": 3},
        ]
    """
    try:
        cutoff = (date.today() - timedelta(days=days)).isoformat()

        rows = (
            db.session.query(
                ApiCostLog.model,
                func.sum(ApiCostLog.cost_usd).label("total_usd"),
                func.count(ApiCostLog.id).label("call_count"),
            )
            .filter(
                ApiCostLog.status == "success",
                ApiCostLog.created_at >= cutoff,
            )
            .group_by(ApiCostLog.model)
            .order_by(func.sum(ApiCostLog.cost_usd).desc())
            .all()
        )

        return [
            {
                "model":      row.model,
                "total_usd":  round(row.total_usd or 0, 4),
                "call_count": row.call_count,
            }
            for row in rows
        ]

    except Exception as e:
        logger.error(f"[TRACKER] get_cost_by_model hatası: {e}", exc_info=True)
        return []


def get_cost_by_task_type(days: int = 7) -> list[dict]:
    """
    Son N günde görev tipine göre maliyet dağılımını döndürür.
    Hangi içerik türünün daha pahalı olduğunu analiz eder.

    Returns:
        [
            {"task_type": "youtube_summary", "total_usd": 0.65, "count": 8},
            {"task_type": "ai_article",      "total_usd": 0.42, "count": 5},
        ]
    """
    try:
        cutoff = (date.today() - timedelta(days=days)).isoformat()

        # TaskLog ve ApiCostLog JOIN ile task tipi bilgisini al
        rows = (
            db.session.query(
                TaskLog.task_type,
                func.sum(TaskLog.cost_usd).label("total_usd"),
                func.count(TaskLog.task_id).label("count"),
            )
            .filter(
                TaskLog.status == "SUCCESS",
                TaskLog.created_at >= cutoff,
                TaskLog.cost_usd.isnot(None),
            )
            .group_by(TaskLog.task_type)
            .order_by(func.sum(TaskLog.cost_usd).desc())
            .all()
        )

        return [
            {
                "task_type": row.task_type,
                "total_usd": round(row.total_usd or 0, 4),
                "count":     row.count,
            }
            for row in rows
        ]

    except Exception as e:
        logger.error(f"[TRACKER] get_cost_by_task_type hatası: {e}", exc_info=True)
        return []


def get_recent_cost_logs(limit: int = 20) -> list[dict]:
    """
    En son N maliyet kaydını döndürür.
    Dashboard'daki maliyet tablosu için kullanılır.
    """
    try:
        logs = (
            ApiCostLog.query
            .filter(ApiCostLog.status != "pre_flight")  # Sadece tamamlananları göster
            .order_by(ApiCostLog.created_at.desc())
            .limit(limit)
            .all()
        )
        return [log.to_dict() for log in logs]

    except Exception as e:
        logger.error(f"[TRACKER] get_recent_cost_logs hatası: {e}", exc_info=True)
        return []


def get_summary_stats() -> dict:
    """
    Genel özet istatistikleri döndürür.
    Dashboard'un üst kart bileşenleri için kullanılır.

    Returns:
        {
            "today_spent": 1.24,
            "today_limit": 2.00,
            "today_calls": 15,
            "total_spent_all_time": 48.35,
            "blocked_calls_today": 2,
        }
    """
    try:
        today_str = date.today().isoformat()
        daily = DailyBudget.query.filter_by(date=today_str).first()

        # Bugünkü başarılı çağrı sayısı
        today_calls = ApiCostLog.query.filter(
            ApiCostLog.created_at >= today_str,
            ApiCostLog.status == "success",
        ).count()

        # Bugün bütçe nedeniyle engellenen görev sayısı
        blocked_today = ApiCostLog.query.filter(
            ApiCostLog.created_at >= today_str,
            ApiCostLog.status == "blocked_by_budget",
        ).count()

        # Tüm zamanların toplam harcaması
        total_all_time = db.session.query(
            func.sum(ApiCostLog.cost_usd)
        ).filter(ApiCostLog.status == "success").scalar() or 0.0

        return {
            "today_spent":          round(daily.spent_usd, 4) if daily else 0.0,
            "today_limit":          round(daily.limit_usd, 4) if daily else 2.00,
            "today_calls":          today_calls,
            "blocked_calls_today":  blocked_today,
            "total_spent_all_time": round(total_all_time, 4),
            "breaker_state":        daily.breaker_state if daily else "CLOSED",
        }

    except Exception as e:
        logger.error(f"[TRACKER] get_summary_stats hatası: {e}", exc_info=True)
        return {
            "today_spent":          0.0,
            "today_limit":          2.00,
            "today_calls":          0,
            "blocked_calls_today":  0,
            "total_spent_all_time": 0.0,
            "breaker_state":        "UNKNOWN",
            "error":                str(e),
        }

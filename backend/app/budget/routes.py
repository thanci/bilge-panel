"""
app/budget/routes.py — Bütçe yönetimi API endpointleri.

Endpoint'ler:
  GET  /api/budget/status       — Anlık bütçe ve Circuit Breaker durumu
  GET  /api/budget/history      — Son N günlük harcama geçmişi (grafik verisi)
  GET  /api/budget/breakdown    — Model ve görev tipi bazında harcama dağılımı
  GET  /api/budget/logs         — Son maliyet kayıtları
  POST /api/budget/reset        — Circuit Breaker'ı manuel sıfırla (tehlikeli!)
  GET  /api/budget/stats        — Dashboard kart istatistikleri

Tüm endpoint'ler @require_auth ile korunmuştur.
"""

import logging
from flask import jsonify, request, g

from app.budget import budget_bp
from app.auth.decorators import require_auth
from app.budget.guard import BudgetGuard
from app.budget.tracker import (
    get_daily_history,
    get_cost_by_model,
    get_cost_by_task_type,
    get_recent_cost_logs,
    get_summary_stats,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# GET /api/budget/status — Anlık Durum
# ──────────────────────────────────────────────────────────────

@budget_bp.route("/status", methods=["GET"])
@require_auth
def budget_status():
    """
    Circuit Breaker durumu ve anlık bütçe bilgisi.
    Dashboard'un üst kısımdaki bütçe göstergesi bu endpoint'i kullanır.
    Her 10-30 saniyede bir Vue.js tarafından polling yapılır.

    Yanıt (200):
    {
        "success": true,
        "data": {
            "date": "2025-04-03",
            "spent_usd": 1.24,
            "limit_usd": 2.00,
            "remaining_usd": 0.76,
            "usage_pct": 62.0,
            "breaker_state": "CLOSED",
            "is_blocked": false
        }
    }
    """
    try:
        status = BudgetGuard.get_status()
        return jsonify({"success": True, "data": status}), 200
    except Exception as e:
        logger.error(f"[BUDGET API] /status hatası: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error":   "budget_status_error",
            "message": "Bütçe durumu alınamadı.",
        }), 500


# ──────────────────────────────────────────────────────────────
# GET /api/budget/history?days=7
# ──────────────────────────────────────────────────────────────

@budget_bp.route("/history", methods=["GET"])
@require_auth
def budget_history():
    """
    Son N günlük harcama geçmişi. Dashboard'daki çizgi/bar grafiği için.
    Sorgu parametresi: ?days=7 (varsayılan), max 30.
    """
    try:
        days = int(request.args.get("days", 7))
        days = max(1, min(days, 30))   # 1-30 arasında sınırla

        history = get_daily_history(days=days)
        return jsonify({"success": True, "data": history}), 200
    except Exception as e:
        logger.error(f"[BUDGET API] /history hatası: {e}", exc_info=True)
        return jsonify({"success": False, "error": "history_error"}), 500


# ──────────────────────────────────────────────────────────────
# GET /api/budget/breakdown?days=7
# ──────────────────────────────────────────────────────────────

@budget_bp.route("/breakdown", methods=["GET"])
@require_auth
def budget_breakdown():
    """
    Model ve görev tipi bazında harcama dağılımı.
    Dashboard'daki pasta grafiği için.
    """
    try:
        days = int(request.args.get("days", 7))
        days = max(1, min(days, 30))

        data = {
            "by_model":     get_cost_by_model(days=days),
            "by_task_type": get_cost_by_task_type(days=days),
        }
        return jsonify({"success": True, "data": data}), 200
    except Exception as e:
        logger.error(f"[BUDGET API] /breakdown hatası: {e}", exc_info=True)
        return jsonify({"success": False, "error": "breakdown_error"}), 500


# ──────────────────────────────────────────────────────────────
# GET /api/budget/logs?limit=20
# ──────────────────────────────────────────────────────────────

@budget_bp.route("/logs", methods=["GET"])
@require_auth
def budget_logs():
    """Son maliyet kayıtlarını döndürür. Varsayılan: son 20 kayıt."""
    try:
        limit = int(request.args.get("limit", 20))
        limit = max(1, min(limit, 100))

        logs = get_recent_cost_logs(limit=limit)
        return jsonify({"success": True, "data": logs}), 200
    except Exception as e:
        logger.error(f"[BUDGET API] /logs hatası: {e}", exc_info=True)
        return jsonify({"success": False, "error": "logs_error"}), 500


# ──────────────────────────────────────────────────────────────
# GET /api/budget/stats
# ──────────────────────────────────────────────────────────────

@budget_bp.route("/stats", methods=["GET"])
@require_auth
def budget_stats():
    """Dashboard kart istatistikleri — özet sayılar."""
    try:
        stats = get_summary_stats()
        return jsonify({"success": True, "data": stats}), 200
    except Exception as e:
        logger.error(f"[BUDGET API] /stats hatası: {e}", exc_info=True)
        return jsonify({"success": False, "error": "stats_error"}), 500


# ──────────────────────────────────────────────────────────────
# POST /api/budget/reset — TEHLİKELİ: Manuel Circuit Breaker Reset
# ──────────────────────────────────────────────────────────────

@budget_bp.route("/reset", methods=["POST"])
@require_auth
def budget_reset():
    """
    Circuit Breaker'ı manuel olarak CLOSED konumuna sıfırlar.

    ⚠️ UYARI: Bu endpoint bütçe limitini SIFIRLAMAZ —
    sadece erişim kilidini açar. Bütçe doluyken açarsanız
    anında tekrar kilitlenebilir.

    Yanıt gövdesi gerekmiyor (POST body boş olabilir).
    """
    try:
        admin = g.current_user
        result = BudgetGuard.manual_reset(admin_username=admin.username)
        return jsonify({"success": True, "data": result}), 200
    except Exception as e:
        logger.error(f"[BUDGET API] /reset hatası: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error":   "reset_failed",
            "message": f"Circuit Breaker sıfırlanamadı: {str(e)}",
        }), 500

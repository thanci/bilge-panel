"""
app/routes/health.py — Sistem sağlık kontrolü endpointleri.

Endpoint'ler:
  GET /api/health          — Genel sistem durumu (herkese açık)
  GET /api/health/auth     — Kimlik doğrulama gerektiren sağlık kontrolü

Bu endpoint'ler;
  - Apache Health Monitor tarafından periyodik olarak sorgulanabilir.
  - Vue.js Dashboard'un backend bağlantısını doğrulamak için kullanılır.
  - Celery ve Redis bağlantı durumunu da rapor eder (Aşama 3'te genişler).
"""

from datetime import datetime, timezone

from flask import jsonify, current_app

from app.routes import main_bp
from app.auth.decorators import require_auth
from app.extensions import db


@main_bp.route("/health", methods=["GET"])
def health_check():
    """
    Herkese açık temel sağlık kontrolü.
    Load balancer veya uptime monitor bu endpoint'i kullanır.
    
    Yanıt (200 OK):
        {
            "success": true,
            "data": {
                "status": "healthy",
                "timestamp": "2025-04-03T10:00:00+00:00",
                "services": {
                    "database": "ok",
                    "redis": "not_configured"
                }
            }
        }
    """
    services = {}

    # --- Veritabanı Bağlantı Kontrolü ---
    try:
        db.session.execute(db.text("SELECT 1"))
        services["database"] = "ok"
    except Exception as e:
        current_app.logger.error(f"[HEALTH] DB bağlantı hatası: {e}")
        services["database"] = f"error: {str(e)}"

    # --- Redis / Celery (Aşama 3'te aktif olacak) ---
    # Şimdilik placeholder olarak bırakıyoruz
    services["redis"]  = "not_configured_yet"
    services["celery"] = "not_configured_yet"

    # Herhangi bir kritik servis down mu?
    overall_status = "healthy" if services["database"] == "ok" else "degraded"
    http_code = 200 if overall_status == "healthy" else 503

    return jsonify({
        "success": overall_status == "healthy",
        "data": {
            "status":    overall_status,
            "app":       "Bilge Yolcu Kontrol Paneli",
            "version":   "1.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "services":  services,
        },
    }), http_code


@main_bp.route("/health/auth", methods=["GET"])
@require_auth
def health_check_auth():
    """
    Kimlik doğrulama gerektiren sağlık kontrolü.
    Vue.js, sayfa yüklendiğinde hem bağlantıyı hem token geçerliliğini
    tek istekte doğrulamak için bu endpoint'i kullanabilir.
    """
    from flask import g
    return jsonify({
        "success": True,
        "data": {
            "status":    "authenticated",
            "user":      g.current_user.username,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }), 200

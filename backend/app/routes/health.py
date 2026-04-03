"""
app/routes/health.py — Sistem sağlık kontrolü endpointleri.
"""

from datetime import datetime, timezone

from flask import jsonify, current_app

from app.routes import main_bp
from app.auth.decorators import require_auth
from app.extensions import db


@main_bp.route("/health", methods=["GET"])
def health_check():
    services = {}

    # --- Veritabanı ---
    try:
        db.session.execute(db.text("SELECT 1"))
        services["database"] = "ok"
    except Exception as e:
        current_app.logger.error(f"[HEALTH] DB hatası: {e}")
        services["database"] = f"error: {str(e)}"

    # --- Redis ---
    try:
        import redis
        r = redis.from_url(current_app.config.get("CELERY_BROKER_URL", ""))
        r.ping()
        services["redis"] = "ok"
    except Exception:
        services["redis"] = "unavailable"

    # --- Celery ---
    if current_app.config.get("CELERY_TASK_ALWAYS_EAGER"):
        services["celery"] = "eager_mode"
    else:
        services["celery"] = "ok"

    overall_status = "healthy" if services["database"] == "ok" else "degraded"
    http_code = 200 if overall_status == "healthy" else 503

    return jsonify({
        "success": overall_status == "healthy",
        "data": {
            "status":    overall_status,
            "app":       "Bilge Yolcu Kontrol Paneli",
            "version":   "1.0.5",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "services":  services,
        },
    }), http_code


@main_bp.route("/health/auth", methods=["GET"])
@require_auth
def health_check_auth():
    from flask import g
    return jsonify({
        "success": True,
        "data": {
            "status":    "authenticated",
            "user":      g.current_user.username,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }), 200

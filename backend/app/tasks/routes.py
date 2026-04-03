"""
app/tasks/routes.py — Görev Yönetimi API Endpointleri.

Endpoint'ler:
  POST /api/tasks/youtube              — YouTube görevi kuyruğa al
  POST /api/tasks/article              — Makale yazma görevi kuyruğa al
  GET  /api/tasks                      — Son görevleri listele
  GET  /api/tasks/<task_id>            — Görev detayı ve durumu
  DELETE /api/tasks/<task_id>          — Bekleyen görevi iptal et
  GET  /api/tasks/status/live          — SSE: Canlı görev durumu (Faz 4'te aktif)
"""

import logging
from flask import request, jsonify, g, current_app

from app.tasks import tasks_bp
from app.auth.decorators import require_auth
from app.tasks.helpers import (
    create_task_log,
    get_task_log,
    list_recent_tasks,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# POST /api/tasks/youtube
# ──────────────────────────────────────────────────────────────

@tasks_bp.route("/youtube", methods=["POST"])
@require_auth
def queue_youtube_task():
    """
    YouTube URL'sini makaleye dönüştürme görevini kuyruğa alır.

    İstek Gövdesi:
        {
            "url":         "https://youtube.com/watch?v=...",  // zorunlu
            "extra_notes": "Özellikle ...'ya odaklan",         // opsiyonel
            "max_tokens":  2500                                 // opsiyonel
        }

    Yanıt (202 Accepted):
        {
            "success": true,
            "data": {
                "task_id": "celery-uuid",
                "status":  "QUEUED",
                "message": "Görev kuyruğa alındı."
            }
        }
    """
    try:
        body = request.get_json(silent=True)
        if not body:
            return jsonify({
                "success": False, "error": "invalid_json",
                "message": "Geçerli JSON gövdesi gerekli.",
            }), 400

        url = body.get("url", "").strip()
        if not url:
            return jsonify({
                "success": False, "error": "missing_url",
                "message": "YouTube URL'si zorunludur.",
            }), 400

        # Görevi kuyruğa al
        from app.tasks.youtube import youtube_to_article_task
        async_result = youtube_to_article_task.delay({
            "url":         url,
            "extra_notes": body.get("extra_notes", ""),
            "max_tokens":  body.get("max_tokens", 2500),
        })
        task_id = async_result.id

        # TaskLog kaydı oluştur
        create_task_log(task_id, "youtube_summary", payload=body)

        logger.info(
            f"[TASKS API] YouTube görevi kuyruğa alındı: "
            f"task_id={task_id[:8]} url={url[:50]}"
        )
        return jsonify({
            "success": True,
            "data": {
                "task_id": task_id,
                "status":  "QUEUED",
                "message": "YouTube görevi kuyruğa alındı.",
            },
        }), 202

    except Exception as e:
        logger.error(f"[TASKS API] YouTube görevi kuyruğa alma hatası: {e}", exc_info=True)
        return jsonify({
            "success": False, "error": "queue_error",
            "message": f"Görev kuyruğa alınamadı: {str(e)}",
        }), 500


# ──────────────────────────────────────────────────────────────
# POST /api/tasks/article
# ──────────────────────────────────────────────────────────────

@tasks_bp.route("/article", methods=["POST"])
@require_auth
def queue_article_task():
    """
    Otonom makale yazma görevini kuyruğa alır.

    İstek Gövdesi:
        {
            "topic":       "Stoicism ve modern kaygı yönetimi",  // zorunlu
            "tone":        "felsefi",                            // opsiyonel
            "length":      "orta",                               // opsiyonel
            "category":    "Felsefe",                            // opsiyonel
            "keywords":    "stoacılık, kaygı",                   // opsiyonel
            "extra_notes": "...",                                // opsiyonel
            "temperature": 0.75                                  // opsiyonel
        }

    Yanıt (202 Accepted):
        {
            "success": true,
            "data": { "task_id": "...", "status": "QUEUED" }
        }
    """
    try:
        body = request.get_json(silent=True)
        if not body:
            return jsonify({
                "success": False, "error": "invalid_json",
                "message": "Geçerli JSON gövdesi gerekli.",
            }), 400

        topic = body.get("topic", "").strip()
        if not topic:
            return jsonify({
                "success": False, "error": "missing_topic",
                "message": "Makale konusu (topic) zorunludur.",
            }), 400

        from app.tasks.ai_writer import ai_article_task
        async_result = ai_article_task.delay({
            "topic":       topic,
            "tone":        body.get("tone", "felsefi"),
            "length":      body.get("length", "orta"),
            "category":    body.get("category", ""),
            "keywords":    body.get("keywords", ""),
            "extra_notes": body.get("extra_notes", ""),
            "temperature": float(body.get("temperature", 0.75)),
        })
        task_id = async_result.id
        create_task_log(task_id, "ai_article", payload=body)

        logger.info(
            f"[TASKS API] Makale görevi kuyruğa alındı: "
            f"task_id={task_id[:8]} topic='{topic[:50]}'"
        )
        return jsonify({
            "success": True,
            "data": {
                "task_id": task_id,
                "status":  "QUEUED",
                "message": "Makale yazma görevi kuyruğa alındı.",
            },
        }), 202

    except Exception as e:
        logger.error(f"[TASKS API] Makale görevi kuyruğa alma hatası: {e}", exc_info=True)
        return jsonify({
            "success": False, "error": "queue_error",
            "message": f"Görev kuyruğa alınamadı: {str(e)}",
        }), 500


# ──────────────────────────────────────────────────────────────
# GET /api/tasks
# ──────────────────────────────────────────────────────────────

@tasks_bp.route("", methods=["GET"])
@require_auth
def list_tasks():
    """
    Son görevleri listeler.
    Sorgu parametreleri:
      ?limit=20       (varsayılan)
      ?type=youtube_summary | ai_article | tümü
    """
    try:
        limit     = int(request.args.get("limit", 20))
        limit     = max(1, min(limit, 100))
        task_type = request.args.get("type")

        tasks = list_recent_tasks(limit=limit, task_type=task_type)
        return jsonify({"success": True, "data": tasks, "count": len(tasks)}), 200

    except Exception as e:
        logger.error(f"[TASKS API] Görev listesi hatası: {e}", exc_info=True)
        return jsonify({"success": False, "error": "list_error"}), 500


# ──────────────────────────────────────────────────────────────
# GET /api/tasks/<task_id>
# ──────────────────────────────────────────────────────────────

@tasks_bp.route("/<task_id>", methods=["GET"])
@require_auth
def get_task(task_id: str):
    """
    Belirli bir görevin durumunu ve sonucunu döndürür.
    Vue.js, görev kuyruğa alındıktan sonra bu endpoint'i polling yapar.
    """
    try:
        task = get_task_log(task_id)
        if task is None:
            return jsonify({
                "success": False,
                "error":   "task_not_found",
                "message": f"task_id={task_id[:16]} bulunamadı.",
            }), 404

        return jsonify({"success": True, "data": task}), 200

    except Exception as e:
        logger.error(f"[TASKS API] Görev detay hatası: {e}", exc_info=True)
        return jsonify({"success": False, "error": "get_error"}), 500


# ──────────────────────────────────────────────────────────────
# DELETE /api/tasks/<task_id>
# ──────────────────────────────────────────────────────────────

@tasks_bp.route("/<task_id>", methods=["DELETE"])
@require_auth
def revoke_task(task_id: str):
    """
    QUEUED veya RUNNING durumundaki bir görevi iptal eder.
    Celery'nin revoke() ile görevi durdurur.
    """
    try:
        from celery.result import AsyncResult
        result = AsyncResult(task_id)

        # Celery düzeyinde iptal et (SIGTERM ile)
        result.revoke(terminate=True, signal="SIGTERM")

        from app.tasks.helpers import update_task_status
        update_task_status(task_id, "REVOKED", error_msg="Admin tarafından iptal edildi.")

        logger.info(f"[TASKS API] Görev iptal edildi: {task_id[:8]}")
        return jsonify({
            "success": True,
            "data": {"task_id": task_id, "status": "REVOKED"},
        }), 200

    except Exception as e:
        logger.error(f"[TASKS API] Görev iptal hatası: {e}", exc_info=True)
        return jsonify({
            "success": False, "error": "revoke_error",
            "message": f"Görev iptal edilemedi: {str(e)}",
        }), 500

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
        payload = {
            "url":         url,
            "extra_notes": body.get("extra_notes", ""),
            "max_tokens":  body.get("max_tokens", 2500),
        }
        # Manuel transkript varsa ekle (YouTube API bypass)
        manual_transcript = body.get("manual_transcript", "").strip()
        if manual_transcript:
            payload["manual_transcript"] = manual_transcript

        async_result = youtube_to_article_task.delay(payload)
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
def delete_or_revoke_task(task_id: str):
    """
    Görevi iptal eder veya siler.
      - QUEUED/RUNNING → Celery revoke + DB'de REVOKED olarak işaretle
      - SUCCESS/FAILED/REVOKED → DB'den tamamen sil
    """
    try:
        from app.models import TaskLog
        from app.extensions import db

        task = TaskLog.query.get(task_id)
        if not task:
            return jsonify({
                "success": False, "error": "not_found",
                "message": f"Görev bulunamadı: {task_id[:16]}",
            }), 404

        if task.status in ("QUEUED", "RUNNING"):
            # Celery'den iptal et
            from celery.result import AsyncResult
            AsyncResult(task_id).revoke(terminate=True, signal="SIGTERM")
            task.status = "REVOKED"
            task.error_msg = "Admin tarafından iptal edildi."
            db.session.commit()
            logger.info(f"[TASKS API] Görev iptal edildi: {task_id[:8]}")
            return jsonify({
                "success": True,
                "data": {"task_id": task_id, "status": "REVOKED", "action": "revoked"},
            }), 200
        else:
            # Tamamlanmış görevleri DB'den sil
            db.session.delete(task)
            db.session.commit()
            logger.info(f"[TASKS API] Görev silindi: {task_id[:8]}")
            return jsonify({
                "success": True,
                "data": {"task_id": task_id, "action": "deleted"},
            }), 200

    except Exception as e:
        logger.error(f"[TASKS API] Görev silme/iptal hatası: {e}", exc_info=True)
        return jsonify({
            "success": False, "error": "delete_error",
            "message": f"İşlem başarısız: {str(e)}",
        }), 500


# ──────────────────────────────────────────────────────────────
# POST /api/tasks/<task_id>/retry
# ──────────────────────────────────────────────────────────────

@tasks_bp.route("/<task_id>/retry", methods=["POST"])
@require_auth
def retry_task(task_id: str):
    """
    Başarısız bir görevi aynı parametrelerle tekrar kuyruğa alır.
    Orijinal görevi REVOKED yapıp yeni bir görev oluşturur.
    """
    try:
        import json as _json
        from app.models import TaskLog

        task = TaskLog.query.get(task_id)
        if not task:
            return jsonify({
                "success": False, "error": "not_found",
                "message": "Görev bulunamadı.",
            }), 404

        if task.status not in ("FAILED", "REVOKED"):
            return jsonify({
                "success": False, "error": "invalid_status",
                "message": f"Sadece FAILED/REVOKED görevler tekrar denenebilir. Mevcut: {task.status}",
            }), 400

        # Orijinal payload'u çıkar
        try:
            original_payload = _json.loads(task.payload) if task.payload else {}
        except (ValueError, TypeError):
            original_payload = {}

        # Görev türüne göre yeniden kuyruğa al
        if task.task_type == "youtube_summary":
            from app.tasks.youtube import youtube_to_article_task
            async_result = youtube_to_article_task.delay(original_payload)
        elif task.task_type == "ai_article":
            from app.tasks.ai_writer import ai_article_task
            async_result = ai_article_task.delay(original_payload)
        else:
            return jsonify({
                "success": False, "error": "unknown_type",
                "message": f"Bilinmeyen görev türü: {task.task_type}",
            }), 400

        new_task_id = async_result.id
        create_task_log(new_task_id, task.task_type, payload=original_payload)

        logger.info(
            f"[TASKS API] Görev tekrar kuyruğa alındı: "
            f"eski={task_id[:8]} yeni={new_task_id[:8]}"
        )
        return jsonify({
            "success": True,
            "data": {
                "old_task_id": task_id,
                "new_task_id": new_task_id,
                "status": "QUEUED",
                "message": "Görev tekrar kuyruğa alındı.",
            },
        }), 202

    except Exception as e:
        logger.error(f"[TASKS API] Tekrar deneme hatası: {e}", exc_info=True)
        return jsonify({
            "success": False, "error": "retry_error",
            "message": f"Tekrar deneme başarısız: {str(e)}",
        }), 500


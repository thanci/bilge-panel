"""
app/routes/publish.py — Yayın Kuyruğu API Endpointleri.

Endpoint'ler:
  POST   /api/publish              — Görevden taslak oluştur
  GET    /api/publish              — Taslak listesi
  GET    /api/publish/<id>         — Taslak detayı
  PUT    /api/publish/<id>         — Taslak güncelle
  POST   /api/publish/<id>/send    — XenForo'ya yayınla
  DELETE /api/publish/<id>         — Taslak sil
"""

import json
import logging
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify
from app.auth.decorators import require_auth
from app.extensions import db
from app.models import PublishDraft, TaskLog

logger = logging.getLogger(__name__)
publish_bp = Blueprint("publish", __name__)


# ──────────────────────────────────────────────────────────────
# POST /api/publish — Görevden taslak oluştur
# ──────────────────────────────────────────────────────────────

@publish_bp.route("", methods=["POST"])
@require_auth
def create_draft():
    """
    Tamamlanmış bir görevden yayın taslağı oluşturur.
    Body: { "task_id": "..." } veya { "title": "...", "content": "..." }
    """
    try:
        body = request.get_json(silent=True) or {}
        task_id = body.get("task_id")

        if task_id:
            # Görevden oluştur
            task = TaskLog.query.get(task_id)
            if not task:
                return jsonify({"success": False, "error": "not_found", "message": "Görev bulunamadı."}), 404
            if task.status != "SUCCESS":
                return jsonify({"success": False, "error": "invalid_status", "message": "Sadece başarılı görevler yayına gönderilebilir."}), 400

            # Result'tan içerik çıkar
            try:
                result = json.loads(task.result) if task.result else {}
            except (ValueError, TypeError):
                result = {}

            content = result.get("content", "")
            if not content:
                return jsonify({"success": False, "error": "no_content", "message": "Görevde içerik bulunamadı."}), 400

            # Payload'dan ek bilgiler
            try:
                payload = json.loads(task.payload) if task.payload else {}
            except (ValueError, TypeError):
                payload = {}

            title = result.get("topic") or payload.get("topic") or payload.get("url", "Başlıksız")
            meta = result.get("meta") or {}
            tags = meta.get("keywords", [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]

            draft = PublishDraft(
                task_id     = task_id,
                title       = title[:255],
                content     = content,
                source_type = task.task_type,
                category    = payload.get("category", ""),
                tags        = json.dumps(tags, ensure_ascii=False),
                xf_node_id  = payload.get("xf_node_id"),
                status      = "DRAFT",
            )
        else:
            # Bağımsız taslak
            title = body.get("title", "Başlıksız").strip() or "Başlıksız"
            content = body.get("content", "").strip()

            tags = body.get("tags", [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]

            draft = PublishDraft(
                title       = title[:255],
                content     = content,
                source_type = "manual",
                category    = body.get("category", ""),
                tags        = json.dumps(tags, ensure_ascii=False),
                xf_node_id  = body.get("xf_node_id"),
                tone        = body.get("tone", "felsefi"),
                status      = "DRAFT",
            )

        db.session.add(draft)
        db.session.commit()

        logger.info(f"[PUBLISH] Taslak oluşturuldu: #{draft.id} '{draft.title[:40]}'")
        return jsonify({"success": True, "data": draft.to_dict()}), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f"[PUBLISH] Taslak oluşturma hatası: {e}", exc_info=True)
        return jsonify({"success": False, "error": "create_error", "message": str(e)}), 500


# ──────────────────────────────────────────────────────────────
# GET /api/publish — Taslak listesi
# ──────────────────────────────────────────────────────────────

@publish_bp.route("", methods=["GET"])
@require_auth
def list_drafts():
    """Tüm taslakları listeler. ?status=DRAFT|PUBLISHED filtresi."""
    try:
        status = request.args.get("status")
        query = PublishDraft.query

        if status:
            query = query.filter_by(status=status.upper())

        drafts = query.order_by(PublishDraft.updated_at.desc()).limit(100).all()
        return jsonify({
            "success": True,
            "data": [d.to_dict() for d in drafts],
            "count": len(drafts),
        }), 200

    except Exception as e:
        logger.error(f"[PUBLISH] Liste hatası: {e}", exc_info=True)
        return jsonify({"success": False, "error": "list_error"}), 500


# ──────────────────────────────────────────────────────────────
# GET /api/publish/<id> — Taslak detayı
# ──────────────────────────────────────────────────────────────

@publish_bp.route("/<int:draft_id>", methods=["GET"])
@require_auth
def get_draft(draft_id: int):
    try:
        draft = PublishDraft.query.get(draft_id)
        if not draft:
            return jsonify({"success": False, "error": "not_found"}), 404
        return jsonify({"success": True, "data": draft.to_dict()}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ──────────────────────────────────────────────────────────────
# PUT /api/publish/<id> — Taslak güncelle
# ──────────────────────────────────────────────────────────────

@publish_bp.route("/<int:draft_id>", methods=["PUT"])
@require_auth
def update_draft(draft_id: int):
    """Taslağın başlık, içerik, kategori, etiketlerini günceller."""
    try:
        draft = PublishDraft.query.get(draft_id)
        if not draft:
            return jsonify({"success": False, "error": "not_found"}), 404

        if draft.status == "PUBLISHED":
            return jsonify({"success": False, "error": "already_published", "message": "Yayınlanmış taslak düzenlenemez."}), 400

        body = request.get_json(silent=True) or {}

        if "title" in body:
            draft.title = body["title"][:255]
        if "content" in body:
            draft.content = body["content"]
        if "category" in body:
            draft.category = body["category"]
        if "xf_node_id" in body:
            draft.xf_node_id = body["xf_node_id"]
        if "tags" in body:
            tags = body["tags"]
            if isinstance(tags, list):
                draft.tags = json.dumps(tags, ensure_ascii=False)
            elif isinstance(tags, str):
                draft.tags = json.dumps([t.strip() for t in tags.split(",") if t.strip()], ensure_ascii=False)
        if "tone" in body:
            draft.tone = body["tone"]

        db.session.commit()
        logger.info(f"[PUBLISH] Taslak güncellendi: #{draft_id}")
        return jsonify({"success": True, "data": draft.to_dict()}), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"[PUBLISH] Güncelleme hatası: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ──────────────────────────────────────────────────────────────
# POST /api/publish/<id>/send — XenForo'ya yayınla
# ──────────────────────────────────────────────────────────────

@publish_bp.route("/<int:draft_id>/send", methods=["POST"])
@require_auth
def publish_draft(draft_id: int):
    """Taslağı XenForo'ya yayınlar."""
    try:
        draft = PublishDraft.query.get(draft_id)
        if not draft:
            return jsonify({"success": False, "error": "not_found"}), 404

        if draft.status == "PUBLISHED":
            return jsonify({"success": False, "error": "already_published", "message": "Bu taslak zaten yayınlanmış."}), 400

        if not draft.xf_node_id:
            return jsonify({"success": False, "error": "no_node", "message": "Hedef forum seçilmedi."}), 400

        # XenForo'ya gönder
        from app.xenforo.client import XenForoClient
        from app.xenforo.exceptions import XenForoError

        # Etiketleri çöz
        try:
            tags = json.loads(draft.tags) if draft.tags else []
        except (ValueError, TypeError):
            tags = []

        with XenForoClient.from_config() as xf:
            resp = xf.threads.create(
                node_id = draft.xf_node_id,
                title   = draft.title,
                message = draft.content,
                tags    = tags,
            )

        thread = resp.get("thread", resp)
        draft.status        = "PUBLISHED"
        draft.xf_thread_id  = thread.get("thread_id")
        draft.xf_thread_url = thread.get("view_url", "")
        draft.published_at  = datetime.now(timezone.utc)
        db.session.commit()

        logger.info(f"[PUBLISH] ✅ Yayınlandı: #{draft_id} → thread_id={draft.xf_thread_id}")
        return jsonify({"success": True, "data": draft.to_dict()}), 200

    except XenForoError as e:
        logger.error(f"[PUBLISH] XenForo hatası: {e}", exc_info=True)
        return jsonify({"success": False, "error": "xenforo_error", "message": str(e)}), 502
    except Exception as e:
        db.session.rollback()
        logger.error(f"[PUBLISH] Yayın hatası: {e}", exc_info=True)
        return jsonify({"success": False, "error": "publish_error", "message": str(e)}), 500


# ──────────────────────────────────────────────────────────────
# DELETE /api/publish/<id> — Taslak sil
# ──────────────────────────────────────────────────────────────

@publish_bp.route("/<int:draft_id>", methods=["DELETE"])
@require_auth
def delete_draft(draft_id: int):
    try:
        draft = PublishDraft.query.get(draft_id)
        if not draft:
            return jsonify({"success": False, "error": "not_found"}), 404

        db.session.delete(draft)
        db.session.commit()
        logger.info(f"[PUBLISH] Taslak silindi: #{draft_id}")
        return jsonify({"success": True, "data": {"id": draft_id, "action": "deleted"}}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


# ────────────────────────────────────────────────────────────────
# POST /api/publish/ai-enhance — AI ile metni genişlet/düzelt
# ────────────────────────────────────────────────────────────────

_AI_ENHANCE_PROMPTS = {
    "expand": """Aşağıdaki paragrafı daha detaylı, derinlikli ve zengin bir şekilde genişlet.
Her cümleyi açıkla, örnekler ekle, bağlamı genişlet. Türkçe, doğal ve akıcı yaz.
Sadece genişletilmiş metni döndür, başka açıklama ekleme.

METİN:
{text}""",

    "rewrite": """Aşağıdaki metni aynı anlamı koruyarak farklı cümlelerle yeniden yaz.
Daha akıcı, daha güçlü ifadeler kullan. Türkçe, doğal yaz.
Sadece yeniden yazılmış metni döndür.

METİN:
{text}""",

    "longer": """Aşağıdaki makaleyi önemli ölçüde genişlet. Her bölüme ek paragraflar,
örnekler, detaylar ve derinlik ekle. Mevcut yapıyı koru ama kelime sayısını
en az 2 katına çıkar. Türkçe, BB-Code formatında yaz.
Sadece genişletilmiş makaleyi döndür.

MAKALE:
{text}""",

    "summarize": """Aşağıdaki metni özetle. Ana fikirleri koru, gereksiz detayları çıkar.
Kısa, net ve etkileyici bir şekilde yeniden yaz. Türkçe.
Sadece özetlenmiş metni döndür.

METİN:
{text}""",

    "continue": """Aşağıdaki metnin devamını yaz. Aynı ton, üslup ve konuyu koru.
En az 3 yeni paragraf ekle. Doğal bir geçişle devam et.
BB-Code formatında, Türkçe yaz. Sadece devam metnini döndür.

METİN:
{text}""",

    "translate": """Aşağıdaki İngilizce metni Türkçeye çevir. Doğal, akıcı Türkçe kullan.
Tercüme havasından kaçın. Sadece çevrilmiş metni döndür.

METİN:
{text}""",
}

@publish_bp.route("/ai-enhance", methods=["POST"])
@require_auth
def ai_enhance():
    """Editordeki metni AI ile genişlet/düzelt/devam ettir."""
    try:
        body = request.get_json(silent=True) or {}
        action = body.get("action", "")
        selected_text = body.get("selected_text", "")
        full_text = body.get("full_text", "")
        tone = body.get("tone", "felsefi")

        if action not in _AI_ENHANCE_PROMPTS:
            return jsonify({"success": False, "error": "invalid_action",
                            "message": f"Geçersiz aksiyon: {action}"}), 400

        # Seçili metin varsa onu kullan, yoksa tam metni
        text = selected_text if selected_text else full_text
        if not text.strip():
            return jsonify({"success": False, "error": "no_text",
                            "message": "Metin bulunamadı."}), 400

        prompt_template = _AI_ENHANCE_PROMPTS[action]
        prompt = prompt_template.format(text=text)

        # Ton eklentisi
        tone_hint = f"\n\nYAZIM TONU: {tone} — bu ton ile uyumlu yaz."
        prompt += tone_hint

        from flask import current_app
        from app.llm.client import complete_with_fallback
        from app.llm.prompts import _BASE_IDENTITY

        system_prompt = f"""{_BASE_IDENTITY}

Sen metin düzenleme ve genişletme uzmanısın.
Verilen talimatı uygula, sadece sonuç metnini döndür.
Başka açıklama, not veya yorum ekleme."""

        llm_response = complete_with_fallback(
            prompt      = prompt,
            system      = system_prompt,
            max_tokens  = 4000,
            temperature = 0.7,
            task_id     = f"ai_enhance_{action}",
        )

        result_text = llm_response.text.strip()

        # "continue" için mevcut metne ekle
        if action == "continue":
            result_text = full_text.rstrip() + "\n\n" + result_text
        elif action == "longer":
            result_text = result_text  # Tam değiştirme

        logger.info(f"[PUBLISH] AI-enhance: {action}, {len(result_text)} karakter")

        return jsonify({
            "success": True,
            "data": {
                "content": result_text,
                "action": action,
                "model": llm_response.model,
            },
        }), 200

    except Exception as e:
        logger.error(f"[PUBLISH] AI-enhance hatası: {e}", exc_info=True)
        return jsonify({"success": False, "error": "ai_error", "message": str(e)}), 500

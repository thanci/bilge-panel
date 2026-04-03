"""
app/xenforo/routes.py — XenForo Yönetim API Endpointleri.

Endpoint'ler:
  GET  /api/xenforo/health          — API bağlantısını test et
  GET  /api/xenforo/nodes           — Forum ağaç yapısını getir
  POST /api/xenforo/nodes/forum     — Yeni forum oluştur
  POST /api/xenforo/nodes/category  — Yeni kategori oluştur
  POST /api/xenforo/nodes/hierarchy — Toplu hiyerarşi oluştur
  GET  /api/xenforo/threads/:id     — Konu detayı
  POST /api/xenforo/threads         — Manuel konu oluştur
  GET  /api/xenforo/threads/forum/:node_id — Forum konu listesi
"""

import logging
from flask import request, jsonify, current_app

from app.xenforo import xf_bp
from app.auth.decorators import require_auth
from app.xenforo.client import XenForoClient
from app.xenforo.exceptions import XenForoError, XenForoAuthError
from app.xenforo.threads import ThreadManager

logger = logging.getLogger(__name__)


def _get_client() -> XenForoClient:
    """Route handler'larında client oluşturmak için yardımcı."""
    return XenForoClient.from_config()

def _xf_error_response(e: XenForoError):
    """XenForo hatasını standart JSON yanıtına çevirir."""
    code = 403 if isinstance(e, XenForoAuthError) else (e.status_code or 500)
    return jsonify({
        "success": False,
        **e.to_dict(),
    }), min(code, 503)   # 5xx'leri 503 ile kapat


# ── GET /api/xenforo/health ────────────────────────────────

@xf_bp.route("/health", methods=["GET"])
@require_auth
def xf_health():
    """XenForo API bağlantısını ve API key doğruluğunu test eder."""
    try:
        with _get_client() as xf:
            # En hafif istek: node listesinin ilk elemanı
            resp = xf.get("nodes", params={"page": 1})
            node_count = len(resp.get("nodes", []))
        return jsonify({
            "success": True,
            "data": {
                "status":      "ok",
                "base_url":    current_app.config.get("XENFORO_BASE_URL", ""),
                "node_count":  node_count,
            },
        }), 200
    except XenForoError as e:
        return _xf_error_response(e)
    except ValueError as e:
        return jsonify({"success": False, "error": "config_missing", "message": str(e)}), 500


# ── GET /api/xenforo/nodes ─────────────────────────────────

@xf_bp.route("/nodes", methods=["GET"])
@require_auth
def list_nodes():
    """
    Forum hiyerarşisini ağaç yapısında döndürür.
    Sorgu parametresi: ?flat=1 (düz liste için)
    """
    try:
        flat = request.args.get("flat", "0") == "1"
        with _get_client() as xf:
            nodes = xf.nodes.list_all()
            data  = nodes if flat else xf.nodes.build_tree(nodes)
        return jsonify({"success": True, "data": data}), 200
    except XenForoError as e:
        return _xf_error_response(e)
    except ValueError as e:
        return jsonify({"success": False, "error": "config_missing", "message": str(e)}), 500


# ── POST /api/xenforo/nodes/forum ──────────────────────────

@xf_bp.route("/nodes/forum", methods=["POST"])
@require_auth
def create_forum():
    """
    Yeni forum (konu açılabilir bölüm) oluşturur.

    İstek:
        {
            "name":           "Yapay Zeka",         // zorunlu
            "parent_node_id": 5,                     // zorunlu (kategori ID'si)
            "description":    "AI konuları...",      // opsiyonel
            "display_order":  10                     // opsiyonel
        }
    """
    body = request.get_json(silent=True) or {}
    name           = body.get("name", "").strip()
    parent_node_id = body.get("parent_node_id")

    if not name or parent_node_id is None:
        return jsonify({
            "success": False,
            "error":   "missing_fields",
            "message": "name ve parent_node_id zorunludur.",
        }), 400

    try:
        with _get_client() as xf:
            node = xf.nodes.create_forum(
                name           = name,
                parent_node_id = int(parent_node_id),
                description    = body.get("description", ""),
                display_order  = int(body.get("display_order", 10)),
            )
        return jsonify({"success": True, "data": node}), 201
    except XenForoError as e:
        return _xf_error_response(e)
    except ValueError as e:
        return jsonify({"success": False, "error": "config_missing", "message": str(e)}), 500


# ── POST /api/xenforo/nodes/category ───────────────────────

@xf_bp.route("/nodes/category", methods=["POST"])
@require_auth
def create_category():
    """
    Yeni kategori (kapsayıcı bölüm) oluşturur.

    İstek:
        {
            "name":           "Felsefe ve Düşünce",
            "parent_node_id": 0,                  // 0 = kök seviyesi
            "description":    "...",
            "display_order":  10
        }
    """
    body = request.get_json(silent=True) or {}
    name = body.get("name", "").strip()

    if not name:
        return jsonify({"success": False, "error": "missing_name"}), 400

    try:
        with _get_client() as xf:
            node = xf.nodes.create_category(
                name           = name,
                parent_node_id = int(body.get("parent_node_id", 0)),
                description    = body.get("description", ""),
                display_order  = int(body.get("display_order", 10)),
            )
        return jsonify({"success": True, "data": node}), 201
    except XenForoError as e:
        return _xf_error_response(e)
    except ValueError as e:
        return jsonify({"success": False, "error": "config_missing", "message": str(e)}), 500


# ── POST /api/xenforo/nodes/hierarchy ──────────────────────

@xf_bp.route("/nodes/hierarchy", methods=["POST"])
@require_auth
def create_hierarchy():
    """
    Ebeveyn-çocuk ilişkisiyle bir forum hiyerarşisini toplu oluşturur.

    İstek gövdesi: spec dizisi (nodes.py / create_hierarchy() formatında)

    Örnek:
        {
            "nodes": [
                {
                    "name": "Felsefe", "type": "Category", "parent_id": 0,
                    "children": [
                        {"name": "Antik Felsefe", "type": "Forum", "order": 10}
                    ]
                }
            ]
        }
    """
    body = request.get_json(silent=True) or {}
    spec = body.get("nodes", [])

    if not spec:
        return jsonify({
            "success": False,
            "error":   "missing_nodes",
            "message": "nodes dizisi zorunludur.",
        }), 400

    try:
        with _get_client() as xf:
            created = xf.nodes.create_hierarchy(spec)
        return jsonify({
            "success": True,
            "data":    {"created": created, "count": len(created)},
        }), 201
    except XenForoError as e:
        return _xf_error_response(e)
    except ValueError as e:
        return jsonify({"success": False, "error": "config_missing", "message": str(e)}), 500


# ── GET /api/xenforo/threads/forum/<node_id> ───────────────

@xf_bp.route("/threads/forum/<int:node_id>", methods=["GET"])
@require_auth
def threads_by_forum(node_id: int):
    """Belirli bir forumun konularını listeler."""
    page = int(request.args.get("page", 1))
    try:
        with _get_client() as xf:
            data = xf.threads.list_by_forum(node_id=node_id, page=page)
        return jsonify({"success": True, "data": data}), 200
    except XenForoError as e:
        return _xf_error_response(e)


# ── GET /api/xenforo/threads/<thread_id> ───────────────────

@xf_bp.route("/threads/<int:thread_id>", methods=["GET"])
@require_auth
def get_thread(thread_id: int):
    """Konu detayını döndürür."""
    try:
        with _get_client() as xf:
            data = xf.threads.get(thread_id)
        return jsonify({"success": True, "data": data}), 200
    except XenForoError as e:
        return _xf_error_response(e)


# ── POST /api/xenforo/threads ──────────────────────────────

@xf_bp.route("/threads", methods=["POST"])
@require_auth
def create_thread_manual():
    """
    Dashboard'dan manuel konu oluşturur (AI görevi olmadan).

    İstek:
        {
            "node_id":  5,                // zorunlu
            "title":    "Konu Başlığı",   // opsiyonel (auto-extract de var)
            "message":  "[B]...[/B]",     // zorunlu
            "tags":     ["tag1", "tag2"], // opsiyonel
            "prefix_id": 1               // opsiyonel
        }
    """
    body    = request.get_json(silent=True) or {}
    node_id = body.get("node_id")
    message = body.get("message", "").strip()

    if not node_id or not message:
        return jsonify({
            "success": False, "error": "missing_fields",
            "message": "node_id ve message zorunludur.",
        }), 400

    # Başlık verilmediyse message'dan çıkar
    title = body.get("title", "").strip() or \
            ThreadManager.extract_title_from_content(message, "Yeni Makale")

    try:
        with _get_client() as xf:
            resp = xf.threads.create(
                node_id   = int(node_id),
                title     = title,
                message   = message,
                tags      = body.get("tags", []),
                prefix_id = body.get("prefix_id"),
            )
        thread_data = resp.get("thread", resp)
        return jsonify({
            "success": True,
            "data": {
                "thread_id": thread_data.get("thread_id"),
                "view_url":  thread_data.get("view_url", ""),
                "title":     thread_data.get("title", title),
            },
        }), 201

    except XenForoError as e:
        logger.error(f"[XF-ROUTES] Konu oluşturma hatası: {e}", exc_info=True)
        return _xf_error_response(e)
    except ValueError as e:
        return jsonify({"success": False, "error": "config_missing", "message": str(e)}), 500

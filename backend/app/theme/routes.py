"""
app/theme/routes.py — Tema Editörü API Endpointleri.

Endpoints:
  GET  /api/theme/files              — styles/ dizin listesi
  GET  /api/theme/file               — Dosya içeriğini oku (?path=...)
  POST /api/theme/file               — Dosya içeriğini kaydet
  POST /api/theme/cache              — XF önbelleğini temizle
"""

import logging

from flask import request, jsonify

from app.theme import theme_bp
from app.auth.decorators import require_auth
from app.ssh.client import SSHClient
from app.ssh.exceptions import SSHError, PathTraversalError
from app.theme.editor import (
    list_style_files,
    read_style_file,
    write_style_file,
    clear_theme_cache,
)

logger = logging.getLogger(__name__)


def _ssh_err(e):
    code = 403 if isinstance(e, PathTraversalError) else 500
    return jsonify({"success": False, "error": type(e).__name__, "message": str(e)}), code


# ── GET /api/theme/files ───────────────────────────────────

@theme_bp.route("/files", methods=["GET"])
@require_auth
def list_files():
    """
    styles/ dizinindeki tema dosyalarını listeler.
    Sorgu: ?path=1/less (alt dizin), ?recursive=1
    """
    path      = request.args.get("path", "")
    recursive = request.args.get("recursive", "1") != "0"

    try:
        with SSHClient.from_config() as ssh:
            files = list_style_files(ssh, path, recursive)
        return jsonify({"success": True, "data": files}), 200
    except (PathTraversalError, PermissionError) as e:
        return _ssh_err(e)
    except (SSHError, ValueError) as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── GET /api/theme/file ────────────────────────────────────

@theme_bp.route("/file", methods=["GET"])
@require_auth
def get_file():
    """
    Tema dosyasını okur.
    Sorgu: ?path=/absolute/path/or/relative
    """
    path = request.args.get("path", "").strip()
    if not path:
        return jsonify({"success": False, "error": "path parametresi gerekli."}), 400

    try:
        with SSHClient.from_config() as ssh:
            result = read_style_file(ssh, path)
        return jsonify({"success": True, "data": result}), 200
    except (PathTraversalError, PermissionError) as e:
        return _ssh_err(e)
    except (SSHError, ValueError) as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── POST /api/theme/file ───────────────────────────────────

@theme_bp.route("/file", methods=["POST"])
@require_auth
def save_file():
    """
    Tema dosyasını kaydeder.
    Yazma öncesi otomatik .bak yedeği alınır.

    İstek: {"path": "...", "content": "...", "backup": true}
    """
    body    = request.get_json(silent=True) or {}
    path    = body.get("path", "").strip()
    content = body.get("content", "")
    backup  = body.get("backup", True)

    if not path:
        return jsonify({"success": False, "error": "path zorunludur."}), 400
    if content is None:
        return jsonify({"success": False, "error": "content zorunludur."}), 400

    try:
        with SSHClient.from_config() as ssh:
            result = write_style_file(ssh, path, content, backup=backup)
        return jsonify({"success": True, "data": result}), 200
    except (PathTraversalError, PermissionError) as e:
        return _ssh_err(e)
    except (SSHError, ValueError) as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── POST /api/theme/cache ──────────────────────────────────

@theme_bp.route("/cache", methods=["POST"])
@require_auth
def clear_cache():
    """
    XenForo template ve addon önbelleklerini temizler.
    Tema dosyası kaydedildikten sonra çağrılır.
    """
    try:
        with SSHClient.from_config() as ssh:
            result = clear_theme_cache(ssh)
        return jsonify({"success": True, "data": result}), 200
    except (SSHError, ValueError) as e:
        return jsonify({"success": False, "error": str(e)}), 500

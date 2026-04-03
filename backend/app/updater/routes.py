"""
app/updater/routes.py — DevOps Güncelleme API Endpointleri.

Endpoints:
  GET  /api/updater/status          — Sistem durumu (PHP, XF sürümü vb.)
  POST /api/updater/upgrade/stream  — XenForo yükseltme pipeline (SSE)
  POST /api/updater/cache/clear     — XF cache temizle
"""

import json
import logging

from flask import jsonify, Response, stream_with_context, request

from app.updater import updater_bp
from app.auth.decorators import require_auth
from app.ssh.client import SSHClient
from app.ssh.exceptions import SSHError
from app.updater.xf_updater import run_upgrade_pipeline, UpgradeAbortedError, rebuild_templates, rebuild_addons

logger = logging.getLogger(__name__)


# ── GET /api/updater/status ────────────────────────────────

@updater_bp.route("/status", methods=["GET"])
@require_auth
def system_status():
    """
    Sunucu durumunu kontrol eder.
    PHP versiyonu, disk kullanımı, XF versiyonu döndürür.
    """
    from flask import current_app

    webroot = current_app.config.get("XENFORO_WEBROOT", "")
    php_bin = current_app.config.get("SSH_PHP_BIN", "php")

    status_cmds = {
        "php_version":  f"{php_bin} -r \"echo PHP_VERSION;\"",
        "disk_usage":   f"df -h {webroot} | tail -1 | awk '{{print $3\"/\"$2\" (\"$5\")'}}'",
        "xf_version":   (
            f"{php_bin} -r \""
            f"define('XFVARS', 0); "
            f"require_once('{webroot}/src/XF/App.php'); "
            f"echo \\XF::$versionString ?? 'bilinmiyor';\""
        ),
        "uptime":       "uptime -p",
        "memory":       "free -h | awk 'NR==2{{print $3\"/\"$2}}'",
    }

    results = {}
    try:
        with SSHClient.from_config() as ssh:
            for key, cmd in status_cmds.items():
                try:
                    out, _, _ = ssh.exec_command(cmd, timeout=15)
                    results[key] = out.strip()
                except SSHError as e:
                    results[key] = f"Hata: {e}"
        return jsonify({"success": True, "data": results}), 200
    except (SSHError, ValueError) as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── POST /api/updater/upgrade/stream ──────────────────────

@updater_bp.route("/upgrade/stream", methods=["POST"])
@require_auth
def upgrade_stream():
    """
    XenForo yükseltme pipeline'ını SSE stream olarak başlatır.

    Pipeline adımları (xf_updater.py):
      A. Yedekleme (mysqldump + tar) — başarısız olursa ABORT
      B. Bakım modu açma
      C. xf:upgrade
      D. Bakım modu kapama
    """
    def generate():
        try:
            for chunk in run_upgrade_pipeline():
                yield f"data: {chunk}\n\n"
        except UpgradeAbortedError as e:
            yield f"data: {json.dumps({'done': True, 'success': False, 'error': str(e)})}\n\n"
        except (SSHError, ValueError, Exception) as e:
            yield f"data: {json.dumps({'stream': 'error', 'line': str(e)})}\n\n"
            yield f"data: {json.dumps({'done': True, 'success': False})}\n\n"

    return Response(
        stream_with_context(generate()),
        content_type = "text/event-stream",
        headers      = {
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":       "keep-alive",
        },
    )


# ── POST /api/updater/cache/clear ─────────────────────────

@updater_bp.route("/cache/clear", methods=["POST"])
@require_auth
def clear_cache():
    """
    XenForo template + addon önbelleklerini temizler.
    Tema editöründen kaydetme sonrası çağrılır.
    """
    body    = request.get_json(silent=True) or {}
    targets = body.get("targets", ["templates", "addons"])  # ikisi de varsayılan

    results = {}
    try:
        with SSHClient.from_config() as ssh:
            if "templates" in targets:
                try:
                    out, _, _ = rebuild_templates(ssh)
                    results["templates"] = out.strip()[:300] or "ok"
                except SSHError as e:
                    results["templates"] = f"HATA: {e}"

            if "addons" in targets:
                try:
                    out, _, _ = rebuild_addons(ssh)
                    results["addons"] = out.strip()[:300] or "ok"
                except SSHError as e:
                    results["addons"] = f"HATA: {e}"

        return jsonify({"success": True, "data": results}), 200
    except (SSHError, ValueError) as e:
        return jsonify({"success": False, "error": str(e)}), 500

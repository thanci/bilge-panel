"""
app/ssh/routes.py — SSH Komut API Endpointleri.

Endpoints:
  GET  /api/ssh/health                — SSH bağlantısını test et
  POST /api/ssh/exec                  — Tek komut çalıştır (JSON yanıt)
  POST /api/ssh/exec/stream           — Komut çıktısını SSE stream et
"""

import json
import logging

from flask import request, jsonify, Response, stream_with_context

from app.ssh import ssh_bp
from app.auth.decorators import require_auth
from app.ssh.client import SSHClient
from app.ssh.exceptions import SSHError, PathTraversalError

logger = logging.getLogger(__name__)

# Güvenlik: bu komutlar doğrudan çalıştırılamaz (kara liste)
_BLOCKED_COMMANDS = ["rm -rf /", "mkfs", "dd if=/dev/zero", ":(){ :|:& };:"]


def _is_safe_command(cmd: str) -> bool:
    """Tehlikeli komut deseni kontrolü."""
    cmd_lower = cmd.lower()
    return not any(b in cmd_lower for b in _BLOCKED_COMMANDS)


def _ssh_error_resp(e: SSHError):
    return jsonify({"success": False, **e.to_dict()}), 500


# ── GET /api/ssh/health ────────────────────────────────────

@ssh_bp.route("/health", methods=["GET"])
@require_auth
def ssh_health():
    """SSH bağlantısını ve kimlik doğrulamayı test eder."""
    try:
        with SSHClient.from_config() as ssh:
            out, _, _ = ssh.exec_command("uname -a && uptime", timeout=15)
        return jsonify({
            "success": True,
            "data":    {"status": "connected", "info": out.strip()},
        }), 200
    except SSHError as e:
        return _ssh_error_resp(e)
    except ValueError as e:
        return jsonify({"success": False, "error": "config_missing", "message": str(e)}), 500


# ── POST /api/ssh/exec ─────────────────────────────────────

@ssh_bp.route("/exec", methods=["POST"])
@require_auth
def exec_command():
    """
    Tek komut çalıştırır (kısa süren komutlar için).

    İstek: {"command": "ls /home/user", "timeout": 30}
    Yanıt: {"success": true, "stdout": "...", "stderr": "...", "exit_code": 0}
    """
    body    = request.get_json(silent=True) or {}
    command = body.get("command", "").strip()
    timeout = int(body.get("timeout", 60))

    if not command:
        return jsonify({"success": False, "error": "Komut boş olamaz."}), 400

    if not _is_safe_command(command):
        logger.warning(f"[SSH-ROUTES] Tehlikeli komut reddedildi: {command}")
        return jsonify({"success": False, "error": "Bu komut güvenlik nedeniyle engellendi."}), 403

    try:
        with SSHClient.from_config() as ssh:
            stdout, stderr, code = ssh.exec_command(command, timeout=timeout)
        return jsonify({
            "success":   True,
            "stdout":    stdout,
            "stderr":    stderr,
            "exit_code": code,
        }), 200
    except SSHError as e:
        return _ssh_error_resp(e)
    except ValueError as e:
        return jsonify({"success": False, "error": "config_missing", "message": str(e)}), 500


# ── POST /api/ssh/exec/stream ──────────────────────────────

@ssh_bp.route("/exec/stream", methods=["POST"])
@require_auth
def stream_command():
    """
    Uzun süren komutları gerçek zamanlı SSE stream olarak çalıştırır.
    Frontend EventSource API ile bağlanır.

    İstek:  {"command": "php cmd.php xf:upgrade", "timeout": 1800}
    Stream: text/event-stream — her satır: data: {"stream":"stdout","line":"..."}
            Son satır:                      data: {"done":true,"exit_code":0}
    """
    body    = request.get_json(silent=True) or {}
    command = body.get("command", "").strip()
    timeout = int(body.get("timeout", 300))

    if not command:
        return jsonify({"success": False, "error": "Komut boş olamaz."}), 400
    if not _is_safe_command(command):
        return jsonify({"success": False, "error": "Bu komut engellendi."}), 403

    def generate():
        try:
            with SSHClient.from_config() as ssh:
                for chunk in ssh.stream_command(command, timeout=timeout):
                    yield f"data: {chunk}\n\n"
        except SSHError as e:
            yield f"data: {json.dumps({'stream': 'error', 'line': str(e)})}\n\n"
            yield f"data: {json.dumps({'done': True, 'exit_code': -1})}\n\n"
        except ValueError as e:
            yield f"data: {json.dumps({'stream': 'error', 'line': f'Config hatası: {e}'})}\n\n"
            yield f"data: {json.dumps({'done': True, 'exit_code': -1})}\n\n"

    return Response(
        stream_with_context(generate()),
        content_type = "text/event-stream",
        headers      = {
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",      # Nginx proxy buffering'i devre dışı bırak
            "Connection":       "keep-alive",
        },
    )

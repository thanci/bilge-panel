"""
app/routes/deploy.py — GitHub Webhook ile Otomatik Deploy.

GitHub'dan push bildirimi geldiğinde sunucudaki auto-deploy.sh'ı çalıştırır.

Kurulum:
  1. GitHub repo → Settings → Webhooks → Add webhook
  2. Payload URL: https://bilgeyolcu.com/yonetim/api/deploy/webhook
  3. Content type: application/json
  4. Secret: .env'deki DEPLOY_WEBHOOK_SECRET değeri
  5. Events: "Just the push event"
"""

import hmac
import hashlib
import subprocess
import logging

from flask import Blueprint, request, jsonify, current_app

deploy_bp = Blueprint("deploy", __name__, url_prefix="/api/deploy")
logger = logging.getLogger(__name__)


def verify_github_signature(payload_body: bytes, signature: str, secret: str) -> bool:
    """GitHub webhook imzasını doğrular (HMAC-SHA256)."""
    if not signature:
        return False
    
    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        payload_body,
        hashlib.sha256,
    ).hexdigest()
    
    return hmac.compare_digest(expected, signature)


@deploy_bp.route("/webhook", methods=["POST"])
def github_webhook():
    """
    GitHub Push Webhook Handler.
    
    Güvenlik:
      - HMAC-SHA256 imza doğrulaması
      - Sadece 'main' branch push'larına tepki verir
      - Deploy script'i background'da çalıştırılır
    """
    secret = current_app.config.get("DEPLOY_WEBHOOK_SECRET", "")
    
    if not secret:
        logger.warning("[DEPLOY] DEPLOY_WEBHOOK_SECRET tanımlı değil!")
        return jsonify({"error": "webhook not configured"}), 503
    
    # ── İmza Doğrulama ──
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_github_signature(request.data, signature, secret):
        logger.warning("[DEPLOY] Geçersiz webhook imzası!")
        return jsonify({"error": "invalid signature"}), 403
    
    # ── Event Kontrolü ──
    event = request.headers.get("X-GitHub-Event", "")
    if event == "ping":
        return jsonify({"message": "pong"}), 200
    
    if event != "push":
        return jsonify({"message": f"ignored event: {event}"}), 200
    
    # ── Branch Kontrolü ──
    payload = request.get_json(silent=True) or {}
    ref = payload.get("ref", "")
    
    if ref != "refs/heads/main":
        return jsonify({"message": f"ignored branch: {ref}"}), 200
    
    # ── Deploy Başlat (Background) ──
    commit = payload.get("after", "unknown")[:7]
    pusher = payload.get("pusher", {}).get("name", "unknown")
    
    logger.info(f"[DEPLOY] Webhook tetiklendi: {pusher} → {commit}")
    
    try:
        # Background'da çalıştır — webhook 30 saniye timeout'a düşmesin
        subprocess.Popen(
            ["bash", "/home/bilgeyolcu/bilge-panel/auto-deploy.sh"],
            stdout=open("/home/bilgeyolcu/logs/deploy.log", "a"),
            stderr=subprocess.STDOUT,
            cwd="/home/bilgeyolcu/bilge-panel",
        )
        
        return jsonify({
            "message": "deploy started",
            "commit": commit,
            "pusher": pusher,
        }), 202
        
    except Exception as e:
        logger.error(f"[DEPLOY] Script başlatılamadı: {e}")
        return jsonify({"error": str(e)}), 500


@deploy_bp.route("/status", methods=["GET"])
def deploy_status():
    """Son deploy durumunu gösterir."""
    import os
    log_path = "/home/bilgeyolcu/logs/deploy.log"
    
    if not os.path.exists(log_path):
        return jsonify({"message": "henüz deploy yapılmadı"}), 200
    
    try:
        with open(log_path, "r") as f:
            lines = f.readlines()
            last_lines = lines[-20:] if len(lines) > 20 else lines
        
        return jsonify({
            "last_deploy_log": "".join(last_lines),
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

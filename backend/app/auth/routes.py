"""
app/auth/routes.py — Kimlik doğrulama endpointleri.

Endpoint'ler:
  POST /api/auth/login    — Kullanıcı adı + şifre ile giriş
  POST /api/auth/refresh  — Access token yenileme
  POST /api/auth/logout   — Oturum sonlandırma (token iptal)
  GET  /api/auth/me       — Mevcut kullanıcı bilgisi

Güvenlik Notları:
  - Başarısız login denemeleri IP bazlı rate limit'e tabidir.
  - Logout, hem access hem refresh token'ı blocklist'e ekler.
  - Tüm yanıtlar tutarlı {"success": bool, "data"/"error": ...} formatında.
"""

from datetime import datetime, timezone

from flask import request, jsonify, current_app, g
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)

from app.auth import auth_bp
from app.auth.decorators import require_auth
from app.extensions import db, limiter
from app.models import AdminUser, TokenBlocklist


# ============================================================
# POST /api/auth/login
# ============================================================

@auth_bp.route("/login", methods=["POST"])
@limiter.limit("5 per 10 minutes")   # IP başına 10 dakikada 5 deneme
def login():
    """
    Kullanıcı adı ve şifre ile giriş yapar.
    Başarılı girişte access_token + refresh_token döner.
    
    İstek Gövdesi (JSON):
        {
            "username": "admin",
            "password": "gizli_sifre"
        }
    
    Yanıt (200 OK):
        {
            "success": true,
            "data": {
                "access_token": "eyJ...",
                "refresh_token": "eyJ...",
                "user": { "id": 1, "username": "admin", ... }
            }
        }
    """
    try:
        # --- İstek Verisi Doğrulama ---
        body = request.get_json(silent=True)
        if not body:
            return jsonify({
                "success": False,
                "error": "invalid_json",
                "message": "İstek gövdesi geçerli JSON olmalıdır.",
            }), 400

        username = body.get("username", "").strip()
        password = body.get("password", "")

        if not username or not password:
            return jsonify({
                "success": False,
                "error": "missing_fields",
                "message": "Kullanıcı adı ve şifre zorunludur.",
            }), 400

        # --- Kullanıcı Sorgulama ---
        user = AdminUser.query.filter_by(username=username).first()

        # Kullanıcı bulunamadı veya şifre yanlış — aynı mesaj (güvenlik)
        if not user or not user.check_password(password):
            current_app.logger.warning(
                f"[AUTH] Başarısız giriş denemesi: username='{username}' "
                f"ip={request.remote_addr}"
            )
            return jsonify({
                "success": False,
                "error": "invalid_credentials",
                "message": "Kullanıcı adı veya şifre hatalı.",
            }), 401

        # --- Hesap Aktif Mi? ---
        if not user.is_active:
            return jsonify({
                "success": False,
                "error": "account_disabled",
                "message": "Bu hesap devre dışı bırakılmış.",
            }), 403

        # --- Token Üretimi ---
        # Flask-JWT-Extended 4.7+ identity'nin string olmasını zorunlu kılar
        uid = str(user.id)
        access_token  = create_access_token(identity=uid)
        refresh_token = create_refresh_token(identity=uid)

        # --- Son Giriş Zamanını Güncelle ---
        try:
            user.last_login_at = datetime.now(timezone.utc)
            db.session.commit()
        except Exception as db_err:
            # Son giriş güncellemesi başarısız olsa bile login devam etsin
            db.session.rollback()
            current_app.logger.warning(f"[AUTH] last_login_at güncellenemedi: {db_err}")

        current_app.logger.info(f"[AUTH] Başarılı giriş: username='{username}'")
        return jsonify({
            "success": True,
            "data": {
                "access_token":  access_token,
                "refresh_token": refresh_token,
                "user":          user.to_dict(),
            },
        }), 200

    except Exception as e:
        current_app.logger.error(f"[AUTH] Login endpoint hatası: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "server_error",
            "message": "Giriş işlemi sırasında sunucu hatası oluştu.",
        }), 500


# ============================================================
# POST /api/auth/refresh
# ============================================================

@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)   # Refresh token zorunlu (access token DEĞİL)
def refresh():
    """
    Geçerli bir refresh token ile yeni access token üretir.
    Access token süresi dolduğunda Vue.js bu endpoint'i çağırır.
    
    Header:
        Authorization: Bearer <refresh_token>
    
    Yanıt (200 OK):
        {
            "success": true,
            "data": {
                "access_token": "eyJ..."
            }
        }
    """
    try:
        user_id = get_jwt_identity()

        # Kullanıcı hâlâ aktif mi? (SQLAlchemy 2.x uyumlu)
        user = db.session.get(AdminUser, int(user_id))
        if not user or not user.is_active:
            return jsonify({
                "success": False,
                "error": "account_unavailable",
                "message": "Hesabınız artık erişilemez durumda.",
            }), 403

        new_access_token = create_access_token(identity=str(user_id))

        return jsonify({
            "success": True,
            "data": {"access_token": new_access_token},
        }), 200

    except Exception as e:
        current_app.logger.error(f"[AUTH] Refresh hatası: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "server_error",
            "message": "Token yenileme sırasında hata oluştu.",
        }), 500


# ============================================================
# POST /api/auth/logout
# ============================================================

@auth_bp.route("/logout", methods=["POST"])
@jwt_required(verify_type=False)   # Access veya refresh token kabul eder
def logout():
    """
    Mevcut token'ı (ve varsa refresh token'ı) blocklist'e ekler.
    Vue.js, logout sırasında her iki token'ı ayrı ayrı bu endpoint'e göndermelidir.
    
    Header:
        Authorization: Bearer <token>
    
    Yanıt (200 OK):
        { "success": true, "message": "Oturum sonlandırıldı." }
    """
    try:
        jwt_payload  = get_jwt()
        jti          = jwt_payload.get("jti")
        token_type   = jwt_payload.get("type", "access")

        if not jti:
            return jsonify({
                "success": False,
                "error": "invalid_token",
                "message": "Token'ın JTI alanı bulunamadı.",
            }), 400

        # Token zaten blocklist'te mi?
        existing = TokenBlocklist.query.filter_by(jti=jti).first()
        if existing:
            # İdempotent davran — hata döndürme
            return jsonify({"success": True, "message": "Oturum zaten sonlandırılmıştı."}), 200

        # Token'ı blocklist'e ekle
        blocked = TokenBlocklist(jti=jti, token_type=token_type)
        db.session.add(blocked)
        db.session.commit()

        current_app.logger.info(f"[AUTH] Token iptal edildi: jti={jti[:8]}... type={token_type}")
        return jsonify({"success": True, "message": "Oturum başarıyla sonlandırıldı."}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"[AUTH] Logout hatası: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "server_error",
            "message": "Oturum sonlandırma sırasında hata oluştu.",
        }), 500


# ============================================================
# GET /api/auth/me
# ============================================================

@auth_bp.route("/me", methods=["GET"])
@require_auth   # Kendi decorator'ımızı kullan — g.current_user inject edilir
def me():
    """
    Mevcut oturum açmış kullanıcının bilgilerini döndürür.
    Vue.js sayfa ilk yüklendiğinde bu endpoint ile kullanıcıyı doğrular.
    
    Header:
        Authorization: Bearer <access_token>
    
    Yanıt (200 OK):
        {
            "success": true,
            "data": {
                "user": { "id": 1, "username": "admin", ... }
            }
        }
    """
    try:
        user = g.current_user  # @require_auth tarafından inject edildi
        return jsonify({
            "success": True,
            "data": {"user": user.to_dict()},
        }), 200

    except Exception as e:
        current_app.logger.error(f"[AUTH] /me endpoint hatası: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "server_error",
            "message": "Kullanıcı bilgisi alınamadı.",
        }), 500

"""
app/routes/debug.py — Geçici tanılama endpoint'i.

Bu dosya JWT token sorununu teşhis etmek için oluşturulmuştur.
Sorun çözüldükten sonra SİLİNMELİDİR.
"""

from flask import jsonify, request, current_app
from app.routes import main_bp


@main_bp.route("/debug/token", methods=["GET"])
def debug_token():
    """
    JWT token tanılama endpoint'i.
    Authorization header'ı okur, token'ı decode eder, sonucu döner.
    Herhangi bir decorator KULLANMAZ — saf test.
    """
    result = {}

    # 1. Header kontrolü
    auth_header = request.headers.get("Authorization", "")
    result["auth_header_present"] = bool(auth_header)
    result["auth_header_value"] = auth_header[:80] + "..." if len(auth_header) > 80 else auth_header

    # 2. Config kontrolü
    jwt_key = current_app.config.get("JWT_SECRET_KEY", "")
    secret_key = current_app.config.get("SECRET_KEY", "")
    result["jwt_secret_key_len"] = len(jwt_key)
    result["jwt_secret_key_first10"] = jwt_key[:10] + "..."
    result["secret_key_first10"] = secret_key[:10] + "..."
    result["keys_match"] = jwt_key == secret_key

    # 3. Token decode denemesi
    if auth_header.startswith("Bearer "):
        token_str = auth_header[7:]
        result["token_length"] = len(token_str)

        try:
            from flask_jwt_extended import decode_token
            decoded = decode_token(token_str)
            result["decode_success"] = True
            result["identity"] = decoded.get("sub")
            result["token_type"] = decoded.get("type")
            result["jti"] = decoded.get("jti")
            result["exp"] = decoded.get("exp")
        except Exception as e:
            result["decode_success"] = False
            result["decode_error"] = f"{type(e).__name__}: {e}"

        # 4. Blocklist kontrolü
        try:
            from app.models import TokenBlocklist
            from app.extensions import db
            jti = result.get("jti")
            if jti:
                blocked = TokenBlocklist.query.filter_by(jti=jti).first()
                result["in_blocklist"] = blocked is not None
        except Exception as e:
            result["blocklist_error"] = f"{type(e).__name__}: {e}"

        # 5. Kullanıcı kontrolü
        try:
            from app.models import AdminUser
            from app.extensions import db
            identity = result.get("identity")
            if identity is not None:
                user = db.session.get(AdminUser, identity)
                result["user_found"] = user is not None
                if user:
                    result["user_active"] = user.is_active
                    result["user_name"] = user.username
        except Exception as e:
            result["user_error"] = f"{type(e).__name__}: {e}"
    else:
        result["token_issue"] = "Bearer prefix yok veya Authorization header boş"

    return jsonify({"success": True, "debug": result}), 200

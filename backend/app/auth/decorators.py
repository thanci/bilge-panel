"""
app/auth/decorators.py — Kimlik doğrulama decorator'ları.

Bu decorator'lar route handler'larının başına eklenerek
yetkisiz erişimi engeller ve mevcut kullanıcıyı inject eder.

Kullanım:
    @require_auth
    def protected_route():
        # g.current_user ile mevcut admin'e erişilir
        ...

    @require_admin
    def admin_only_route():
        ...
"""

import functools
from flask import jsonify, g
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity

from app.extensions import db
from app.models import AdminUser


def require_auth(fn):
    """
    Decorator: Geçerli JWT access token zorunlu.

    Token geçerliyse:
      - g.current_user → AdminUser nesnesi olarak set edilir
      - Route handler çalıştırılır

    Token geçersiz veya eksikse:
      - Flask-JWT-Extended kendi hata handler'larını tetikler (401)

    DÜZELTME: SQLAlchemy 2.0'da Query.get() kaldırıldı.
    Model.query.get(id) → db.session.get(Model, id) olarak güncellendi.
    Eski kod AttributeError fırlatıyor, except bloğu 401 dönüyordu.
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            # JWT'yi doğrula — geçersiz/süresi dolmuşsa exception fırlatır
            verify_jwt_in_request()

            # Token payload'ından kullanıcı kimliğini al
            # (identity string olarak saklanıyor — int'e çevir)
            user_id = get_jwt_identity()

            # Kullanıcıyı veritabanından çek (SQLAlchemy 2.x uyumlu)
            user = db.session.get(AdminUser, int(user_id))
            if not user:
                return jsonify({
                    "success": False,
                    "error": "user_not_found",
                    "message": "Bu token'a ait kullanıcı bulunamadı.",
                }), 401

            if not user.is_active:
                return jsonify({
                    "success": False,
                    "error": "account_disabled",
                    "message": "Bu hesap devre dışı bırakılmış.",
                }), 403

            # Kullanıcıyı request context'ine ekle
            # Sonraki handler'lar g.current_user ile erişebilir
            g.current_user = user

        except Exception as e:
            # ── Tanılama: gerçek hatayı backend terminal'e bas ──
            import traceback
            from flask import current_app
            current_app.logger.error(
                f"[AUTH] require_auth HATA: {type(e).__name__}: {e}"
            )
            current_app.logger.error(traceback.format_exc())

            return jsonify({
                "success": False,
                "error": "auth_error",
                "message": f"Kimlik doğrulama hatası: {type(e).__name__}: {e}",
            }), 401


        return fn(*args, **kwargs)

    return wrapper


def require_admin(fn):
    """
    Decorator: @require_auth'u içerir + aktif admin hesabı kontrolü yapar.
    Şu an tüm admin kullanıcılar eşit yetkiye sahip.
    İleride role tabanlı yetkilendirme buraya eklenebilir.
    """
    @functools.wraps(fn)
    @require_auth  # require_auth'u zincirle
    def wrapper(*args, **kwargs):
        # Ek yetki kontrolleri buraya eklenebilir
        # Örnek: if g.current_user.role != "superadmin": return 403
        return fn(*args, **kwargs)

    return wrapper

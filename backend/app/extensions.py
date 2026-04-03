"""
app/extensions.py — Flask eklenti örnekleri.

Tüm eklentiler burada tanımlanır ve app factory'de init_app() ile
bağlanır. Bu yaklaşım döngüsel import'ları önler.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# --- Veritabanı ORM ---
# Tüm model sınıfları bu nesneyi miras alır
db = SQLAlchemy()

# --- JWT Yöneticisi ---
# Token doğrulama, yenileme ve blocklist işlemleri
jwt = JWTManager()

# --- CORS ---
# Vue.js frontend'in farklı origin'den istek yapmasına izin verir
cors = CORS()

# --- Rate Limiter ---
# IP tabanlı istek sınırlama (brute-force koruması)
# Storage URI uygulama başlatılırken config'den inject edilir
limiter = Limiter(
    key_func=get_remote_address,   # İstemci IP'si üzerinden sınırla
    default_limits=["2000 per day", "500 per hour"],
)

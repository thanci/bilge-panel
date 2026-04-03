"""
app/auth/__init__.py — Auth Blueprint tanımı.

Bu dosya, auth modülünün diğer modüller tarafından import
edilebileceği Blueprint nesnesini dışa açar.
"""

from flask import Blueprint

# Blueprint adı "auth" — URL prefix app factory'de belirlenir (/api/auth)
auth_bp = Blueprint("auth", __name__)

# Routes'ları blueprint'e bağla (import sırası önemli — döngüsel import önlemi)
from app.auth import routes  # noqa: F401, E402

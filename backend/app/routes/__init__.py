"""
app/routes/__init__.py — Ana Blueprint tanımı.

Genel amaçlı endpointleri (health check, sistem durumu vb.) barındırır.
"""

from flask import Blueprint

main_bp = Blueprint("main", __name__)

# Routes dosyalarını import et
from app.routes import health  # noqa: F401, E402


"""
app/updater/__init__.py — DevOps Güncelleyici Blueprint.
"""

from flask import Blueprint

updater_bp = Blueprint("updater", __name__)

from app.updater import routes  # noqa: F401, E402

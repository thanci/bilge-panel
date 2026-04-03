"""
app/theme/__init__.py — Tema Editörü Blueprint.
"""

from flask import Blueprint

theme_bp = Blueprint("theme", __name__)

from app.theme import routes  # noqa: F401, E402

"""
app/budget/__init__.py — Budget Blueprint tanımı.
"""

from flask import Blueprint

budget_bp = Blueprint("budget", __name__)

from app.budget import routes  # noqa: F401, E402

"""
app/tasks/__init__.py — Tasks Blueprint tanımı.
"""

from flask import Blueprint

tasks_bp = Blueprint("tasks", __name__)

from app.tasks import routes  # noqa: F401, E402

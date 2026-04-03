"""
app/ssh/__init__.py — SSH Blueprint.
"""

from flask import Blueprint

ssh_bp = Blueprint("ssh", __name__)

from app.ssh import routes  # noqa: F401, E402

"""
app/xenforo/__init__.py — XenForo Blueprint.
"""

from flask import Blueprint

xf_bp = Blueprint("xenforo", __name__)

from app.xenforo import routes  # noqa: F401, E402

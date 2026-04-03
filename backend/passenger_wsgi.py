"""
passenger_wsgi.py — cPanel Phusion Passenger giriş noktası.

cPanel "Setup Python App" bu dosyayı otomatik olarak başlatır.
Passenger, her gelen isteği buradaki `application` callable'ına yönlendirir.

cPanel Ayarları:
  - Application root:  /home/bilgeyolcu/bilge-panel/backend
  - Application URL:   /yonetim
  - Application startup file: passenger_wsgi.py
  - Application Entry point:  application
  - Python version:    3.11

Passenger, SCRIPT_NAME (PASSENGER_BASE_URI) olarak /yonetim ekler.
Flask istekleri /yonetim prefix'i olmadan alır:
  https://bilgeyolcu.com/yonetim/api/auth/login → Flask'a /api/auth/login gelir
  https://bilgeyolcu.com/yonetim/login           → Flask'a /login gelir
"""

import os
import sys

# ── 1. Backend dizinini sys.path'e ekle ──────────────────────
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# ── 2. .env dosyasını yükle ─────────────────────────────────
# Passenger, cwd'yi değiştirebilir — mutlak yol kullan
from dotenv import load_dotenv
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

# ── 3. Flask uygulamasını oluştur ───────────────────────────
from app import create_app

application = create_app()

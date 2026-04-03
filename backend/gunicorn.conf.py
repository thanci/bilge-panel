"""
gunicorn.conf.py — Gunicorn üretim yapılandırması.

Kullanım:
  gunicorn -c gunicorn.conf.py wsgi:application

systemd servisi bu dosyayı otomatik olarak referans alır.
"""

import os
import multiprocessing

# ── Bağlantı ──────────────────────────────────────────────
# Apache mod_proxy bu adrese yönlendirir
bind = os.environ.get("GUNICORN_BIND", "127.0.0.1:5000")

# ── Worker Sayısı ─────────────────────────────────────────
# Kural: (2 × CPU çekirdek) + 1
# VDS'de genellikle 2-4 CPU → 5-9 worker
# SQLite kullandığımız için fazla worker write-lock sorununa
# neden olabilir. 3 worker güvenli bir başlangıç.
workers = int(os.environ.get("GUNICORN_WORKERS", 3))

# ── Worker Türü ───────────────────────────────────────────
# sync: SQLite ile en uyumlu (write-lock sorunu yok)
# gthread: I/O-bound işlemler için (SSE streaming gerekirse)
worker_class = "sync"

# ── Zaman Aşımı ──────────────────────────────────────────
# LLM API çağrıları uzun sürebilir — 120 saniye
timeout = 120

# ── Graceful Timeout ──────────────────────────────────────
graceful_timeout = 30

# ── Keep-Alive ────────────────────────────────────────────
keepalive = 5

# ── Preload ───────────────────────────────────────────────
# Uygulamayı fork öncesi yükle → bellek tasarrufu
preload_app = True

# ── Logging ───────────────────────────────────────────────
accesslog = os.environ.get(
    "GUNICORN_ACCESS_LOG",
    "/home/bilgeyolcu/bilge-panel/logs/gunicorn-access.log"
)
errorlog = os.environ.get(
    "GUNICORN_ERROR_LOG",
    "/home/bilgeyolcu/bilge-panel/logs/gunicorn-error.log"
)
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")

# ── PID Dosyası ───────────────────────────────────────────
pidfile = "/home/bilgeyolcu/bilge-panel/logs/gunicorn.pid"

# ── Max Requests (Worker Recycling) ──────────────────────
# Her worker bu kadar request sonra yeniden başlatılır
# → memory leak koruması
max_requests = 1000
max_requests_jitter = 50

# ── Güvenlik ──────────────────────────────────────────────
# Proxy arkasında çalışıyoruz — X-Forwarded-* header'larına güven
forwarded_allow_ips = "127.0.0.1"

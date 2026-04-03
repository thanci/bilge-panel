"""
run.py — Geliştirme ortamı için uygulama başlatıcı.
Üretim ortamında bu dosya yerine wsgi.py + gunicorn kullanılır.

Kullanım:
    python run.py
"""

from app import create_app

# Uygulama fabrikasından Flask instance'ı oluştur
app = create_app()

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",        # Sadece localhost — güvenlik
        port=app.config["PORT"],
        debug=app.config["DEBUG"],
        use_reloader=False,      # Celery worker'larla çakışmayı önler
    )

"""
wsgi.py — Apache mod_wsgi / Gunicorn üretim giriş noktası.

cPanel'deki Passenger veya mod_wsgi bu dosyayı arar.
Apache VirtualHost'a eklenecek satır:
    WSGIScriptAlias /yonetim /home/KULLANICI/bilge-panel/backend/wsgi.py

Gunicorn ile başlatmak için:
    gunicorn --bind 127.0.0.1:5000 --workers 2 wsgi:application
"""

from app import create_app

# mod_wsgi veya gunicorn, 'application' adında bir callable bekler
application = create_app()

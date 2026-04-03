"""
app/__init__.py — Flask uygulama fabrikası (App Factory).

Neden fabrika deseni?
  - Test sırasında farklı config ile birden fazla uygulama örneği oluşturulabilir.
  - Eklentiler create_app() çağrılana kadar başlatılmaz → döngüsel import yok.
  - Blueprint'ler burada kayıt altına alınır.
"""

import logging
from flask import Flask, jsonify

from app.config import get_config
from app.extensions import db, jwt, cors, limiter


def create_app() -> Flask:
    """
    Flask uygulama örneğini oluşturur, yapılandırır ve döndürür.
    wsgi.py ve run.py tarafından çağrılır.
    """
    app = Flask(__name__)

    # ---- 1. Yapılandırmayı Yükle ----------------------------------------
    config_class = get_config()
    app.config.from_object(config_class)

    # ---- 2. Loglama Ayarla -----------------------------------------------
    _configure_logging(app)

    # ---- 3. Eklentileri Başlat -------------------------------------------
    _init_extensions(app)

    # ---- 4. Veritabanı Tablolarını Oluştur -------------------------------
    _init_database(app)

    # ---- 5. JWT Callback'lerini Tanımla ----------------------------------
    _register_jwt_handlers(app)

    # ---- 6. Blueprint'leri Kaydet ----------------------------------------
    _register_blueprints(app)

    # ---- 7. Celery'yi Başlat (mevcut app context ile) --------------------
    _init_celery(app)

    # ---- 8. Hata Yöneticilerini Kaydet -----------------------------------
    _register_error_handlers(app)

    app.logger.info(
        f"[APP] Bilge Yolcu paneli başlatıldı | "
        f"ENV={app.config.get('ENV', 'production')} | "
        f"DEBUG={app.debug}"
    )
    return app


def _configure_logging(app: Flask) -> None:
    """
    Üretim ortamında loglama seviyesini INFO'ya ayarlar.
    Geliştirmede DEBUG seviyesinde detaylı log üretilir.
    """
    level = logging.DEBUG if app.debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    app.logger.setLevel(level)


def _init_extensions(app: Flask) -> None:
    """
    Tüm Flask eklentilerini uygulama bağlamına bağlar.
    Her eklentinin init_app() metodu burada çağrılır.
    """
    # Veritabanı ORM
    db.init_app(app)

    # JWT kimlik doğrulama
    jwt.init_app(app)

    # CORS — sadece izin verilen origin'lere açık
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
        supports_credentials=True,
    )

    # Rate limiter — brute-force koruması
    limiter.init_app(app)


def _init_database(app: Flask) -> None:
    """
    Tüm ORM modellerini import ederek veritabanı tablolarını oluşturur.
    Tablo zaten varsa dokunmaz (CREATE TABLE IF NOT EXISTS davranışı).
    """
    with app.app_context():
        # Modellerin import edilmesi SQLAlchemy'nin tablo haritasını doldurur
        from app import models  # noqa: F401 — Yalnızca kayıt için import

        db.create_all()
        app.logger.info("[DB] Tablolar doğrulandı / oluşturuldu.")


def _register_jwt_handlers(app: Flask) -> None:
    """
    Flask-JWT-Extended callback'lerini tanımlar.
    Token blocklist kontrolü ve hata yanıtları burada şekillendirilir.
    """
    from app.models import TokenBlocklist

    @jwt.token_in_blocklist_loader
    def check_token_in_blocklist(jwt_header, jwt_payload) -> bool:
        """
        Her korumalı endpoint çağrısında bu callback çalışır.
        Token JTI'sini blocklist tablosunda arar.
        Döndürür: True → token geçersiz (erişim reddedilir)

        DÜZELTME: SQLAlchemy 2.x'te db.session.query(Model.query...).scalar()
        sözdizimi çalışmıyor. Basit .first() is not None kullanıldı.
        """
        jti = jwt_payload.get("jti")
        if not jti:
            return True  # JTI yoksa güvenli taraf: reddet
        try:
            # SQLAlchemy 1.x ve 2.x ile uyumlu sorgu
            blocked = TokenBlocklist.query.filter_by(jti=jti).first()
            return blocked is not None
        except Exception as e:
            app.logger.error(f"[JWT] Blocklist sorgu hatası: {e}")
            return False  # Hata durumunda erişime izin ver (fail-open)
                          # Alternatif: return True (fail-closed, daha güvenli)


    @jwt.expired_token_loader
    def expired_token_response(jwt_header, jwt_payload):
        return jsonify({
            "success": False,
            "error": "token_expired",
            "message": "Oturum süreniz doldu. Lütfen yeniden giriş yapın.",
        }), 401

    @jwt.invalid_token_loader
    def invalid_token_response(error_msg):
        return jsonify({
            "success": False,
            "error": "invalid_token",
            "message": "Geçersiz kimlik doğrulama token'ı.",
        }), 401

    @jwt.unauthorized_loader
    def missing_token_response(error_msg):
        return jsonify({
            "success": False,
            "error": "missing_token",
            "message": "Bu işlem için kimlik doğrulama gerekli.",
        }), 401

    @jwt.revoked_token_loader
    def revoked_token_response(jwt_header, jwt_payload):
        return jsonify({
            "success": False,
            "error": "token_revoked",
            "message": "Bu oturum sonlandırıldı. Lütfen yeniden giriş yapın.",
        }), 401


def _register_blueprints(app: Flask) -> None:
    """
    Tüm route blueprint'lerini uygulamaya kaydeder.
    Yeni modüller eklendikçe buraya blueprint kaydı eklenir.
    """
    # Auth blueprint: /api/auth/*
    from app.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix="/api/auth")

    # Sağlık kontrolü: /api/health
    from app.routes import main_bp
    app.register_blueprint(main_bp, url_prefix="/api")

    # Bütçe ve Circuit Breaker: /api/budget/*
    from app.budget import budget_bp
    app.register_blueprint(budget_bp, url_prefix="/api/budget")

    # Görev Yönetimi: /api/tasks/*
    from app.tasks import tasks_bp
    app.register_blueprint(tasks_bp, url_prefix="/api/tasks")

    # XenForo API: /api/xenforo/*
    from app.xenforo import xf_bp
    app.register_blueprint(xf_bp, url_prefix="/api/xenforo")

    # SSH Terminali: /api/ssh/*
    from app.ssh import ssh_bp
    app.register_blueprint(ssh_bp, url_prefix="/api/ssh")

    # DevOps Güncelleyici: /api/updater/*
    from app.updater import updater_bp
    app.register_blueprint(updater_bp, url_prefix="/api/updater")

    # Tema Editörü: /api/theme/*
    from app.theme import theme_bp
    app.register_blueprint(theme_bp, url_prefix="/api/theme")

    # Deploy Webhook: /api/deploy/*
    from app.routes.deploy import deploy_bp
    app.register_blueprint(deploy_bp)

    # ── SPA Statik Dosya Servisi (Üretim / Passenger) ────────────────
    # Geliştirmede Vite dev server kullanılır, burası atlanır.
    # Üretimde Passenger TÜM istekleri Flask'a yönlendirir, bu yüzden
    # Vue.js build dosyalarını (JS, CSS, index.html) Flask sunmalıdır.
    _register_spa_routes(app)

    app.logger.info("[APP] Blueprint'ler kaydedildi.")


def _init_celery(app: Flask) -> None:
    """
    Celery'yi Flask uygulamasına bağlar.
    celery_worker.py'de de çağrılır; burada app context aktif iken
    yapılandırmanın doğruluğunu doğrular.
    """
    try:
        from app.tasks.celery_app import celery, init_celery
        init_celery(app)
        app.logger.info("[APP] Celery başlatıldı.")
    except Exception as e:
        # Celery başlamazsa uygulama çökmeden devam etsin
        # (Redis olmadan geliştirme ortamında çalışabilir)
        app.logger.warning(f"[APP] Celery başlatılamadı: {e} — async görevler devre dışı.")


def _register_error_handlers(app: Flask) -> None:
    """
    Uygulama genelinde HTTP hata yanıtlarını JSON formatına çevirir.
    Vue.js frontend'in tutarlı hata formatı almasını sağlar.
    """
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"success": False, "error": "bad_request", "message": str(e)}), 400

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({"success": False, "error": "forbidden", "message": "Erişim reddedildi."}), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"success": False, "error": "not_found", "message": "Kaynak bulunamadı."}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"success": False, "error": "method_not_allowed", "message": str(e)}), 405

    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        return jsonify({
            "success": False,
            "error": "rate_limit_exceeded",
            "message": "Çok fazla istek gönderildi. Lütfen bekleyin.",
        }), 429

    @app.errorhandler(500)
    def internal_error(e):
        app.logger.error(f"[SERVER] Sunucu hatası: {e}")
        return jsonify({
            "success": False,
            "error": "internal_server_error",
            "message": "Sunucu hatası oluştu. Lütfen sistem loglarını kontrol edin.",
        }), 500


def _register_spa_routes(app: Flask) -> None:
    """
    Üretim modunda Vue.js SPA dosyalarını Flask üzerinden servis eder.

    Geliştirme modunda (debug=True), Vite dev server tüm frontend'i
    yönettiği için bu fonksiyon hiçbir şey yapmaz.

    Üretimde Passenger tüm istekleri Flask'a yönlendirir:
      - /api/* → Blueprint'ler (auth, budget, tasks, vb.)
      - /assets/* → Vue.js build dosyaları (JS, CSS)
      - /* → index.html (Vue Router history mode catch-all)
    """
    import os
    from flask import send_from_directory

    # Geliştirme modunda atla — Vite zaten hallediyor
    if app.debug:
        return

    # Vue.js build dizini: backend/public/yonetim/
    spa_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "public", "yonetim"
    )
    spa_dir = os.path.normpath(spa_dir)

    if not os.path.isdir(spa_dir):
        app.logger.warning(
            f"[SPA] Vue.js build dizini bulunamadı: {spa_dir} — "
            f"'npm run build' çalıştırmanız gerekiyor."
        )
        return

    index_path = os.path.join(spa_dir, "index.html")
    if not os.path.isfile(index_path):
        app.logger.warning(f"[SPA] index.html bulunamadı: {index_path}")
        return

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_spa(path):
        """
        SPA catch-all route.
        - Dosya varsa (JS, CSS, font, resim) doğrudan sun.
        - Yoksa index.html döndür (Vue Router yönetecek).
        """
        # API istekleri buraya düşmemeli (blueprint'ler yakalamış olmalı)
        if path.startswith("api/"):
            return jsonify({
                "success": False,
                "error": "not_found",
                "message": "API endpoint bulunamadı.",
            }), 404

        # Dosya varsa sun
        file_path = os.path.join(spa_dir, path)
        if path and os.path.isfile(file_path):
            return send_from_directory(spa_dir, path)

        # Yoksa index.html döndür — Vue Router devralır
        return send_from_directory(spa_dir, "index.html")

    app.logger.info(f"[SPA] Vue.js statik servis aktif: {spa_dir}")


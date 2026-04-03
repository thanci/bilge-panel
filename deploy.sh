#!/usr/bin/env bash
# ============================================================
# deploy.sh — Bilge Yolcu Panel — VDS Deployment Script
#
# İlk kurulum:   bash deploy.sh --init
# Güncelleme:    bash deploy.sh
# Sadece restart: bash deploy.sh --restart
# Admin oluştur:  bash deploy.sh --admin
# ============================================================

set -euo pipefail

# ── Renk Kodları ──────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[✗]${NC} $*" >&2; }
info() { echo -e "${CYAN}[→]${NC} $*"; }

# ── Değişkenler ───────────────────────────────────────────
HOME_DIR="/home/bilgeyolcu"
PROJECT_DIR="${HOME_DIR}/bilge-panel"
BACKEND_DIR="${PROJECT_DIR}/backend"
PUBLIC_HTML="${HOME_DIR}/public_html"
PANEL_PUBLIC="${PUBLIC_HTML}/yonetim"
VENV_DIR="${PROJECT_DIR}/venv"
PYTHON_BIN="/opt/alt/python311/bin/python3"
PIP="${VENV_DIR}/bin/pip"
PYTHON="${VENV_DIR}/bin/python3"
SYSTEMD_DIR="${PROJECT_DIR}/systemd"
LOG_DIR="${PROJECT_DIR}/logs"

# ══════════════════════════════════════════════════════════
# Fonksiyonlar
# ══════════════════════════════════════════════════════════

check_prerequisites() {
    info "Ön koşullar kontrol ediliyor..."

    local ok=true

    # Python
    if [ ! -f "${PYTHON_BIN}" ]; then
        err "Python 3.11 bulunamadı: ${PYTHON_BIN}"
        ok=false
    fi

    # Redis
    if command -v redis-cli &>/dev/null; then
        if redis-cli ping &>/dev/null; then
            log "Redis aktif"
        else
            warn "Redis kurulu ama çalışmıyor — 'sudo systemctl start redis' deneyin"
        fi
    else
        warn "redis-cli bulunamadı — Celery memory modunda çalışacak"
    fi

    # Proje dizini
    if [ ! -d "${PROJECT_DIR}" ]; then
        err "Proje dizini yok: ${PROJECT_DIR}"
        ok=false
    fi

    if [ "$ok" = false ]; then exit 1; fi
    log "Ön koşullar tamam"
}

create_venv() {
    if [ -d "${VENV_DIR}" ]; then
        warn "venv mevcut — atlanıyor"
    else
        info "Python venv oluşturuluyor..."
        ${PYTHON_BIN} -m venv "${VENV_DIR}"
        log "venv oluşturuldu"
    fi

    info "Bağımlılıklar kuruluyor..."
    ${PIP} install --upgrade pip setuptools wheel -q
    ${PIP} install -r "${BACKEND_DIR}/requirements.txt" -q
    log "Bağımlılıklar kuruldu"
}

setup_directories() {
    mkdir -p "${PANEL_PUBLIC}" "${HOME_DIR}/backups" "${LOG_DIR}"
    log "Dizinler hazır"
}

deploy_frontend() {
    local BUILD_DIR="${BACKEND_DIR}/public/yonetim"

    if [ ! -d "${BUILD_DIR}" ]; then
        err "Frontend build dizini yok: ${BUILD_DIR}"
        err "Lokal makinede 'npm run build' çalıştırın"
        exit 1
    fi

    info "Frontend dosyaları kopyalanıyor..."

    # Eski dosyaları temizle (.htaccess hariç)
    find "${PANEL_PUBLIC}" -maxdepth 1 \
        -not -name '.htaccess' \
        -not -name '.' \
        -exec rm -rf {} + 2>/dev/null || true

    # Build dosyalarını kopyala
    cp -r "${BUILD_DIR}/"* "${PANEL_PUBLIC}/"

    # .htaccess'i yerleştir
    if [ ! -f "${PANEL_PUBLIC}/.htaccess" ] || [ "${1:-}" = "--force" ]; then
        cp "${BACKEND_DIR}/.htaccess" "${PANEL_PUBLIC}/.htaccess"
        log ".htaccess güncellendi"
    fi

    log "Frontend deploy edildi → ${PANEL_PUBLIC}"
}

setup_env() {
    if [ ! -f "${BACKEND_DIR}/.env" ]; then
        if [ -f "${BACKEND_DIR}/.env.production" ]; then
            cp "${BACKEND_DIR}/.env.production" "${BACKEND_DIR}/.env"
            warn ".env.production → .env kopyalandı"
            warn "LÜTFEN .env değerlerini düzenleyin: nano ${BACKEND_DIR}/.env"
        else
            err ".env dosyası bulunamadı!"
            exit 1
        fi
    fi
    chmod 600 "${BACKEND_DIR}/.env"
    log ".env güvenli (chmod 600)"
}

init_database() {
    info "Veritabanı tabloları oluşturuluyor..."
    cd "${BACKEND_DIR}"
    ${PYTHON} -c "
from dotenv import load_dotenv; load_dotenv()
from app import create_app
app = create_app()
with app.app_context():
    from app.extensions import db
    db.create_all()
    print('[DB] Tablolar oluşturuldu.')
"
    log "Veritabanı hazır"
}

create_admin() {
    info "Admin kullanıcısı oluşturuluyor..."
    cd "${BACKEND_DIR}"
    ${PYTHON} -c "
import sys
from dotenv import load_dotenv; load_dotenv()
from app import create_app
from app.extensions import db
from app.models import AdminUser

app = create_app()
with app.app_context():
    if AdminUser.query.filter_by(username='admin').first():
        print('[ADMIN] admin zaten mevcut — atlanıyor.')
        sys.exit(0)
    password = input('Admin şifresi girin (min 6 karakter): ')
    if len(password) < 6:
        print('[HATA] Şifre çok kısa.'); sys.exit(1)
    user = AdminUser(username='admin', email='admin@bilgeyolcu.com',
                     display_name='Yönetici', is_active=True)
    user.set_password(password)
    db.session.add(user); db.session.commit()
    print(f'[ADMIN] ✓ admin oluşturuldu (ID: {user.id})')
"
}

# ── systemd Servisleri ────────────────────────────────────
install_services() {
    if ! command -v systemctl &>/dev/null; then
        warn "systemd bulunamadı — Passenger moduna geçiliyor"
        restart_passenger
        return
    fi

    info "systemd servisleri kuruluyor..."

    # Servis dosyalarını kopyala
    sudo cp "${SYSTEMD_DIR}/bilgeyolcu-gunicorn.service" /etc/systemd/system/
    sudo cp "${SYSTEMD_DIR}/bilgeyolcu-celery.service" /etc/systemd/system/

    sudo systemctl daemon-reload

    # Servisleri etkinleştir (boot'ta otomatik başlasın)
    sudo systemctl enable bilgeyolcu-gunicorn.service
    sudo systemctl enable bilgeyolcu-celery.service

    # Başlat
    sudo systemctl restart bilgeyolcu-gunicorn.service
    sudo systemctl restart bilgeyolcu-celery.service

    log "Gunicorn servisi: $(sudo systemctl is-active bilgeyolcu-gunicorn)"
    log "Celery servisi:   $(sudo systemctl is-active bilgeyolcu-celery)"
}

restart_services() {
    if command -v systemctl &>/dev/null; then
        info "Servisler yeniden başlatılıyor..."
        sudo systemctl restart bilgeyolcu-gunicorn.service
        sudo systemctl restart bilgeyolcu-celery.service
        log "Gunicorn: $(sudo systemctl is-active bilgeyolcu-gunicorn)"
        log "Celery:   $(sudo systemctl is-active bilgeyolcu-celery)"
    else
        restart_passenger
    fi
}

restart_passenger() {
    info "Passenger yeniden başlatılıyor..."
    mkdir -p "${BACKEND_DIR}/tmp"
    touch "${BACKEND_DIR}/tmp/restart.txt"
    log "Passenger restart sinyali gönderildi"
}

show_status() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════${NC}"
    echo -e "${CYAN}  Bilge Yolcu Panel — Servis Durumu${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════${NC}"

    if command -v systemctl &>/dev/null; then
        echo -e "  Gunicorn:  $(sudo systemctl is-active bilgeyolcu-gunicorn 2>/dev/null || echo 'yok')"
        echo -e "  Celery:    $(sudo systemctl is-active bilgeyolcu-celery 2>/dev/null || echo 'yok')"
    fi

    if command -v redis-cli &>/dev/null; then
        echo -e "  Redis:     $(redis-cli ping 2>/dev/null || echo 'kapalı')"
    fi

    echo -e "  Panel:     https://bilgeyolcu.com/yonetim/"
    echo -e "  Health:    https://bilgeyolcu.com/yonetim/api/health"
    echo ""
}

# ══════════════════════════════════════════════════════════
# İLK KURULUM
# ══════════════════════════════════════════════════════════
deploy_init() {
    echo -e "${CYAN}"
    echo "  ╔═══════════════════════════════════════╗"
    echo "  ║   Bilge Yolcu — İLK KURULUM           ║"
    echo "  ╚═══════════════════════════════════════╝"
    echo -e "${NC}"

    check_prerequisites
    create_venv
    setup_directories
    setup_env
    deploy_frontend --force
    init_database
    create_admin
    install_services

    echo ""
    echo -e "${GREEN}"
    echo "  ╔═══════════════════════════════════════╗"
    echo "  ║   ✓ İLK KURULUM TAMAMLANDI            ║"
    echo "  ╚═══════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
    echo "  ŞİMDİ YAPMANIZ GEREKENLER:"
    echo ""
    echo "  1. .env dosyasını düzenleyin:"
    echo "     nano ${BACKEND_DIR}/.env"
    echo ""
    echo "  2. WHM'de mod_proxy aktif olduğunu doğrulayın:"
    echo "     WHM → Apache Configuration → Global → mod_proxy"
    echo ""
    echo "  3. Servisleri yeniden başlatın:"
    echo "     bash ${PROJECT_DIR}/deploy.sh --restart"
    echo ""

    show_status
}

# ══════════════════════════════════════════════════════════
# GÜNCELLEME
# ══════════════════════════════════════════════════════════
deploy_update() {
    echo -e "${CYAN}  ── Bilge Yolcu — Güncelleme ──${NC}"

    check_prerequisites

    # Git pull
    if [ -d "${PROJECT_DIR}/.git" ]; then
        info "Git pull..."
        cd "${PROJECT_DIR}"
        git pull origin main 2>&1 | head -5
    fi

    # Bağımlılıklar
    info "pip bağımlılıkları..."
    ${PIP} install -r "${BACKEND_DIR}/requirements.txt" -q

    # Frontend
    deploy_frontend

    # DB migrasyonları
    init_database

    # Servisleri yeniden başlat
    restart_services

    echo ""
    log "GÜNCELLEME TAMAMLANDI"
    show_status
}

# ══════════════════════════════════════════════════════════
# ANA AKIŞ
# ══════════════════════════════════════════════════════════
case "${1:-}" in
    --init)     deploy_init ;;
    --admin)    create_admin ;;
    --restart)  restart_services ;;
    --status)   show_status ;;
    --help|-h)
        echo "Kullanım: bash deploy.sh [SEÇENEK]"
        echo ""
        echo "  --init      İlk kurulum (venv, DB, admin, systemd)"
        echo "  --admin     Yeni admin kullanıcısı oluştur"
        echo "  --restart   Gunicorn + Celery yeniden başlat"
        echo "  --status    Servis durumlarını göster"
        echo "  (boş)       Güncelleme (git pull + install + restart)"
        echo ""
        ;;
    *)          deploy_update ;;
esac

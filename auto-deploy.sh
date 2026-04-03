#!/bin/bash
# ================================================================
#  Bilge Yolcu — Otomatik Deploy Script
#  Kullanım:
#    bash ~/bilge-panel/auto-deploy.sh           (normal deploy)
#    bash ~/bilge-panel/auto-deploy.sh --full    (pip install dahil)
# ================================================================

set -e

PROJECT_DIR="/home/bilgeyolcu/bilge-panel"
VENV_DIR="${PROJECT_DIR}/venv"
PUBLIC_HTML="/home/bilgeyolcu/public_html/yonetim"
LOG_FILE="/home/bilgeyolcu/logs/deploy.log"

# Renkli çıktı
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[DEPLOY]${NC} $1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}[UYARI]${NC} $1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WARN] $1" >> "$LOG_FILE"
}

error() {
    echo -e "${RED}[HATA]${NC} $1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $1" >> "$LOG_FILE"
}

# Log dizini oluştur
mkdir -p "$(dirname "$LOG_FILE")"

log "Deploy başlıyor..."

# ── 1. Git Pull ──────────────────────────────────────────────
cd "$PROJECT_DIR"

# Mevcut commit'i kaydet
OLD_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "initial")

log "Git pull yapılıyor..."
git pull origin main 2>&1 | tee -a "$LOG_FILE"

NEW_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "unknown")

if [ "$OLD_COMMIT" = "$NEW_COMMIT" ]; then
    log "Değişiklik yok — deploy atlandı."
    exit 0
fi

log "Güncelleme: ${OLD_COMMIT:0:7} → ${NEW_COMMIT:0:7}"

# ── 2. Bağımlılıkları Güncelle (--full ile) ──────────────────
if [[ "$1" == "--full" ]] || git diff --name-only "$OLD_COMMIT" "$NEW_COMMIT" | grep -q "requirements.txt"; then
    log "requirements.txt değişti — bağımlılıklar güncelleniyor..."
    "${VENV_DIR}/bin/pip" install -r "${PROJECT_DIR}/backend/requirements.txt" -q
    log "Bağımlılıklar güncellendi."
else
    log "requirements.txt değişmedi — pip install atlandı."
fi

# ── 3. Frontend Dosyalarını Kopyala ──────────────────────────
if git diff --name-only "$OLD_COMMIT" "$NEW_COMMIT" | grep -q "backend/public/yonetim/"; then
    log "Frontend dosyaları güncelleniyor..."
    mkdir -p "$PUBLIC_HTML"
    cp -r "${PROJECT_DIR}/backend/public/yonetim/"* "$PUBLIC_HTML/"
    
    # .htaccess'i de kopyala
    if [ -f "${PROJECT_DIR}/backend/.htaccess" ]; then
        cp "${PROJECT_DIR}/backend/.htaccess" "${PUBLIC_HTML}/.htaccess"
    fi
    
    log "Frontend dosyaları güncellendi."
else
    log "Frontend değişmedi — kopyalama atlandı."
fi

# ── 4. DB Migrate (varsa) ───────────────────────────────────
# İleride Alembic eklenirse burada çalıştırılacak
# "${VENV_DIR}/bin/python" -m flask db upgrade

# ── 5. Servisleri Yeniden Başlat ─────────────────────────────
log "Servisler yeniden başlatılıyor..."
sudo systemctl restart bilgeyolcu-gunicorn 2>&1 || warn "Gunicorn restart edilemedi"
sudo systemctl restart bilgeyolcu-celery 2>&1 || warn "Celery restart edilemedi"

# ── 6. Sağlık Kontrolü ──────────────────────────────────────
sleep 3
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" https://bilgeyolcu.com/yonetim/api/health)

if [ "$HEALTH" = "200" ]; then
    log "✅ Deploy başarılı! (HTTP $HEALTH)"
else
    error "❌ Sağlık kontrolü başarısız! (HTTP $HEALTH)"
    error "Loglara bakın: journalctl -u bilgeyolcu-gunicorn --no-pager -n 30"
    exit 1
fi

log "Deploy tamamlandı: ${NEW_COMMIT:0:7}"
echo ""
echo "═══════════════════════════════════════"
echo "  ✅ Deploy başarılı!"
echo "  Commit: ${NEW_COMMIT:0:7}"
echo "  Tarih:  $(date '+%Y-%m-%d %H:%M:%S')"
echo "═══════════════════════════════════════"

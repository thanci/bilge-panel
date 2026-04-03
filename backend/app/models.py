"""
app/models.py — SQLAlchemy ORM modelleri.

Tüm veritabanı tabloları bu dosyada tanımlanır:
  - AdminUser      : Yönetici kullanıcı hesapları
  - TokenBlocklist : Geçersiz kılınan JWT token'ları (logout)
  - ApiCostLog     : LLM API maliyet kayıtları (her çağrı için)
  - DailyBudget    : Günlük bütçe özeti ve Circuit Breaker durumu
  - TaskLog        : Celery görev durumu ve meta verileri
"""

import bcrypt
from datetime import datetime, timezone

from app.extensions import db


# ============================================================
# YÖNETİCİ KULLANICI
# ============================================================

class AdminUser(db.Model):
    """
    Kontrol paneline erişim yetkisi olan yönetici hesabı.
    Şifreler bcrypt ile hashlenir — düz metin asla saklanmaz.
    """
    __tablename__ = "admin_users"

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(64), unique=True, nullable=False, index=True)
    # bcrypt hash: $2b$12$... formatında, maksimum 60 karakter
    password_hash = db.Column(db.String(128), nullable=False)
    is_active     = db.Column(db.Boolean, default=True, nullable=False)
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_login_at = db.Column(db.DateTime, nullable=True)

    def set_password(self, plain_password: str) -> None:
        """
        Düz metin şifreyi bcrypt ile hashler ve kaydeder.
        Mevcut hash varsa üzerine yazar.
        """
        if not plain_password or len(plain_password) < 8:
            raise ValueError("Şifre en az 8 karakter olmalıdır.")
        # bcrypt, work_factor=12 — güçlü ve hesaplı
        hashed = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt(rounds=12))
        self.password_hash = hashed.decode("utf-8")

    def check_password(self, plain_password: str) -> bool:
        """
        Girilen şifreyi kayıtlı hash ile karşılaştırır.
        Döndürür: True (eşleşiyor) / False (eşleşmiyor)
        """
        try:
            return bcrypt.checkpw(
                plain_password.encode("utf-8"),
                self.password_hash.encode("utf-8"),
            )
        except Exception:
            # Hash bozuksa veya beklenmedik hata varsa False dön
            return False

    def to_dict(self) -> dict:
        """API yanıtı için güvenli sözlük — şifre hash'i dahil edilmez."""
        return {
            "id":            self.id,
            "username":      self.username,
            "is_active":     self.is_active,
            "created_at":    self.created_at.isoformat() if self.created_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }

    def __repr__(self) -> str:
        return f"<AdminUser {self.username}>"


# ============================================================
# JWT TOKEN BLOCKLIST (Logout için)
# ============================================================

class TokenBlocklist(db.Model):
    """
    Geçersiz kılınan JWT token'larının JTI (JWT ID) listesi.
    Kullanıcı logout yaptığında token JTI buraya eklenir.
    @jwt.token_in_blocklist_loader bu tabloyu sorgular.
    """
    __tablename__ = "token_blocklist"

    id         = db.Column(db.Integer, primary_key=True)
    # JWT'nin benzersiz kimliği (UUID formatında)
    jti        = db.Column(db.String(64), unique=True, nullable=False, index=True)
    token_type = db.Column(db.String(16), nullable=False)   # "access" veya "refresh"
    revoked_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return f"<BlockedToken {self.jti[:8]}... ({self.token_type})>"


# ============================================================
# API MALİYET KAYDI
# ============================================================

class ApiCostLog(db.Model):
    """
    Her LLM API çağrısının maliyet kaydı.
    Budget Guard, bu tabloyu okuyarak günlük harcamayı hesaplar.
    """
    __tablename__ = "api_cost_log"

    id            = db.Column(db.Integer, primary_key=True)
    # Hangi Celery görevi bu çağrıyı yaptı?
    task_id       = db.Column(db.String(64), nullable=False, index=True)
    # Kullanılan model: "gemini-2.5-flash", "claude-haiku-3-5", "gpt-4o-mini"
    model         = db.Column(db.String(64), nullable=False)
    prompt_tokens = db.Column(db.Integer, nullable=False, default=0)
    output_tokens = db.Column(db.Integer, nullable=False, default=0)
    # Gerçek maliyet: API yanıtından alınan token kullanımından hesaplanan
    cost_usd      = db.Column(db.Float, nullable=False, default=0.0)
    # Tahmini maliyet: Pre-flight check'te Tiktoken ile hesaplanan
    est_cost_usd  = db.Column(db.Float, nullable=True)
    # "success", "blocked_by_budget", "rate_limited", "failed"
    status        = db.Column(db.String(32), nullable=False, default="success")
    created_at    = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True,   # Tarih bazlı sorgular için index
    )

    def to_dict(self) -> dict:
        return {
            "id":            self.id,
            "task_id":       self.task_id,
            "model":         self.model,
            "prompt_tokens": self.prompt_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd":      round(self.cost_usd, 6),
            "est_cost_usd":  round(self.est_cost_usd, 6) if self.est_cost_usd else None,
            "status":        self.status,
            "created_at":    self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<ApiCostLog task={self.task_id[:8]} model={self.model} ${self.cost_usd:.4f}>"


# ============================================================
# GÜNLÜK BÜTÇE VE CIRCUIT BREAKER DURUMU
# ============================================================

class DailyBudget(db.Model):
    """
    Günlük bütçe harcama özeti ve Circuit Breaker durum takibi.
    Her gün için bir satır oluşturulur (tarih primary key).
    Gece yarısı Celery Beat ile sıfırlanır.
    """
    __tablename__ = "daily_budget"

    # "2025-04-03" formatında — birincil anahtar
    date          = db.Column(db.String(10), primary_key=True)
    # Bugüne kadar harcanan toplam (USD)
    spent_usd     = db.Column(db.Float, nullable=False, default=0.0)
    # .env'deki DAILY_API_BUDGET değeri (snapshot olarak saklanır)
    limit_usd     = db.Column(db.Float, nullable=False)
    # Circuit Breaker durumu:
    #   CLOSED    = Normal çalışma, API çağrılarına izin var
    #   OPEN      = Bütçe doldu, TÜM API çağrıları bloke
    #   HALF_OPEN = Gece yarısı reset sonrası deneme aşaması
    breaker_state = db.Column(db.String(16), nullable=False, default="CLOSED")
    updated_at    = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    @property
    def remaining_usd(self) -> float:
        """Kalan bütçe miktarı (USD)."""
        return max(0.0, self.limit_usd - self.spent_usd)

    @property
    def usage_percentage(self) -> float:
        """Kullanım yüzdesi (0.0 - 1.0 arasında)."""
        if self.limit_usd <= 0:
            return 1.0
        return min(1.0, self.spent_usd / self.limit_usd)

    def to_dict(self) -> dict:
        return {
            "date":            self.date,
            "spent_usd":       round(self.spent_usd, 4),
            "limit_usd":       round(self.limit_usd, 4),
            "remaining_usd":   round(self.remaining_usd, 4),
            "usage_pct":       round(self.usage_percentage * 100, 1),
            "breaker_state":   self.breaker_state,
            "updated_at":      self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return (
            f"<DailyBudget {self.date} "
            f"${self.spent_usd:.4f}/${self.limit_usd:.2f} [{self.breaker_state}]>"
        )


# ============================================================
# GÖREV KAYDI
# ============================================================

class TaskLog(db.Model):
    """
    Celery görevlerinin durum ve meta veri kayıtları.
    Dashboard'daki "Görev Kuyruğu" bileşeni bu tabloyu okur.
    """
    __tablename__ = "task_log"

    # Celery'nin UUID task ID'si
    task_id     = db.Column(db.String(64), primary_key=True)
    # "youtube_summary", "ai_article", "xf_sync", "xf_upgrade" vb.
    task_type   = db.Column(db.String(64), nullable=False, index=True)
    # "QUEUED", "RUNNING", "SUCCESS", "FAILED", "REVOKED"
    status      = db.Column(db.String(16), nullable=False, default="QUEUED", index=True)
    # Girdi parametreleri (JSON string)
    payload     = db.Column(db.Text, nullable=True)
    # Çıktı sonucu (JSON string — XF thread URL, makale ID'si vb.)
    result      = db.Column(db.Text, nullable=True)
    # Hata durumunda hata mesajı
    error_msg   = db.Column(db.Text, nullable=True)
    # Hangi LLM modeli kullanıldı?
    model_used  = db.Column(db.String(64), nullable=True)
    # Bu görevin toplam maliyeti (USD)
    cost_usd    = db.Column(db.Float, nullable=True)
    started_at  = db.Column(db.DateTime, nullable=True)
    finished_at = db.Column(db.DateTime, nullable=True)
    created_at  = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    @property
    def duration_seconds(self) -> float | None:
        """Görev süresi (saniye). Tamamlanmamışsa None döner."""
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None

    def to_dict(self, include_content: bool = False) -> dict:
        import json as _json

        base = {
            "task_id":          self.task_id,
            "task_type":        self.task_type,
            "status":           self.status,
            "model_used":       self.model_used,
            "cost_usd":         round(self.cost_usd, 4) if self.cost_usd else None,
            "duration_seconds": self.duration_seconds,
            "error_msg":        self.error_msg,
            "created_at":       self.created_at.isoformat() if self.created_at else None,
            "started_at":       self.started_at.isoformat() if self.started_at else None,
            "finished_at":      self.finished_at.isoformat() if self.finished_at else None,
        }

        # Detay istenmişse payload ve result'ı da ekle
        if include_content:
            try:
                base["payload"] = _json.loads(self.payload) if self.payload else None
            except (ValueError, TypeError):
                base["payload"] = self.payload
            try:
                base["result"] = _json.loads(self.result) if self.result else None
            except (ValueError, TypeError):
                base["result"] = self.result
        else:
            # Liste görünümünde özet bilgi
            base["has_result"] = bool(self.result)
            base["has_error"]  = bool(self.error_msg)

        return base

    def __repr__(self) -> str:
        return f"<TaskLog {self.task_id[:8]}... [{self.status}] {self.task_type}>"


# ============================================================
# YAYIN TASLAK KUYRUĞU
# ============================================================

class PublishDraft(db.Model):
    """
    Editoryal yayın kuyruğu. Tamamlanmış görevlerden oluşturulan
    içerikler burada düzenlenip XenForo'ya yayınlanır.

    Durum Akışı:
      DRAFT → (düzenleme) → PUBLISHED
      DRAFT → (silme)     → kayıt silinir
    """
    __tablename__ = "publish_draft"

    id            = db.Column(db.Integer, primary_key=True)
    # Kaynak görev (opsiyonel — bağımsız taslak da oluşturulabilir)
    task_id       = db.Column(db.String(64), db.ForeignKey("task_log.task_id", ondelete="SET NULL"), nullable=True, index=True)
    # Makale başlığı
    title         = db.Column(db.String(255), nullable=False)
    # BB-Code formatında içerik
    content       = db.Column(db.Text, nullable=False)
    # Kaynak görev türü: youtube_summary, ai_article
    source_type   = db.Column(db.String(64), nullable=True)
    # Kategori / anahtar kelimeler
    category      = db.Column(db.String(128), nullable=True)
    tags          = db.Column(db.Text, nullable=True)    # JSON array string
    # XenForo hedef forum node ID'si
    xf_node_id    = db.Column(db.Integer, nullable=True)
    # Durum: DRAFT, PUBLISHED
    status        = db.Column(db.String(16), nullable=False, default="DRAFT", index=True)
    # Yayınlanmış ise XenForo bilgileri
    xf_thread_id  = db.Column(db.Integer, nullable=True)
    xf_thread_url = db.Column(db.String(512), nullable=True)
    # Zaman damgaları
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                              onupdate=lambda: datetime.now(timezone.utc))
    published_at  = db.Column(db.DateTime, nullable=True)

    def to_dict(self) -> dict:
        import json as _json
        try:
            tags_list = _json.loads(self.tags) if self.tags else []
        except (ValueError, TypeError):
            tags_list = []

        return {
            "id":             self.id,
            "task_id":        self.task_id,
            "title":          self.title,
            "content":        self.content,
            "source_type":    self.source_type,
            "category":       self.category,
            "tags":           tags_list,
            "xf_node_id":     self.xf_node_id,
            "status":         self.status,
            "xf_thread_id":   self.xf_thread_id,
            "xf_thread_url":  self.xf_thread_url,
            "created_at":     self.created_at.isoformat() if self.created_at else None,
            "updated_at":     self.updated_at.isoformat() if self.updated_at else None,
            "published_at":   self.published_at.isoformat() if self.published_at else None,
        }

    def __repr__(self) -> str:
        return f"<PublishDraft #{self.id} [{self.status}] '{self.title[:30]}'>"

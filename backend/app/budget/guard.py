"""
app/budget/guard.py — BudgetGuard: Circuit Breaker ve Pre-flight Check Motoru.

Bu modül sistemin en kritik güvenlik katmanıdır.
Hiçbir LLM API çağrısı bu modülden geçmeden GERÇEKLEŞEMEZ.

Tasarım İlkeleri:
  1. FAIL CLOSED: Guard'ın kendisi çökerse API çağrısı REDDEDİLİR.
  2. ATOMİK YAZMA: Bütçe güncelleme işlemleri SQLite transaction'ı içinde yapılır.
  3. HIZLI OKUMA: Circuit breaker durumu 30 saniyelik bir bellek cache'inde tutulur.
  4. GECİKMESİZ BİLDİRİM: Bütçe eşikleri aşıldığında Telegram mesajı gönderilir.

Circuit Breaker Durumları:
  CLOSED    → Normal çalışma. API çağrılarına izin verilir.
  OPEN      → Bütçe doldu. TÜM API çağrıları HARİÇ kalan reddedilir.
  HALF_OPEN → Gece yarısı reset sonrası. Yeni gün başladı, CLOSED'a geçer.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AŞAMA 3 — CELERY ENTEGRASYON NOTU (Kodlamaya başlamadan oku):

  Celery task'ları BudgetGuard'ı iki şekilde kullanabilir:

  YÖNTEM A — @budget_guard_task Decorator (ÖNERİLEN):
  ─────────────────────────────────────────────────────
    @celery.task(bind=True, max_retries=3)
    @budget_guard_task(model_key="PRIMARY_MODEL", token_estimate_fn=lambda payload: ...)
    def youtube_summary_task(self, payload):
        # Decorator pre_flight_check'i otomatik çağırır,
        # BudgetExceededError veya CircuitBreakerOpenError durumunda task'ı FAILED yapar,
        # Başarı sonrası record_actual_cost'u otomatik çağırır.
        result = call_llm(payload["text"])
        return result

  YÖNTEM B — Manuel Çağrı (karmaşık multi-step task'lar için):
  ─────────────────────────────────────────────────────────────
    @celery.task(bind=True, max_retries=3)
    def ai_article_task(self, payload):
        task_id = self.request.id
        try:
            # ADIM 1: Pre-flight check (API çağrısından ÖNCE)
            token_count = estimate_token_count(payload["prompt"])
            BudgetGuard.pre_flight_check(
                token_count=token_count,
                model=current_app.config["PRIMARY_MODEL"],
                task_id=task_id,
            )
            # ADIM 2: Actual API call
            response = call_llm(payload["prompt"])
            # ADIM 3: Gerçek maliyeti kaydet
            BudgetGuard.record_actual_cost(
                task_id=task_id,
                model=current_app.config["PRIMARY_MODEL"],
                prompt_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.output_tokens,
            )
            return response.content
        except (BudgetExceededError, CircuitBreakerOpenError):
            raise  # RETRY YAPMA — para harcanmasını önle
        except Exception as exc:
            raise self.retry(exc=exc, countdown=2 ** self.request.retries)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
import threading
import time
from datetime import date, datetime, timezone
from typing import Optional

from flask import current_app

from app.extensions import db
from app.models import ApiCostLog, DailyBudget
from app.budget.exceptions import (
    BudgetGuardError,
    BudgetExceededError,
    CircuitBreakerOpenError,
    InsufficientBudgetError,
)
from app.budget.pricing import (
    calculate_estimated_cost,
    calculate_actual_cost,
    estimate_token_count,
)

logger = logging.getLogger(__name__)

# ============================================================
# BELLEK İÇİ CACHE — SQLite'ı her istekte sorgulamayı önler
# ============================================================

# Cache yapısı: {"state": "CLOSED", "spent": 1.24, "limit": 2.00, "ts": <unix_time>}
_budget_cache: dict = {}
_cache_lock   = threading.Lock()   # Thread-safe cache erişimi
_CACHE_TTL    = 30                 # Saniye — 30 saniyeliK cache geçerlilik süresi


def _is_cache_valid() -> bool:
    """Cache'in hâlâ geçerli olup olmadığını kontrol eder."""
    if not _budget_cache:
        return False
    return (time.monotonic() - _budget_cache.get("ts", 0)) < _CACHE_TTL


def _invalidate_cache() -> None:
    """Cache'i geçersiz kılar — bütçe yazma işlemlerinden sonra çağrılır."""
    with _cache_lock:
        _budget_cache.clear()


def _update_cache(state: str, spent: float, limit: float) -> None:
    """Cache'i güncel değerlerle doldurur."""
    with _cache_lock:
        _budget_cache["state"] = state
        _budget_cache["spent"] = spent
        _budget_cache["limit"] = limit
        _budget_cache["ts"]    = time.monotonic()


# ============================================================
# YARDIMCI: Bugünkü DailyBudget Satırını Getir / Oluştur
# ============================================================

def _get_or_create_today() -> DailyBudget:
    """
    Bugünkü tarih için DailyBudget satırını döndürür.
    Satır yoksa (yeni gün) oluşturur ve commit eder.
    Bu fonksiyon her zaman aktif bir db.session içinde çağrılmalıdır.
    """
    today_str = date.today().isoformat()   # "2025-04-03"

    daily = DailyBudget.query.filter_by(date=today_str).first()
    if daily is None:
        # Limit değerini .env'den al — her zaman güncel config kullan
        try:
            limit = float(current_app.config.get("DAILY_API_BUDGET", 2.00))
        except (TypeError, ValueError):
            limit = 2.00
            logger.warning("[BUDGET] DAILY_API_BUDGET okunamadı, 2.00$ kullanılıyor.")

        daily = DailyBudget(
            date          = today_str,
            spent_usd     = 0.0,
            limit_usd     = limit,
            breaker_state = "CLOSED",
        )
        db.session.add(daily)
        db.session.flush()   # ID al, henüz commit etme

    return daily


# ============================================================
# ANA SINIF: BudgetGuard
# ============================================================

class BudgetGuard:
    """
    Tüm LLM API çağrılarının geçmek zorunda olduğu güvenlik kapısı.

    Doğru kullanım sırası:
        1. pre_flight_check() → API çağrısına izin var mı?
        2. [LLM API çağrısı]
        3. record_actual_cost() → Gerçek maliyeti kaydet

    Bu sınıfın statik metotları, Flask uygulama bağlamı (app context)
    aktif olduğunda çağrılabilir — Celery task'larında push_context() gerekir.
    """

    # Circuit Breaker durumları — string sabitler
    STATE_CLOSED    = "CLOSED"
    STATE_OPEN      = "OPEN"
    STATE_HALF_OPEN = "HALF_OPEN"

    # ──────────────────────────────────────────────────────────
    # ADIM 1: PRE-FLIGHT CHECK
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def pre_flight_check(
        token_count: int,
        model: str,
        task_id: str,
        output_token_estimate: Optional[int] = None,
    ) -> float:
        """
        LLM API çağrısından ÖNCE çağrılması ZORUNLU bütçe kontrolü.

        İşlem sırası:
          1. Cache'i kontrol et — Circuit Breaker OPEN mi?
          2. Tahmini maliyeti hesapla
          3. Günlük bütçeye eklediğinde limiti aşıyor mu?
          4. Bütçe yeterli → ApiCostLog'a "pre_flight" kaydı yaz
          5. Bütçe yetersiz → Circuit Breaker'ı aç, Telegram bildir, hata fırlat

        FAIL CLOSED: Beklenmedik hatada API çağrısına izin VERME.

        Args:
            token_count:           Giriş metninin tahmini token sayısı
            model:                 Kullanılacak LLM modeli
            task_id:               Celery task UUID'si (loglama için)
            output_token_estimate: Beklenen çıktı token sayısı (None = otomatik tahmin)

        Returns:
            Tahmini maliyet (USD) — başarılı kontrol durumunda

        Raises:
            CircuitBreakerOpenError:  Breaker zaten OPEN konumunda
            InsufficientBudgetError:  Bu görev için yeterli bütçe yok
            BudgetGuardError:         Guard'ın kendisi çöktü (fail-closed)
        """
        try:
            # --- Hızlı cache kontrolü (SQLite'a gitmeden) ---
            with _cache_lock:
                if _is_cache_valid():
                    cached_state = _budget_cache.get("state", BudgetGuard.STATE_CLOSED)
                    if cached_state == BudgetGuard.STATE_OPEN:
                        raise CircuitBreakerOpenError(
                            "Circuit Breaker OPEN: Günlük API bütçesi doldu. "
                            "Gece yarısı otomatik olarak sıfırlanacak."
                        )

            # --- Tahmini maliyeti hesapla ---
            est_cost = calculate_estimated_cost(
                token_count=token_count,
                model=model,
                output_token_estimate=output_token_estimate,
            )

            # --- Veritabanı: ATOMİK kontrol ve loglama ---
            try:
                # Savepoint: Hata olursa sadece bu bloğu geri al
                with db.session.begin_nested():
                    daily = _get_or_create_today()

                    # Circuit Breaker OPEN mu? (DB'den kesin kontrol)
                    if daily.breaker_state == BudgetGuard.STATE_OPEN:
                        _update_cache(
                            BudgetGuard.STATE_OPEN,
                            daily.spent_usd,
                            daily.limit_usd
                        )
                        raise CircuitBreakerOpenError(
                            f"Circuit Breaker OPEN: {daily.spent_usd:.4f}$ / "
                            f"{daily.limit_usd:.2f}$ bütçe kullanıldı."
                        )

                    # Tahmini maliyet + mevcut harcama limiti aşar mı?
                    if daily.spent_usd + est_cost >= daily.limit_usd:
                        # Bütçe doldu → Circuit Breaker'ı aç
                        BudgetGuard._open_breaker(
                            daily=daily,
                            reason=f"Pre-flight: {daily.spent_usd:.4f}$ harcandı, "
                                   f"tahmini {est_cost:.4f}$ daha gerekiyor "
                                   f"(limit: {daily.limit_usd:.2f}$)",
                        )
                        raise InsufficientBudgetError(
                            message=f"Bütçe yetersiz: {est_cost:.4f}$ gerekiyor, "
                                    f"{daily.remaining_usd:.4f}$ kaldı.",
                            est_cost=est_cost,
                            remaining=daily.remaining_usd,
                        )

                    # ✅ Bütçe yeterli — Pre-flight log kaydı oluştur
                    pre_flight_log = ApiCostLog(
                        task_id       = task_id,
                        model         = model,
                        prompt_tokens = token_count,
                        output_tokens = output_token_estimate or 0,
                        cost_usd      = 0.0,       # Henüz gerçek maliyet yok
                        est_cost_usd  = est_cost,
                        status        = "pre_flight",
                    )
                    db.session.add(pre_flight_log)

                    # Cache'i güncelle
                    _update_cache(
                        daily.breaker_state,
                        daily.spent_usd,
                        daily.limit_usd,
                    )

                # Savepoint başarıyla kapandı → commit
                db.session.commit()

            except (CircuitBreakerOpenError, InsufficientBudgetError, BudgetExceededError):
                raise  # Bütçe hatalarını yukarıya ilet — yakalama
            except Exception as db_err:
                db.session.rollback()
                logger.error(
                    f"[BUDGET] Pre-flight DB hatası: {db_err}",
                    exc_info=True
                )
                # FAIL CLOSED: DB hatası → API çağrısını engelle
                raise BudgetGuardError(
                    f"Budget Guard veritabanı hatası: {db_err}. "
                    "Güvenli taraf: API isteği reddedildi."
                )

            logger.info(
                f"[BUDGET] ✅ Pre-flight onaylandı | task={task_id[:8]} "
                f"model={model} est_cost=${est_cost:.6f}"
            )
            return est_cost

        except (CircuitBreakerOpenError, InsufficientBudgetError, BudgetGuardError):
            raise  # Bütçe/guard hatalarını yukarıya ilet

        except Exception as unexpected_err:
            # FAIL CLOSED: Beklenmedik her hata API isteğini engeller
            logger.critical(
                f"[BUDGET] KRITIK: Beklenmedik pre-flight hatası: {unexpected_err}",
                exc_info=True,
            )
            raise BudgetGuardError(
                f"Budget Guard beklenmedik hata: {unexpected_err}. "
                "FAIL CLOSED: API isteği reddedildi."
            )

    # ──────────────────────────────────────────────────────────
    # ADIM 2: GERÇEK MALİYETİ KAYDET
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def record_actual_cost(
        task_id: str,
        model: str,
        prompt_tokens: int,
        output_tokens: int,
        status: str = "success",
    ) -> float:
        """
        API çağrısı tamamlandıktan SONRA çağrılır.
        API yanıtından gelen gerçek token sayılarıyla maliyeti hesaplar
        ve günlük harcamaya ekler.

        Args:
            task_id:       Celery task UUID'si
            model:         Kullanılan LLM modeli
            prompt_tokens: API'nin raporladığı giriş token sayısı
            output_tokens: API'nin raporladığı çıktı token sayısı
            status:        "success", "rate_limited", "failed" vb.

        Returns:
            Gerçek maliyet (USD)

        Önemli:
            Bu metot kesinlikle exception fırlatmamalıdır — API başarılı oldu,
            sadece muhasebe yapıyoruz. Hata olursa logla ve devam et.
        """
        actual_cost = 0.0
        try:
            actual_cost = calculate_actual_cost(
                prompt_tokens=prompt_tokens,
                output_tokens=output_tokens,
                model=model,
            )

            with db.session.begin_nested():
                daily = _get_or_create_today()

                # Günlük harcamayı artır
                daily.spent_usd   += actual_cost
                daily.updated_at   = datetime.now(timezone.utc)

                # Pre-flight kaydını güncelle (varsa)
                pre_log = ApiCostLog.query.filter_by(
                    task_id=task_id,
                    status="pre_flight",
                ).order_by(ApiCostLog.created_at.desc()).first()

                if pre_log:
                    # Mevcut pre-flight kaydını gerçek değerlerle güncelle
                    pre_log.prompt_tokens = prompt_tokens
                    pre_log.output_tokens = output_tokens
                    pre_log.cost_usd      = actual_cost
                    pre_log.status        = status
                else:
                    # Pre-flight kaydı yoksa (olmamalı ama) yeni kayıt oluştur
                    logger.warning(
                        f"[BUDGET] task={task_id[:8]} için pre_flight kaydı bulunamadı. "
                        "Yeni kayıt oluşturuluyor."
                    )
                    new_log = ApiCostLog(
                        task_id       = task_id,
                        model         = model,
                        prompt_tokens = prompt_tokens,
                        output_tokens = output_tokens,
                        cost_usd      = actual_cost,
                        status        = status,
                    )
                    db.session.add(new_log)

                # Harcama limiti aştı mı? (Gerçek maliyet sonrası kontrol)
                if daily.spent_usd >= daily.limit_usd:
                    BudgetGuard._open_breaker(
                        daily=daily,
                        reason=f"Gerçek maliyet sonrası limit aşıldı: "
                               f"{daily.spent_usd:.4f}$ / {daily.limit_usd:.2f}$",
                    )
                else:
                    # Uyarı eşiği kontrol: %80 geçildi mi?
                    try:
                        warning_threshold = float(
                            current_app.config.get("BUDGET_WARNING_THRESHOLD", 0.80)
                        )
                    except (TypeError, ValueError):
                        warning_threshold = 0.80

                    if daily.usage_percentage >= warning_threshold:
                        BudgetGuard._send_warning_notification(daily)

                # Cache'i geçersiz kıl — güncel değerler DB'de
                _invalidate_cache()

            db.session.commit()

            logger.info(
                f"[BUDGET] 💰 Maliyet kaydedildi | task={task_id[:8]} "
                f"model={model} cost=${actual_cost:.6f} "
                f"| Bugün toplam: ${daily.spent_usd:.4f}"
            )
            return actual_cost

        except Exception as e:
            # NOT: Bu metot exception fırlatmaz — API başarılı oldu, loglama sorununu
            # işlem akışını durdurmak için kullanmıyoruz.
            db.session.rollback()
            logger.error(
                f"[BUDGET] Maliyet kaydı hatası (veri kaybı riski!): {e}",
                exc_info=True,
            )
            return actual_cost  # En azından hesaplanan değeri döndür

    # ──────────────────────────────────────────────────────────
    # DURUM SORGULAMA
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def get_status() -> dict:
        """
        Anlık bütçe durumunu döndürür.
        Dashboard /api/budget/status endpoint'i tarafından çağrılır.

        Returns:
            {
                "date": "2025-04-03",
                "spent_usd": 1.24,
                "limit_usd": 2.00,
                "remaining_usd": 0.76,
                "usage_pct": 62.0,
                "breaker_state": "CLOSED",
                "is_blocked": false
            }
        """
        try:
            daily = _get_or_create_today()
            result = daily.to_dict()
            result["is_blocked"] = (daily.breaker_state == BudgetGuard.STATE_OPEN)
            db.session.commit()  # Yeni gün oluştuysa commit et
            return result
        except Exception as e:
            db.session.rollback()
            logger.error(f"[BUDGET] get_status hatası: {e}", exc_info=True)
            # Hata durumunda güvenli varsayılan — is_blocked=True (fail-closed)
            return {
                "date":          date.today().isoformat(),
                "spent_usd":     0.0,
                "limit_usd":     0.0,
                "remaining_usd": 0.0,
                "usage_pct":     100.0,
                "breaker_state": "UNKNOWN",
                "is_blocked":    True,  # Fail-closed
                "error":         str(e),
            }

    # ──────────────────────────────────────────────────────────
    # GECE YARISI RESET (Celery Beat tarafından çağrılır)
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def reset_daily() -> dict:
        """
        Gece yarısı çalışan Celery Beat görevi tarafından çağrılır.
        Yeni gün başladığında circuit breaker'ı sıfırlar.
        
        Aşama 3'te bu fonksiyon şu şekilde Celery'ye bağlanacak:
            @celery.task
            @celery_app.on_after_configure.connect
            def setup_periodic_tasks(sender, **kwargs):
                sender.add_periodic_task(
                    crontab(hour=0, minute=1),   # Gece 00:01
                    reset_daily_budget_task.s(),
                )
        """
        try:
            today_str     = date.today().isoformat()
            yesterday_str = None  # Önceki gün kaydı zaten var

            # Bugünkü kaydı bul (varsa)
            daily = DailyBudget.query.filter_by(date=today_str).first()

            if daily and daily.breaker_state in (
                BudgetGuard.STATE_OPEN,
                BudgetGuard.STATE_HALF_OPEN,
            ):
                daily.breaker_state = BudgetGuard.STATE_CLOSED
                daily.updated_at    = datetime.now(timezone.utc)
                db.session.commit()
                _invalidate_cache()

                logger.info(f"[BUDGET] 🔄 Gece yarısı reset: {today_str} CLOSED'a döndü.")

                # Telegram'a reset bildirimi gönder
                try:
                    from app.notifications.telegram import send_telegram_message
                    send_telegram_message(
                        f"🔄 *[RESET]* Günlük API bütçesi sıfırlandı.\n"
                        f"📅 Yeni gün: {today_str}\n"
                        f"💰 Limit: ${daily.limit_usd:.2f}"
                    )
                except Exception as notify_err:
                    logger.warning(f"[BUDGET] Reset Telegram bildirimi gönderilemedi: {notify_err}")

                return {"status": "reset", "date": today_str}

            return {"status": "no_action_needed", "date": today_str}

        except Exception as e:
            db.session.rollback()
            logger.error(f"[BUDGET] Gece yarısı reset hatası: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    # ──────────────────────────────────────────────────────────
    # MANUEL RESET (Dashboard'dan acil açma)
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def manual_reset(admin_username: str) -> dict:
        """
        Admin tarafından manuel olarak circuit breaker'ı sıfırlar.
        /api/budget/reset endpoint'i aracılığıyla çağrılır.
        """
        try:
            daily = _get_or_create_today()
            old_state              = daily.breaker_state
            daily.breaker_state   = BudgetGuard.STATE_CLOSED
            daily.updated_at      = datetime.now(timezone.utc)
            db.session.commit()
            _invalidate_cache()

            logger.warning(
                f"[BUDGET] ⚡ Manuel reset: {old_state} → CLOSED | admin={admin_username}"
            )

            try:
                from app.notifications.telegram import send_telegram_message
                send_telegram_message(
                    f"⚡ *[MANUEL RESET]* Circuit Breaker admin tarafından sıfırlandı.\n"
                    f"👤 Admin: {admin_username}\n"
                    f"💸 Mevcut harcama: ${daily.spent_usd:.4f} / ${daily.limit_usd:.2f}"
                )
            except Exception:
                pass

            return {
                "status":    "reset",
                "old_state": old_state,
                "new_state": BudgetGuard.STATE_CLOSED,
            }
        except Exception as e:
            db.session.rollback()
            logger.error(f"[BUDGET] Manuel reset hatası: {e}", exc_info=True)
            raise BudgetGuardError(f"Manuel reset başarısız: {e}")

    # ──────────────────────────────────────────────────────────
    # ÖZEL YARDIMCI METOTLAR
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def _open_breaker(daily: DailyBudget, reason: str) -> None:
        """
        Circuit Breaker'ı OPEN konumuna geçirir.
        Bu metot mutlaka aktif bir db.session içinde çağrılmalıdır.
        commit() çağıran kod bloğuna bırakılmıştır.
        """
        if daily.breaker_state == BudgetGuard.STATE_OPEN:
            return   # Zaten açık, tekrar açmaya gerek yok

        daily.breaker_state = BudgetGuard.STATE_OPEN
        daily.updated_at    = datetime.now(timezone.utc)
        db.session.flush()   # DB'ye yaz ama commit etme (dışarıda yapılacak)

        # Cache'i anında geçersiz kıl
        _update_cache(BudgetGuard.STATE_OPEN, daily.spent_usd, daily.limit_usd)

        logger.critical(
            f"[BUDGET] 🚨 CIRCUIT BREAKER AÇILDI! "
            f"spent=${daily.spent_usd:.4f} limit=${daily.limit_usd:.2f} | {reason}"
        )

        # Telegram bildirimi — ağ hatası ana akışı durdurmamalı
        try:
            from app.notifications.telegram import send_telegram_message
            send_telegram_message(
                f"🚨 *[ACİL — CIRCUIT BREAKER AÇILDI]*\n\n"
                f"📅 Tarih: {daily.date}\n"
                f"💸 Harcanan: ${daily.spent_usd:.4f}\n"
                f"💰 Limit: ${daily.limit_usd:.2f}\n"
                f"❌ Durum: TÜM API ÇAĞRILARI BLOKE\n\n"
                f"ℹ️ Sebep: {reason}\n\n"
                f"🔄 Gece yarısı otomatik sıfırlanır veya "
                f"panelden manuel olarak açabilirsiniz."
            )
        except Exception as notify_err:
            logger.warning(f"[BUDGET] Circuit breaker Telegram bildirimi gönderilemedi: {notify_err}")

    @staticmethod
    def _send_warning_notification(daily: DailyBudget) -> None:
        """
        Bütçe uyarı eşiğine ulaşıldığında (%80 varsayılan) Telegram'a bildirim gönderir.
        Günde en fazla 1 kez bildirim göndermek için basit bir flag kullanır.
        """
        # Basit tekrar bildirim önleme: session'da flag tut
        flag_key = f"_warned_{daily.date}"
        if getattr(daily, "_warning_sent", False):
            return
        # DailyBudget nesnesine geçici flag ekle (DB'ye yazılmaz)
        object.__setattr__(daily, "_warning_sent", True)

        try:
            from app.notifications.telegram import send_telegram_message
            send_telegram_message(
                f"⚠️ *[UYARI]* Günlük API bütçesinin "
                f"%{daily.usage_percentage * 100:.0f}'i kullanıldı!\n\n"
                f"📅 Tarih: {daily.date}\n"
                f"💸 Harcanan: ${daily.spent_usd:.4f}\n"
                f"💰 Limit: ${daily.limit_usd:.2f}\n"
                f"🟡 Kalan: ${daily.remaining_usd:.4f}"
            )
        except Exception as e:
            logger.warning(f"[BUDGET] Uyarı Telegram bildirimi gönderilemedi: {e}")


# ============================================================
# CELERY DECORATOR — Aşama 3'te aktif olacak
# ============================================================

def budget_guard_task(model_key: str = "PRIMARY_MODEL", token_estimate_fn=None):
    """
    Celery task'larını otomatik olarak BudgetGuard'a bağlayan decorator.

    Bu decorator Aşama 3'te Celery task'larına uygulanacaktır.
    Şu an PLACEHOLDER — Celery entegrasyonu hazır olduğunda aktif edilecek.

    Kullanım (Aşama 3):
        @celery.task(bind=True, max_retries=3)
        @budget_guard_task(
            model_key="PRIMARY_MODEL",
            token_estimate_fn=lambda payload: estimate_token_count(payload.get("text", ""))
        )
        def youtube_summary_task(self, payload):
            return call_llm(payload["text"])

    Parametreler:
        model_key:           Config anahtarı (örn: "PRIMARY_MODEL")
        token_estimate_fn:   payload'dan token sayısını tahmin eden fonksiyon
    """
    import functools

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(self, *args, **kwargs):
            task_id = self.request.id

            # Aşama 3'te aktif olacak kod buraya gelecek:
            # try:
            #     payload     = args[0] if args else kwargs
            #     token_count = token_estimate_fn(payload) if token_estimate_fn else 1000
            #     model       = current_app.config.get(model_key, "gemini-2.5-flash")
            #     BudgetGuard.pre_flight_check(token_count, model, task_id)
            # except (BudgetExceededError, CircuitBreakerOpenError):
            #     raise  # Celery bu task'ı FAILED yapacak, RETRY olmayacak

            return fn(self, *args, **kwargs)

        return wrapper
    return decorator

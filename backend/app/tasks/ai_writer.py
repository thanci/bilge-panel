"""
app/tasks/ai_writer.py — GÖREV B: Otonom Makale Yazarı.

Bu görev, verilen parametrelere göre tamamen özgün bir makale üretir.
YouTube dönüştürücüden farkı: harici veri çekme adımı yoktur.
Prompt mühendisliği ve BudgetGuard entegrasyonu kritik noktadır.

Desteklenen Ton'lar:
  felsefi  — Spekülatif, soru soran üslup
  bilimsel — Kanıt odaklı, akademik
  anlatı   — Hikâye örgüsü kuran, edebi
  seo      — Arama motoru odaklı, yapılandırılmış

Uzunluk Hedefleri:
  kısa  — ~500 kelime → max_tokens=800
  orta  — ~900 kelime → max_tokens=1500
  uzun  — ~1500 kelime → max_tokens=2500
"""

import logging

from flask import current_app

from app.tasks.celery_app import celery
from app.tasks.helpers import update_task_status
from app.budget.guard import BudgetGuard
from app.budget.exceptions import (
    BudgetExceededError,
    CircuitBreakerOpenError,
    BudgetGuardError,
)
from app.budget.pricing import estimate_token_count
from app.llm.client import complete_with_fallback, AllModelsFailedError, LLMContentFilterError
from app.llm.prompts import AI_WRITER_SYSTEM, build_article_prompt, parse_meta_block
from app.notifications.telegram import notify_task_success, notify_task_failed

logger = logging.getLogger(__name__)


# Uzunluk → max_tokens eşlem tablosu
_LENGTH_TO_MAX_TOKENS = {
    "kısa": 800,
    "orta": 1500,
    "uzun": 2500,
}

# Geçerli ton değerleri
_VALID_TONES = {"felsefi", "bilimsel", "anlatı", "seo"}


# ============================================================
# ANA GÖREV
# ============================================================

@celery.task(
    name        = "app.tasks.ai_writer.ai_article_task",
    bind        = True,
    max_retries = 3,
    rate_limit  = "8/m",    # Dakikada maksimum 8 makale görevi
)
def ai_article_task(self, payload: dict) -> dict:
    """
    Otonom makale yazma görevi.

    payload formatı:
        {
            "topic":       "Stoicism ve modern kaygı yönetimi",  # ZORUNLU
            "tone":        "felsefi",   # opsiyonel, varsayılan "felsefi"
            "length":      "orta",      # opsiyonel, varsayılan "orta"
            "category":    "Felsefe",   # opsiyonel, XenForo kategori adı
            "keywords":    "stoacılık, epiktetos, kaygı, felsefe",  # opsiyonel
            "extra_notes": "Marcus Aurelius'a odaklan",  # opsiyonel
            "temperature": 0.75,        # opsiyonel (0.0-1.0, varsayılan 0.75)
            "xf_node_id":  5,           # opsiyonel — yayınlanacak forum node ID'si
            "xf_prefix_id": 2,          # opsiyonel — konu öneki ID'si
        }

    Bu görevi kuyruğa almak için:
        from app.tasks.ai_writer import ai_article_task
        result = ai_article_task.delay({
            "topic":  "Kant'ın ahlak felsefesi ve çağımıza yansımaları",
            "tone":   "felsefi",
            "length": "uzun",
        })
        task_id = result.id
    """
    task_id = self.request.id

    try:
        # ── ADIM 1: Durumu RUNNING yap ─────────────────────────────────
        update_task_status(task_id, "RUNNING")

        # ── ADIM 2: Payload doğrulama ──────────────────────────────────
        topic = payload.get("topic", "").strip()
        if not topic:
            raise ValueError("payload.topic zorunludur.")
        if len(topic) < 5:
            raise ValueError(f"Konu çok kısa: '{topic}'")

        tone   = payload.get("tone", "felsefi").strip().lower()
        length = payload.get("length", "orta").strip().lower()
        category  = payload.get("category", "")
        keywords  = payload.get("keywords", "")
        extra_notes = payload.get("extra_notes", "")
        temperature = float(payload.get("temperature", 0.75))

        # Geçersiz ton kontrolü
        if tone not in _VALID_TONES:
            logger.warning(
                f"[WRITER] Geçersiz ton '{tone}', 'felsefi' kullanılıyor."
            )
            tone = "felsefi"

        # Geçersiz uzunluk kontrolü
        if length not in _LENGTH_TO_MAX_TOKENS:
            logger.warning(
                f"[WRITER] Geçersiz uzunluk '{length}', 'orta' kullanılıyor."
            )
            length = "orta"

        max_tokens = _LENGTH_TO_MAX_TOKENS[length]

        # ── ADIM 3: Prompt oluşturma ───────────────────────────────────
        prompt = build_article_prompt(
            topic       = topic,
            tone        = tone,
            length      = length,
            category    = category,
            keywords    = keywords,
            extra_notes = extra_notes,
        )

        # ── ADIM 4: Token sayımı ───────────────────────────────────────
        # Sistem promptu + kullanıcı mesajı birlikte tahmin edilir
        full_text_for_estimation = AI_WRITER_SYSTEM + " " + prompt
        token_count = estimate_token_count(full_text_for_estimation)

        model = current_app.config.get("PRIMARY_MODEL", "gemini-2.5-flash")

        logger.info(
            f"[WRITER] Görev başlıyor | task={task_id[:8]} "
            f"topic='{topic[:50]}' ton={tone} uzunluk={length} "
            f"~{token_count} token"
        )

        # ── ADIM 5: ★ BÜTÇE ÖN KONTROLÜ ★ ────────────────────────────
        # Bu çağrı, bütçe doluysa CircuitBreakerOpenError veya
        # InsufficientBudgetError fırlatır → retry yapılmaz, FAILED olur
        BudgetGuard.pre_flight_check(
            token_count           = token_count,
            model                 = model,
            task_id               = task_id,
            output_token_estimate = max_tokens,
        )

        # ── ADIM 6: LLM Çağrısı (Gemini → Claude → GPT-4o-mini) ───────
        # Bu fonksiyon içinde rate limit backoff'u yönetilir
        llm_response = complete_with_fallback(
            prompt      = prompt,
            system      = AI_WRITER_SYSTEM,
            max_tokens  = max_tokens,
            temperature = temperature,
            task_id     = task_id,
        )

        # ── ADIM 7: ★ GERÇEK MALİYETİ KAYDET ★ ───────────────────────
        BudgetGuard.record_actual_cost(
            task_id       = task_id,
            model         = llm_response.model,
            prompt_tokens = llm_response.prompt_tokens,
            output_tokens = llm_response.output_tokens,
            status        = "success",
        )

        # ── ADIM 8: Meta bloğu ayrıştırma ─────────────────────────────
        parsed = parse_meta_block(llm_response.text)
        final_content = parsed["content"]
        meta = {
            "description": parsed["description"],
            "keywords":    parsed["keywords"] or [k.strip() for k in keywords.split(",") if k.strip()],
        }

        # ── ADIM 9: XenForo'da konu oluştur (Fail-Soft) ─────────────
        # xf_node_id verilmediyse yayın atlanır, görev yine SUCCESS sayılır.
        # XenForo hatası LLM görevini FAILED yapmaz (bağımsız).
        from app.xenforo.publisher import publish_to_xenforo

        xf_result = publish_to_xenforo(
            task_id   = task_id,
            content   = final_content,
            title     = topic,                          # Konu başlığı = makale konusu
            node_id   = payload.get("xf_node_id"),
            tags      = meta.get("keywords", []),
            prefix_id = payload.get("xf_prefix_id"),   # Ton başlığı varsa
        )

        # ── ADIM 10: TaskLog güncelle ──────────────────────────────────
        update_task_status(
            task_id    = task_id,
            status     = "SUCCESS",
            result     = {
                "topic":      topic,
                "tone":       tone,
                "length":     length,
                "word_count": len(final_content.split()),
                "content":    final_content[:500] + "..." if len(final_content) > 500 else final_content,
                "meta":       meta,
                "xf":         xf_result,
            },
            model_used = llm_response.model,
        )

        # ── ADIM 11: Telegram bildirimi ────────────────────────────────
        notify_task_success(task_id, "ai_article")

        logger.info(
            f"[WRITER] ✅ Makale tamamlandı | task={task_id[:8]} "
            f"model={llm_response.model} "
            f"kelime≈{len(final_content.split())}"
        )
        return {
            "status":    "success",
            "topic":     topic,
            "content":   final_content,
            "meta":      meta,
            "model":     llm_response.model,
            "in_tokens": llm_response.prompt_tokens,
            "out_tokens": llm_response.output_tokens,
        }

    # ── HATA YÖNETİMİ ──────────────────────────────────────────────────

    except (BudgetExceededError, CircuitBreakerOpenError, BudgetGuardError) as exc:
        # BÜTÇE HATASI → KESİNLİKLE RETRY YAPMA
        # Retry yapılırsa aynı hata → para harcanmaz ama kuyruk kirlenir
        update_task_status(task_id, "FAILED", error_msg=str(exc))
        notify_task_failed(task_id, "ai_article", str(exc))
        logger.warning(f"[WRITER] Bütçe hatası, görev durduruldu: {exc}")
        raise   # Celery'ye ilet (max_retries aşılmış gibi davran)

    except ValueError as exc:
        # PAYLOAD HATASI → Retry anlamsız
        update_task_status(task_id, "FAILED", error_msg=str(exc))
        logger.warning(f"[WRITER] Geçersiz payload: {exc}")
        raise

    except LLMContentFilterError as exc:
        # İÇERİK FİLTRESİ → Ton veya konuyu değiştirmeden retry anlamsız
        update_task_status(task_id, "FAILED", error_msg=str(exc))
        notify_task_failed(task_id, "ai_article", str(exc))
        raise

    except AllModelsFailedError as exc:
        # TÜM MODELLER BAŞARISIZ → FAILED
        update_task_status(task_id, "FAILED", error_msg=str(exc))
        raise

    except Exception as exc:
        # GENEL HATA → Celery exponential backoff retry
        retry_count = self.request.retries
        logger.error(
            f"[WRITER] Genel hata (retry {retry_count}/{self.max_retries}): {exc}",
            exc_info=True,
        )
        if retry_count < self.max_retries:
            wait = 2 ** retry_count    # 2, 4, 8 saniye bekle
            raise self.retry(exc=exc, countdown=wait)
        else:
            update_task_status(task_id, "FAILED", error_msg=str(exc))
            notify_task_failed(task_id, "ai_article", str(exc))
            raise

"""
app/tasks/youtube.py — GÖREV A: YouTube → Makale Dönüştürücü.

Bu görev aşağıdaki adımları sırayla çalıştırır:

  1. URL doğrulama ve video ID çıkarma
  2. Redis önbellek kontrolü (7 gün TTL)
  3. youtube-transcript-api ile transkript çekme (TR → EN fallback)
  4. Transkripti metin birleştirme
  5. Token sayımı
  6. ★ BudgetGuard.pre_flight_check() — Bütçe onayı ÇOK ÖNEMLİ
  7. Multi-model LLM çağrısı (Gemini → Claude → GPT-4o-mini)
  8. ★ BudgetGuard.record_actual_cost() — Gerçek maliyet kaydı
  9. Meta bloğu ayrıştırma
  10. TaskLog güncelleme (SUCCESS)
  11. [Faz 5'te] XenForo thread oluşturma placeholder

Hata yönetimi:
  - BudgetExceededError / CircuitBreakerOpenError → RETRY YAPMA, FAILED yap
  - TranscriptFetchError → RETRY YAPMA (video'da altyazı yok, tekrar denense de yok)
  - LLMRateLimitError → Exponential backoff — önce LLM client halleder, sonra task retry
  - AllModelsFailedError → FAILED yap, Telegram kritik bildirim
  - Genel Exception → max 3 retry (Celery)
"""

import logging
import re
from urllib.parse import urlparse, parse_qs

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
from app.llm.prompts import YOUTUBE_SUMMARY_SYSTEM, build_youtube_prompt, parse_meta_block
from app.cache.redis_cache import (
    get_transcript_cache,
    set_transcript_cache,
    acquire_task_lock,
    release_task_lock,
)
from app.notifications.telegram import notify_task_success, notify_task_failed

logger = logging.getLogger(__name__)


# ============================================================
# YARDIMCI FONKSİYONLAR
# ============================================================

class TranscriptFetchError(Exception):
    """Transkript çekilemediğinde fırlatılır — RETRY anlamsız."""
    pass


def _extract_video_id(url: str) -> str:
    """
    YouTube URL'sinden video ID'sini ayıklar.
    Desteklenen formatlar:
      - https://www.youtube.com/watch?v=VIDEO_ID
      - https://youtu.be/VIDEO_ID
      - https://youtube.com/shorts/VIDEO_ID
      - https://www.youtube.com/embed/VIDEO_ID

    Returns:
        video_id — 11 karakterlik string

    Raises:
        ValueError — Geçersiz URL
    """
    url = url.strip()

    # Short URL: youtu.be/ID
    if "youtu.be/" in url:
        match = re.search(r"youtu\.be/([a-zA-Z0-9_-]{11})", url)
        if match:
            return match.group(1)

    # Shorts veya embed
    match = re.search(r"/(?:shorts|embed)/([a-zA-Z0-9_-]{11})", url)
    if match:
        return match.group(1)

    # Standart: ?v=ID
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "v" in qs and qs["v"]:
        vid = qs["v"][0]
        if re.match(r"^[a-zA-Z0-9_-]{11}$", vid):
            return vid

    raise ValueError(f"Geçerli YouTube video ID'si bulunamadı: {url}")


def _fetch_transcript(video_id: str) -> tuple[str, str, str]:
    """
    youtube-transcript-api kullanarak transkripti çeker.
    Önce Türkçe, sonra İngilizce, sonra mevcut herhangi bir dil denenir.

    Returns:
        (transcript_text, video_title, channel_name) — başarıyla alınan transkript

    Raises:
        TranscriptFetchError — Transkript alınamadı
    """
    try:
        from youtube_transcript_api import (
            YouTubeTranscriptApi,
            TranscriptsDisabled,
            NoTranscriptFound,
            VideoUnavailable,
        )
    except ImportError:
        raise TranscriptFetchError("youtube-transcript-api kütüphanesi yüklü değil.")

    try:
        # Dil önceliği: Türkçe → İngilizce → otomatik üretilmiş → herhangi biri
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            # Manuel Türkçe transkript ara
            try:
                transcript = transcript_list.find_transcript(["tr"])
                language_used = "tr"
            except NoTranscriptFound:
                # Manuel İngilizce
                try:
                    transcript = transcript_list.find_transcript(["en"])
                    language_used = "en"
                except NoTranscriptFound:
                    # Otomatik oluşturulmuş Türkçe
                    try:
                        transcript = transcript_list.find_generated_transcript(["tr", "en"])
                        language_used = "auto"
                    except NoTranscriptFound:
                        # Son çare: mevcut ilk transkript
                        transcript = next(iter(transcript_list))
                        language_used = transcript.language_code

            raw_segments = transcript.fetch()

        except NoTranscriptFound:
            raise TranscriptFetchError(
                f"Video için hiçbir transkript bulunamadı: {video_id}"
            )

        # Transkript segmentlerini tek metne birleştir
        # Her segmentin 'text' alanı var
        text_parts = []
        for seg in raw_segments:
            # API'ye göre .text veya['text'] olabilir
            text = seg.text if hasattr(seg, "text") else seg.get("text", "")
            text = text.strip().replace("\n", " ")
            if text:
                text_parts.append(text)

        full_text = " ".join(text_parts)

        if not full_text or len(full_text) < 50:
            raise TranscriptFetchError(
                f"Transkript çok kısa veya boş: {len(full_text)} karakter"
            )

        logger.info(
            f"[YOUTUBE] Transkript alındı: video={video_id} "
            f"dil={language_used} uzunluk={len(full_text)} karakter"
        )
        # Video başlığı ve kanal adı için ek API çağrısı yapmıyoruz
        # (yt-dlp veya oEmbed ile Faz 5'te eklenebilir)
        return full_text, "", ""

    except TranscriptFetchError:
        raise
    except Exception as e:
        raise TranscriptFetchError(f"Transkript çekme hatası ({video_id}): {e}")


def _chunk_transcript_if_needed(text: str, max_token_limit: int = 80_000) -> list[str]:
    """
    Çok uzun transkriptleri (3+ saatlik videolar) işlenebilir parçalara böler.

    Gemini Flash 1M token kapasitesine sahip, ama bütçe kontrolü nedeniyle
    max_token_limit ile sınırlandırıyoruz. Çok uzun metinler Map-Reduce
    yaklaşımıyla özetlenir:
      1. Transkript N parçaya bölünür
      2. Her parça ayrı özetlenir
      3. Özetler birleştirilerek final makaleye çevrilir

    Bu işlem için birden fazla BudgetGuard.pre_flight_check() çağrısı gerekir.
    Şimdilik 80K token (~320KB text) altındaki transkriptler tek parça işlenir.
    """
    token_estimate = estimate_token_count(text)
    if token_estimate <= max_token_limit:
        return [text]  # Tek parça yeterli

    # Kelime sayısına göre bölme (yaklaşık eşit parçalar)
    words = text.split()
    words_per_chunk = int(len(words) * max_token_limit / token_estimate)
    chunks = []
    for i in range(0, len(words), words_per_chunk):
        chunk = " ".join(words[i: i + words_per_chunk])
        if chunk:
            chunks.append(chunk)

    logger.info(
        f"[YOUTUBE] Uzun transkript {len(chunks)} parçaya bölündü "
        f"(toplam ~{token_estimate} token)"
    )
    return chunks


# ============================================================
# ANA GÖREV
# ============================================================

@celery.task(
    name        = "app.tasks.youtube.youtube_to_article_task",
    bind        = True,
    max_retries = 3,
    rate_limit  = "5/m",   # Dakikada maksimum 5 YouTube görevi
)
def youtube_to_article_task(self, payload: dict) -> dict:
    """
    YouTube URL'sini makaleye dönüştürür.

    payload formatı:
        {
            "url":       "https://youtube.com/watch?v=...",
            "extra_notes": "Özellikle ...'ya odaklan",   # opsiyonel
            "max_tokens":  2500,                          # opsiyonel
        }

    Bu görevi kuyruğa almak için:
        from app.tasks.youtube import youtube_to_article_task
        result = youtube_to_article_task.delay({
            "url": "https://youtube.com/watch?v=abc123"
        })
        task_id = result.id

    NOT: Celery task'ının task_id'si TaskLog'a kaydedilmeli.
         Bkz. app/tasks/routes.py
    """
    task_id  = self.request.id
    video_id = None
    lock_key = None

    try:
        # ── ADIM 1: Durumu RUNNING yap ─────────────────────────────────
        update_task_status(task_id, "RUNNING")

        # ── ADIM 2: URL doğrulama ve video ID ──────────────────────────
        url = payload.get("url", "").strip()
        if not url:
            raise ValueError("payload.url zorunludur.")

        try:
            video_id = _extract_video_id(url)
        except ValueError as e:
            raise TranscriptFetchError(str(e))

        # ── ADIM 3: Duplicate task kilidi ──────────────────────────────
        lock_key = f"lock:youtube:{video_id}"
        if not acquire_task_lock(lock_key, ttl=600):
            # Başka bir worker bu videoyu işliyors
            logger.warning(f"[YOUTUBE] Video zaten işleniyor, kilit var: {video_id}")
            update_task_status(
                task_id, "FAILED",
                error_msg="Bu video başka bir görevde zaten işleniyor."
            )
            return {"status": "duplicate", "video_id": video_id}

        # ── ADIM 4: Redis önbellek kontrolü ────────────────────────────
        transcript_text = get_transcript_cache(video_id)
        if transcript_text:
            logger.info(f"[YOUTUBE] Transkript Redis önbellekten alındı: {video_id}")
            video_title = ""
            channel_name = ""
        else:
            # ── ADIM 5: Transkript fetch ────────────────────────────────
            transcript_text, video_title, channel_name = _fetch_transcript(video_id)
            # Önbelleğe al (7 gün)
            set_transcript_cache(video_id, transcript_text)

        # ── ADIM 6: Transkript chunking (uzun video kontrolü) ──────────
        chunks = _chunk_transcript_if_needed(transcript_text)
        extra_notes  = payload.get("extra_notes", "")
        max_tokens   = int(payload.get("max_tokens", 2500))

        # ── ADIM 7: Her parça için LLM çağrısı ─────────────────────────
        # Tek parça (standart durum):
        if len(chunks) == 1:
            prompt = build_youtube_prompt(
                transcript_text = chunks[0],
                video_title     = video_title,
                channel_name    = channel_name,
                extra_notes     = extra_notes,
            )
            token_count = estimate_token_count(prompt)
            model = current_app.config.get("PRIMARY_MODEL", "gemini-2.5-flash")

            # ★ BÜTÇE ÖN KONTROLÜ — API çağrısından önce zorunlu ★
            BudgetGuard.pre_flight_check(
                token_count           = token_count,
                model                 = model,
                task_id               = task_id,
                output_token_estimate = max_tokens,
            )

            # LLM çağrısı
            llm_response = complete_with_fallback(
                prompt     = prompt,
                system     = YOUTUBE_SUMMARY_SYSTEM,
                max_tokens = max_tokens,
                task_id    = task_id,
            )

            # ★ GERÇEK MALİYETİ KAYDET ★
            BudgetGuard.record_actual_cost(
                task_id       = task_id,
                model         = llm_response.model,
                prompt_tokens = llm_response.prompt_tokens,
                output_tokens = llm_response.output_tokens,
                status        = "success",
            )

            parsed = parse_meta_block(llm_response.text)
            final_content = parsed["content"]
            meta = {
                "description": parsed["description"],
                "keywords":    parsed["keywords"],
            }
            model_used = llm_response.model
            total_cost = BudgetGuard._calc_cost_from_response(llm_response) if hasattr(BudgetGuard, '_calc_cost_from_response') else None

        else:
            # Çok parçalı: Map-Reduce özeti
            # Her parça için ayrı pre_flight_check yapılır
            final_content, meta, model_used = _process_chunked_transcript(
                chunks      = chunks,
                task_id     = task_id,
                extra_notes = extra_notes,
                max_tokens  = max_tokens,
            )

        # ── ADIM 8: XenForo'da konu oluştur (Fail-Soft) ─────────────
        # xf_node_id payload'da verilmediyse yayın atlanır — görev yine SUCCESS
        # XenForo hatası LLM görevini FAILED yapmaz (bağımsız)
        from app.xenforo.publisher import publish_to_xenforo
        from app.xenforo.threads   import ThreadManager

        # Video başlığı yoksa (oEmbed eklenmediği için) içerikten çıkar
        xf_title = video_title or ThreadManager.extract_title_from_content(
            final_content,
            fallback=f"YouTube Özeti: {video_id}",
        )
        xf_result = publish_to_xenforo(
            task_id   = task_id,
            content   = final_content,
            title     = xf_title,
            node_id   = payload.get("xf_node_id"),
            tags      = meta.get("keywords", []),
        )

        # ── ADIM 9: TaskLog START güncelle ─────────────────────────────
        update_task_status(
            task_id    = task_id,
            status     = "SUCCESS",
            result     = {
                "video_id":   video_id,
                "content":    final_content[:500] + "..." if len(final_content) > 500 else final_content,
                "full_length": len(final_content),
                "meta":       meta,
                "xf":         xf_result,
            },
            model_used = model_used,
        )

        # ── ADIM 10: Telegram bildirimi ────────────────────────────────
        notify_task_success(task_id, "youtube_summary")

        logger.info(
            f"[YOUTUBE] ✅ Görev tamamlandı: task={task_id[:8]} "
            f"video={video_id} model={model_used}"
        )
        return {
            "status":   "success",
            "video_id": video_id,
            "content":  final_content,
            "meta":     meta,
        }

    # ── HATA YÖNETİMİ ──────────────────────────────────────────────────

    except (BudgetExceededError, CircuitBreakerOpenError, BudgetGuardError) as exc:
        # BÜTÇE HATASI → RETRY YAPMA, direkt FAILED
        update_task_status(task_id, "FAILED", error_msg=str(exc))
        notify_task_failed(task_id, "youtube_summary", str(exc))
        logger.warning(f"[YOUTUBE] Bütçe hatası, görev durduruldu: {exc}")
        raise   # Celery'nin retry yapmaması için raise (başka except yok)

    except TranscriptFetchError as exc:
        # TRANSKRİPT HATASI → Video'da altyazı yok, retry anlamsız
        update_task_status(task_id, "FAILED", error_msg=str(exc))
        notify_task_failed(task_id, "youtube_summary", str(exc))
        logger.warning(f"[YOUTUBE] Transkript hatası, görev durduruldu: {exc}")
        raise

    except LLMContentFilterError as exc:
        # İÇERİK FİLTRESİ → Retry anlamsız
        update_task_status(task_id, "FAILED", error_msg=str(exc))
        notify_task_failed(task_id, "youtube_summary", str(exc))
        raise

    except AllModelsFailedError as exc:
        # TÜM MODELLER BAŞARISIZ → FAILED, Telegram notify_all_models_failed zaten çağrıldı
        update_task_status(task_id, "FAILED", error_msg=str(exc))
        raise

    except Exception as exc:
        # GENEL HATA → Celery'nin retry mekanizmasını kullan
        retry_count = self.request.retries
        logger.error(
            f"[YOUTUBE] Görev hatası (retry {retry_count}/{self.max_retries}): {exc}",
            exc_info=True,
        )
        if retry_count < self.max_retries:
            # Exponential backoff: 2^retry = 2, 4, 8 saniye
            wait = 2 ** retry_count
            raise self.retry(exc=exc, countdown=wait)
        else:
            update_task_status(task_id, "FAILED", error_msg=str(exc))
            notify_task_failed(task_id, "youtube_summary", str(exc))
            raise

    finally:
        # Görev tamamlandı veya başarısız oldu — kilidi serbest bırak
        if lock_key:
            release_task_lock(lock_key)


def _process_chunked_transcript(
    chunks: list[str],
    task_id: str,
    extra_notes: str,
    max_tokens: int,
) -> tuple[str, dict, str]:
    """
    Çok parçalı transkript için Map-Reduce yaklaşımı.

    1. Map: Her parçayı kısa özetle
    2. Reduce: Özetleri birleştirip final makaleye çevir

    Her LLM çağrısı için ayrı BudgetGuard.pre_flight_check() yapılır.
    """
    model = current_app.config.get("PRIMARY_MODEL", "gemini-2.5-flash")
    summaries = []

    for i, chunk in enumerate(chunks):
        chunk_prompt = (
            f"Aşağıdaki bölümü (Parça {i+1}/{len(chunks)}) kısaca özetle "
            f"(300-500 kelime, madde madde değil, paragraf halinde):\n\n{chunk}"
        )
        token_count = estimate_token_count(chunk_prompt)

        # Her parça için bütçe kontrolü
        BudgetGuard.pre_flight_check(
            token_count           = token_count,
            model                 = model,
            task_id               = f"{task_id}_chunk{i}",
            output_token_estimate = 600,
        )

        resp = complete_with_fallback(
            prompt     = chunk_prompt,
            system     = YOUTUBE_SUMMARY_SYSTEM,
            max_tokens = 600,
            task_id    = task_id,
        )
        BudgetGuard.record_actual_cost(
            task_id       = f"{task_id}_chunk{i}",
            model         = resp.model,
            prompt_tokens = resp.prompt_tokens,
            output_tokens = resp.output_tokens,
        )
        summaries.append(resp.text.strip())
        model_used = resp.model

    # Reduce: Özetleri birleştir
    combined = "\n\n---\n\n".join(summaries)
    final_prompt = build_youtube_prompt(
        transcript_text = combined,
        extra_notes     = extra_notes + " (Bu metin bölüm özetlerinin derlemesidir.)",
    )
    token_count = estimate_token_count(final_prompt)

    BudgetGuard.pre_flight_check(
        token_count           = token_count,
        model                 = model,
        task_id               = f"{task_id}_final",
        output_token_estimate = max_tokens,
    )
    final_resp = complete_with_fallback(
        prompt     = final_prompt,
        system     = YOUTUBE_SUMMARY_SYSTEM,
        max_tokens = max_tokens,
        task_id    = task_id,
    )
    BudgetGuard.record_actual_cost(
        task_id       = f"{task_id}_final",
        model         = final_resp.model,
        prompt_tokens = final_resp.prompt_tokens,
        output_tokens = final_resp.output_tokens,
    )

    parsed = parse_meta_block(final_resp.text)
    return parsed["content"], {"description": parsed["description"], "keywords": parsed["keywords"]}, final_resp.model

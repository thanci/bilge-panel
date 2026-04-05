"""
app/llm/client.py — Multi-Model LLM İstemcisi ve Fallback Zinciri.

Mimari: Primary → Fallback-1 → Fallback-2
  1. Gemini 2.5 Flash  (birincil — hız + maliyet optimumu)
  2. Claude Haiku 3.5  (1. fallback — kalite)
  3. GPT-4o-mini       (2. fallback — en geniş uyumluluk)

Fallback Koşulları:
  - 429 Rate Limit    → Exponential backoff, sonra sonraki modele geç
  - 500 Server Error  → Anında sonraki modele geç (retry sınırı = 2)
  - API Key Hatası    → Sonraki modele geç (bu modeli atla)
  - 503 Service Unav. → Sonraki modele geç

Fallback Olmayan Durumlar (sabit hata):
  - İçerik filtresine takılma (HARM_CATEGORY) → Exception fırlat, kaydet
  - BudgetGuardError → Kesinlikle fallback yok, direkt durdur

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NOT: Bu modül doğrudan çağrılmaz. Celery task'ları
     complete_with_fallback() fonksiyonunu kullanır.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

from flask import current_app

logger = logging.getLogger(__name__)


# ============================================================
# VERİ YAPILARI
# ============================================================

@dataclass
class LLMResponse:
    """
    Tüm model provider'larının yanıtını normalize eden ortak yapı.
    Hangi modelin çalıştığından bağımsız olarak aynı alanlara sahip.
    """
    text:          str       # Üretilen metin
    model:         str       # Gerçekten kullanılan model adı
    prompt_tokens: int       # Giriş token sayısı (API'den alındı)
    output_tokens: int       # Çıktı token sayısı (API'den alındı)


class LLMRateLimitError(Exception):
    """429 Rate Limit — exponential backoff ile retry yapılabilir."""
    pass


class LLMServerError(Exception):
    """5xx Server Error — genellikle geçici, sonraki modele geç."""
    pass


class LLMContentFilterError(Exception):
    """İçerik filtresi — retry veya fallback yapma, kaydet."""
    pass


class AllModelsFailedError(Exception):
    """Tüm modeller başarısız oldu — Telegram ile kritik bildirim gönder."""
    pass


# ============================================================
# PROVIDER ADAPTÖRLER
# ============================================================

class _GeminiAdapter:
    """
    google-generativeai 0.8.x adaptörü.
    Gemini 2.5 Flash için API çağrısı yapar.

    NOT: Gemini 2.5 Flash varsayılan olarak "thinking" moduyla gelir.
    Thinking modu açıkken, düşünme token'ları max_output_tokens bütçesinden
    yenir — bu da kısa çıktılara neden olur. İçerik üretimi görevlerinde
    thinking'i kapatıyoruz.
    """

    def __init__(self, api_key: str):
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self._genai = genai
        except ImportError:
            raise RuntimeError("google-generativeai paketi yüklü değil.")

    def complete(
        self,
        prompt: str,
        system: str,
        model: str,
        max_tokens: int,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Gemini modeline istek gönderir."""
        import google.generativeai as genai
        from google.api_core import exceptions as gexc

        try:
            # Gemini 2.5 thinking modelleri: düşünme token'ları max_output_tokens'tan
            # tüketilir, bu yüzden max_tokens'ı artırıyoruz
            effective_max_tokens = max_tokens
            is_thinking_model = "2.5" in model

            if is_thinking_model:
                # Thinking overhead'i telafi etmek için 4x artır
                effective_max_tokens = max_tokens * 4

            # thinking_config'li GenerationConfig dene
            generation_config = None
            if is_thinking_model:
                try:
                    generation_config = self._genai.types.GenerationConfig(
                        max_output_tokens=effective_max_tokens,
                        temperature=temperature,
                        thinking_config={"thinking_budget": 0},
                    )
                    logger.info("[LLM] Gemini thinking_config=0 başarıyla ayarlandı")
                except (TypeError, ValueError) as te:
                    logger.warning(f"[LLM] thinking_config desteklenmiyor ({te}), fallback")
                    generation_config = None

            # Fallback: thinking_config'siz GenerationConfig
            if generation_config is None:
                generation_config = self._genai.types.GenerationConfig(
                    max_output_tokens=effective_max_tokens,
                    temperature=temperature,
                )

            gmodel = self._genai.GenerativeModel(
                model_name         = model,
                system_instruction = system,
                generation_config  = generation_config,
            )
            response = gmodel.generate_content(prompt)

            # İçerik filtresi kontrolü
            if not response.candidates:
                raise LLMContentFilterError(
                    f"Gemini içerik filtresi tetiklendi: {response.prompt_feedback}"
                )

            text = response.text
            usage = response.usage_metadata

            # Debug: yanıt uzunluğunu logla
            logger.info(
                f"[LLM] Gemini yanıt detayı: "
                f"text_len={len(text)} chars, "
                f"prompt_tokens={usage.prompt_token_count}, "
                f"output_tokens={usage.candidates_token_count}, "
                f"total_tokens={getattr(usage, 'total_token_count', 'N/A')}"
            )

            return LLMResponse(
                text          = text,
                model         = model,
                prompt_tokens = usage.prompt_token_count,
                output_tokens = usage.candidates_token_count,
            )

        except gexc.ResourceExhausted as e:
            raise LLMRateLimitError(f"Gemini 429: {e}")
        except gexc.InternalServerError as e:
            raise LLMServerError(f"Gemini 500: {e}")
        except gexc.ServiceUnavailable as e:
            raise LLMServerError(f"Gemini 503: {e}")
        except LLMContentFilterError:
            raise
        except Exception as e:
            # Beklenmedik hata — server error olarak handle et
            raise LLMServerError(f"Gemini beklenmedik: {e}")


class _ClaudeAdapter:
    """
    anthropic 0.40.x adaptörü.
    Claude Haiku 3.5 için API çağrısı yapar.
    """

    def __init__(self, api_key: str):
        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            raise RuntimeError("anthropic paketi yüklü değil.")

    def complete(
        self,
        prompt: str,
        system: str,
        model: str,
        max_tokens: int,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Claude modeline istek gönderir."""
        import anthropic

        try:
            response = self._client.messages.create(
                model      = model,
                max_tokens = max_tokens,
                temperature= temperature,
                system     = system,
                messages   = [{"role": "user", "content": prompt}],
            )
            text = response.content[0].text if response.content else ""
            return LLMResponse(
                text          = text,
                model         = model,
                prompt_tokens = response.usage.input_tokens,
                output_tokens = response.usage.output_tokens,
            )

        except anthropic.RateLimitError as e:
            raise LLMRateLimitError(f"Claude 429: {e}")
        except anthropic.APIStatusError as e:
            if e.status_code >= 500:
                raise LLMServerError(f"Claude 5xx: {e}")
            raise LLMServerError(f"Claude API hatası ({e.status_code}): {e}")
        except Exception as e:
            raise LLMServerError(f"Claude beklenmedik: {e}")


class _OpenAIAdapter:
    """
    openai 1.x adaptörü.
    GPT-4o-mini için API çağrısı yapar.
    """

    def __init__(self, api_key: str):
        try:
            from openai import OpenAI
            self._client = OpenAI(api_key=api_key)
        except ImportError:
            raise RuntimeError("openai paketi yüklü değil.")

    def complete(
        self,
        prompt: str,
        system: str,
        model: str,
        max_tokens: int,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """GPT-4o-mini modeline istek gönderir."""
        from openai import RateLimitError, APIStatusError

        try:
            response = self._client.chat.completions.create(
                model       = model,
                max_tokens  = max_tokens,
                temperature = temperature,
                messages    = [
                    {"role": "system", "content": system},
                    {"role": "user",   "content": prompt},
                ],
            )
            text = response.choices[0].message.content or ""
            return LLMResponse(
                text          = text,
                model         = model,
                prompt_tokens = response.usage.prompt_tokens,
                output_tokens = response.usage.completion_tokens,
            )

        except RateLimitError as e:
            raise LLMRateLimitError(f"OpenAI 429: {e}")
        except APIStatusError as e:
            raise LLMServerError(f"OpenAI {e.status_code}: {e}")
        except Exception as e:
            raise LLMServerError(f"OpenAI beklenmedik: {e}")


# ============================================================
# FALLBACK ZİNCİRİ
# ============================================================

# Exponential backoff değerleri: 1. retry → 4s, 2. retry → 8s bekle
_RATE_LIMIT_BACKOFFS = [4, 8]
_MAX_RETRIES_PER_MODEL = 2


def complete_with_fallback(
    prompt: str,
    system: str,
    max_tokens: int = 2000,
    temperature: float = 0.7,
    task_id: str = "",
) -> LLMResponse:
    """
    Multi-model LLM istemcisi — Gemini → Claude → GPT-4o-mini fallback zinciri.

    Celery task'larından çağrılır. Bu fonksiyon BudgetGuard çağrısı YAPMAZ —
    bütçe kontrolü task başlamadan önce yapılmış olmalıdır. Bu fonksiyon
    sadece API çağrısını gerçekleştirir.

    Fallback Akışı:
      1. Gemini Flash dene
         ├─ 429 → 4s bekle, tekrar dene → 8s bekle, tekrar dene → Fallback
         ├─ 5xx → Anında Claude'a geç
         └─ İçerik filtresi → Exception fırlat (fallback YOK)
      2. Claude Haiku dene (aynı retry mantığı)
      3. GPT-4o-mini dene (aynı retry mantığı)
      4. Hepsi başarısız → AllModelsFailedError

    Args:
        prompt:      LLM'e gönderilecek kullanıcı mesajı
        system:      Sistem direktifi (YOUTUBE_SUMMARY_SYSTEM vb.)
        max_tokens:  Maksimum çıktı token sayısı
        temperature: Yaratıcılık düzeyi (0.0 = deterministik, 1.0 = maksimum)
        task_id:     Loglama için Celery task UUID'si

    Returns:
        LLMResponse

    Raises:
        LLMContentFilterError: İçerik filtresi tetiklendi (tekrar deneme anlamsız)
        AllModelsFailedError:  Tüm modeller tükendi
    """
    # Yapılandırmadan model listesi oluştur
    model_chain = _build_model_chain()

    last_error: Optional[Exception] = None

    for (model_name, adapter) in model_chain:
        if adapter is None:
            logger.warning(f"[LLM] {model_name} için API key yapılandırılmamış — atlanıyor.")
            continue

        logger.info(f"[LLM] Deneniyor: model={model_name} task={task_id[:8]}")

        for attempt in range(_MAX_RETRIES_PER_MODEL + 1):
            try:
                response = adapter.complete(
                    prompt      = prompt,
                    system      = system,
                    model       = model_name,
                    max_tokens  = max_tokens,
                    temperature = temperature,
                )
                logger.info(
                    f"[LLM] ✅ Başarılı | model={response.model} "
                    f"in={response.prompt_tokens} out={response.output_tokens} "
                    f"task={task_id[:8]}"
                )
                return response   # ← Başarı

            except LLMContentFilterError as e:
                # İçerik filtresi → ne retry ne fallback
                logger.error(f"[LLM] İçerik filtresi ({model_name}): {e}")
                raise   # Doğrudan task'a ilet

            except LLMRateLimitError as e:
                last_error = e
                if attempt < _MAX_RETRIES_PER_MODEL:
                    wait = _RATE_LIMIT_BACKOFFS[attempt]
                    logger.warning(
                        f"[LLM] 429 Rate Limit ({model_name}) — "
                        f"{wait}s bekleyip tekrar deneniyor. "
                        f"(deneme {attempt + 1}/{_MAX_RETRIES_PER_MODEL})"
                    )
                    time.sleep(wait)
                else:
                    logger.warning(
                        f"[LLM] {model_name} rate limit exhausted — "
                        f"sonraki modele geçiliyor."
                    )
                    break  # Bu modeli bırak, sonrakine geç

            except LLMServerError as e:
                last_error = e
                logger.warning(
                    f"[LLM] 5xx/Sunucu hatası ({model_name}): {e} — "
                    f"sonraki modele geçiliyor."
                )
                break  # Server hatasında hemen fallback

    # Tüm modeller başarısız oldu
    error_msg = f"Tüm LLM modelleri başarısız. Son hata: {last_error}"
    logger.critical(f"[LLM] 🆘 {error_msg}")

    try:
        from app.notifications.telegram import notify_all_models_failed
        notify_all_models_failed(task_id)
    except Exception:
        pass

    raise AllModelsFailedError(error_msg)


def _build_model_chain() -> list[tuple[str, object]]:
    """
    Flask config'den API key'leri okuyarak aktif model listesi oluşturur.
    API key'i olmayan modeller None adapter ile eklenir (atlanır).

    Returns:
        [(model_name, adapter_instance_or_None), ...]
    """
    chain = []

    # 1. Gemini Flash — Birincil
    primary_key = current_app.config.get("GEMINI_API_KEY", "")
    primary_model = current_app.config.get("PRIMARY_MODEL", "gemini-2.5-flash")
    if primary_key:
        try:
            chain.append((primary_model, _GeminiAdapter(primary_key)))
        except RuntimeError as e:
            logger.warning(f"[LLM] Gemini adaptör başlatılamadı: {e}")
            chain.append((primary_model, None))
    else:
        logger.warning("[LLM] GEMINI_API_KEY yapılandırılmamış.")
        chain.append((primary_model, None))

    # 2. Claude Haiku — 1. Fallback
    claude_key = current_app.config.get("ANTHROPIC_API_KEY", "")
    claude_model = current_app.config.get("FALLBACK_MODEL_1", "claude-haiku-3-5")
    if claude_key:
        try:
            chain.append((claude_model, _ClaudeAdapter(claude_key)))
        except RuntimeError as e:
            logger.warning(f"[LLM] Claude adaptör başlatılamadı: {e}")
            chain.append((claude_model, None))
    else:
        chain.append((claude_model, None))

    # 3. GPT-4o-mini — 2. Fallback
    openai_key = current_app.config.get("OPENAI_API_KEY", "")
    openai_model = current_app.config.get("FALLBACK_MODEL_2", "gpt-4o-mini")
    if openai_key:
        try:
            chain.append((openai_model, _OpenAIAdapter(openai_key)))
        except RuntimeError as e:
            logger.warning(f"[LLM] OpenAI adaptör başlatılamadı: {e}")
            chain.append((openai_model, None))
    else:
        chain.append((openai_model, None))

    return chain

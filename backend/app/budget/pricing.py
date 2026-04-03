"""
app/budget/pricing.py — Model birim fiyat tablosu ve token tahmincisi.

Bu modül iki görevi üstlenir:
  1. Her LLM modelinin güncel birim fiyatlarını tutar (USD / token)
  2. Pre-flight check için metin girişinden token sayısını tahmin eder

Token Tahmini Neden Tam Değil?
  - Tiktoken yalnızca OpenAI tokenizer'ını tam destekler.
  - Gemini ve Claude için karakter/token oranı dile göre değişir.
  - Pre-flight check TEMKİNLİ (conservative) tahmin yapar → %20 güvenlik tamponu.
  - Gerçek maliyet, API yanıtındaki token sayısından hesaplanır (record_actual_cost).
"""

import re
import logging

logger = logging.getLogger(__name__)

# ============================================================
# MODEL BİRİM FİYAT TABLOSU
# Kaynak: Resmi API fiyatlandırma sayfaları (2025 Q1)
# Birim: USD / 1 token
# ============================================================

MODEL_PRICING: dict[str, dict[str, float]] = {
    # Gemini 2.5 Flash — Birincil model
    # < 128K token için: $0.075/1M input, $0.30/1M output
    # > 128K token için: $0.15/1M input, $0.60/1M output (long context surcharge)
    "gemini-2.5-flash": {
        "input":  0.075 / 1_000_000,
        "output": 0.300 / 1_000_000,
        "input_long":  0.150 / 1_000_000,   # 128K+ token için
        "output_long": 0.600 / 1_000_000,
        "long_context_threshold": 128_000,
    },
    # Claude Haiku 3.5 — İlk fallback
    "claude-haiku-3-5": {
        "input":  0.800 / 1_000_000,
        "output": 4.000 / 1_000_000,
    },
    # GPT-4o-mini — İkinci fallback
    "gpt-4o-mini": {
        "input":  0.150 / 1_000_000,
        "output": 0.600 / 1_000_000,
    },
}

# Bilinmeyen model için güvenli varsayılan (en pahalı → aşmaya karşı koruma)
_FALLBACK_PRICING = {
    "input":  1.0 / 1_000_000,
    "output": 4.0 / 1_000_000,
}

# Pre-flight güvenlik tamponu: tahmini %20 büyüt
# (Tokenizer farkından kaynaklanabilecek sapmaları karşılar)
ESTIMATION_SAFETY_MARGIN = 1.20


def estimate_token_count(text: str, model: str = "gemini-2.5-flash") -> int:
    """
    Verilen metin için token sayısını tahmin eder.

    Strateji:
      - OpenAI modelleri için: tiktoken (hassas)
      - Diğer modeller için: dile duyarlı karakter/token oranı (yaklaşık)

    Türkçe için not:
      Türkçe, İngilizce'den daha uzun morfolojiye sahiptir.
      GPT ailesinde Türkçe metinler İngilizce'ye göre ~%30-40 daha fazla
      token tüketir. Bu yüzden Türkçe için oranı 3.5 yerine 3.0 kullanıyoruz.

    Args:
        text:  Token sayılacak metin
        model: Tahmin için kullanılacak model adı

    Returns:
        Tahmini token sayısı (SAFETY_MARGIN uygulanmamış — guard'da uygulanır)
    """
    if not text:
        return 0

    # --- OpenAI Modelleri: tiktoken ile hassas sayım ---
    if model.startswith("gpt-"):
        try:
            import tiktoken
            # GPT-4o-mini için cl100k_base encoding
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except ImportError:
            logger.warning("[PRICING] tiktoken yüklü değil, karakter tahminine geçiliyor.")
        except Exception as e:
            logger.warning(f"[PRICING] tiktoken hatası: {e} — karakter tahminine geçiliyor.")

    # --- Gemini ve Claude: Dile Duyarlı Karakter Tahmini ---
    return _estimate_by_character_ratio(text)


def _estimate_by_character_ratio(text: str) -> int:
    """
    Metnin dil yapısına göre token sayısını tahmin eder.

    Oranlar:
      - Saf Latin/İngilizce : 4.0 karakter/token
      - Türkçe (Latin alfabe): 3.2 karakter/token (uzun kelimeler nedeniyle)
      - Karma (TR+EN)        : 3.5 karakter/token
      - Sayı/sembol yoğun   : 2.5 karakter/token (her sembol ~1 token)
    """
    if not text:
        return 0

    total_chars = len(text)

    # Türkçe karakter yoğunluğunu kontrol et
    turkish_chars = set("çğışöüÇĞİŞÖÜ")
    turkish_count = sum(1 for c in text if c in turkish_chars)
    turkish_ratio = turkish_count / max(total_chars, 1)

    if turkish_ratio > 0.02:
        # Türkçe ağırlıklı metin — daha fazla token tüketir
        chars_per_token = 3.2
    elif re.search(r"[^\x00-\x7F]", text):
        # Unicode/karma dil
        chars_per_token = 3.5
    else:
        # Saf ASCII/İngilizce
        chars_per_token = 4.0

    return max(1, round(total_chars / chars_per_token))


def calculate_estimated_cost(
    token_count: int,
    model: str,
    output_token_estimate: int | None = None,
) -> float:
    """
    Pre-flight check için tahmini maliyet hesaplar (USD).

    Güvenlik Tamponu:
        Hem token sayısı hem de maliyet %20 büyütülür.
        Bu, beklenmedik uzun yanıtların bütçeyi patlatmasını önler.

    Args:
        token_count:           Giriş token sayısı (Tiktoken veya karakter tahmini)
        model:                 Kullanılacak LLM modeli
        output_token_estimate: Beklenen çıktı token sayısı.
                               None ise giriş token'ının %40'ı varsayılır.

    Returns:
        Tahmini toplam maliyet (USD), güvenlik tamponu dahil.
    """
    pricing = MODEL_PRICING.get(model, _FALLBACK_PRICING)

    # Bilinmeyen fiyat yapısını güvenle ele al
    if "input" not in pricing:
        pricing = _FALLBACK_PRICING

    # Uzun bağlam ek ücreti kontrolü (Gemini Flash için)
    long_threshold = pricing.get("long_context_threshold", float("inf"))
    if token_count > long_threshold:
        input_price  = pricing.get("input_long", pricing["input"])
        output_price = pricing.get("output_long", pricing["output"])
    else:
        input_price  = pricing["input"]
        output_price = pricing["output"]

    # Çıktı token tahmini: belirtilmemişse giriş'in %40'ı
    if output_token_estimate is None:
        output_token_estimate = max(100, round(token_count * 0.40))

    # Ham maliyet
    raw_cost = (token_count * input_price) + (output_token_estimate * output_price)

    # Güvenlik tamponu uygula
    return round(raw_cost * ESTIMATION_SAFETY_MARGIN, 8)


def calculate_actual_cost(
    prompt_tokens: int,
    output_tokens: int,
    model: str,
) -> float:
    """
    API yanıtından dönen gerçek token sayılarıyla kesin maliyeti hesaplar.
    record_actual_cost() tarafından çağrılır.

    Args:
        prompt_tokens: API'nin raporladığı giriş token sayısı
        output_tokens: API'nin raporladığı çıktı token sayısı
        model:         Kullanılan model adı

    Returns:
        Gerçek maliyet (USD), güvenlik tamponu UYGULANMAZ.
    """
    pricing = MODEL_PRICING.get(model, _FALLBACK_PRICING)

    long_threshold = pricing.get("long_context_threshold", float("inf"))
    if prompt_tokens > long_threshold:
        input_price  = pricing.get("input_long", pricing.get("input", 0))
        output_price = pricing.get("output_long", pricing.get("output", 0))
    else:
        input_price  = pricing.get("input", 0)
        output_price = pricing.get("output", 0)

    return round((prompt_tokens * input_price) + (output_tokens * output_price), 8)


def get_model_display_name(model: str) -> str:
    """Dashboard'da gösterim için model adını formatlar."""
    display_names = {
        "gemini-2.5-flash": "Gemini 2.5 Flash",
        "claude-haiku-3-5": "Claude Haiku 3.5",
        "gpt-4o-mini":      "GPT-4o-mini",
    }
    return display_names.get(model, model)

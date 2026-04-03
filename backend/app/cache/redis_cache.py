"""
app/cache/redis_cache.py — Redis önbellek yöneticisi.

Bu modül Redis bağlantısını yönetir ve uygulama genelinde
önbellekleme için bir arayüz sunar. Redis kullanılabilir değilse
tüm operasyonlar sessizce başarısız olur — önbellek her zaman
opsiyoneldir, asla kritik yol üzerinde değildir.

Kullanım Alanları:
  - YouTube transkript metinleri (7 gün)
  - LLM yanıt önbellekleme (varsa, isteğe bağlı)
  - Görev kilit mekanizmaları (duplicate task engeli)
"""

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Lazy import — Redis bağlantısını ilk kullanımda kur
_redis_client = None
_redis_available = None   # None: henüz test edilmedi


def _get_redis():
    """
    Redis istemcisini döndürür (lazy init).
    Bağlantı başarısızsa None döner — uygulama çökmez.
    """
    global _redis_client, _redis_available

    # Daha önce başarısız olduysa tekrar deneme
    if _redis_available is False:
        return None

    if _redis_client is not None:
        return _redis_client

    try:
        import redis
        from flask import current_app
        redis_url = current_app.config.get("REDIS_URL", "redis://127.0.0.1:6379/0")
        client = redis.from_url(
            redis_url,
            decode_responses  = True,   # Byte değil string dönsün
            socket_timeout    = 2,
            socket_connect_timeout = 2,
        )
        # Bağlantıyı test et
        client.ping()
        _redis_client    = client
        _redis_available = True
        logger.info(f"[REDIS] Bağlantı kuruldu: {redis_url}")
        return client

    except ImportError:
        logger.warning("[REDIS] redis kütüphanesi yüklü değil. Cache devre dışı.")
        _redis_available = False
        return None

    except Exception as e:
        logger.warning(f"[REDIS] Bağlantı hatası: {e}. Cache devre dışı.")
        _redis_available = False
        return None


# ─────────────────────────────────────────────────────────────
# TEMEL OPERASYONLAR
# ─────────────────────────────────────────────────────────────

def cache_get(key: str) -> Optional[Any]:
    """
    Redis'ten değer okur. JSON otomatik deserialize edilir.

    Returns:
        Değer (dict/list/str) veya None (cache miss veya Redis yok)
    """
    try:
        client = _get_redis()
        if client is None:
            return None
        raw = client.get(key)
        if raw is None:
            return None
        # JSON decode dene — string ise doğrudan döndür
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw
    except Exception as e:
        logger.debug(f"[REDIS] cache_get hata | key={key}: {e}")
        return None


def cache_set(key: str, value: Any, ttl: int = 3600) -> bool:
    """
    Redis'e değer yazar. Dict/list JSON'a dönüştürülür.

    Args:
        key:   Redis anahtarı
        value: Saklanacak değer
        ttl:   Süre sonu (saniye). Varsayılan: 1 saat.

    Returns:
        True → başarılı, False → hata/Redis yok
    """
    try:
        client = _get_redis()
        if client is None:
            return False
        if isinstance(value, (dict, list)):
            raw = json.dumps(value, ensure_ascii=False)
        else:
            raw = str(value)
        client.setex(key, ttl, raw)
        return True
    except Exception as e:
        logger.debug(f"[REDIS] cache_set hata | key={key}: {e}")
        return False


def cache_delete(key: str) -> bool:
    """Belirtilen anahtarı Redis'ten siler."""
    try:
        client = _get_redis()
        if client is None:
            return False
        client.delete(key)
        return True
    except Exception as e:
        logger.debug(f"[REDIS] cache_delete hata | key={key}: {e}")
        return False


def cache_exists(key: str) -> bool:
    """Anahtarın Redis'te mevcut olup olmadığını kontrol eder."""
    try:
        client = _get_redis()
        if client is None:
            return False
        return bool(client.exists(key))
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────
# UYGULAMA ÖZEL YARDIMCILAR
# ─────────────────────────────────────────────────────────────

# TTL sabitleri
TTL_TRANSCRIPT   = 7 * 24 * 3600   # 7 gün — video pek değişmez
TTL_TASK_LOCK    = 5 * 60           # 5 dakika — aynı birden fazla görevi engelle
TTL_LLM_CACHE    = 24 * 3600       # 24 saat — aynı prompt önbellekleme


def get_transcript_cache(video_id: str) -> Optional[str]:
    """YouTube transkriptini önbellekten alır."""
    return cache_get(f"yt:transcript:{video_id}")


def set_transcript_cache(video_id: str, transcript_text: str) -> bool:
    """YouTube transkriptini 7 gün boyunca önbelleğe alır."""
    return cache_set(f"yt:transcript:{video_id}", transcript_text, ttl=TTL_TRANSCRIPT)


def acquire_task_lock(lock_key: str, ttl: int = TTL_TASK_LOCK) -> bool:
    """
    Duplicate görev engelleyici kilit mekanizması.
    Aynı video/konunun eş zamanlı birden fazla işlenmesini önler.

    Kullanım:
        if not acquire_task_lock(f"lock:youtube:{video_id}"):
            raise DuplicateTaskError("Bu video zaten işleniyor.")

    Returns:
        True → kilit alındı (işleme başlanabilir)
        False → kilit mevcuttu (başka bir işlem devam ediyor)
    """
    try:
        client = _get_redis()
        if client is None:
            return True  # Redis yoksa kilidi her zaman "al" — yalancı pozitif
        # SET NX (Not Exists): sadece yoksa oluştur
        result = client.set(lock_key, "1", nx=True, ex=ttl)
        return result is True
    except Exception as e:
        logger.debug(f"[REDIS] acquire_task_lock hata | key={lock_key}: {e}")
        return True  # Hata durumunda kilidi "al" — işlemi engelleme


def release_task_lock(lock_key: str) -> None:
    """Görev kilidini serbest bırakır (görev tamamlanınca)."""
    cache_delete(lock_key)


def is_redis_healthy() -> bool:
    """Redis bağlantı durumunu test eder (health check için)."""
    try:
        client = _get_redis()
        if client is None:
            return False
        client.ping()
        return True
    except Exception:
        return False

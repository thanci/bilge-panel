"""
app/xenforo/client.py — XenForo 2.x REST API İstemcisi.

XenForo API Kimlik Doğrulama Mimarisi:
═══════════════════════════════════════
  Her istek iki header taşır:
    XF-Api-Key:  <super_admin_api_key>        -- Her zaman gönderilir
    XF-Api-User: <admin_user_id>              -- Konuyu hangi kullanıcı adına aç

  Super Admin API Key Oluşturma:
    XenForo Admin Panel → Araçlar → API anahtarları → Yeni ekle
    Tür: "Super user" (tam yetki)
    Güvenlik: Yalnızca sunucu IP'lerini beyaz listeye alın

  Önemli Teknik Detay:
    XenForo REST API, POST/PATCH isteklerinde JSON DEĞİL,
    application/x-www-form-urlencoded formatı bekler.
    GET isteklerinde JSON yanıt döner.

  Rate Limiting:
    XenForo'nun yerleşik rate limiti yoktur, ancak
    aşırı yük sunucuyu etkileyebilir. Celery concurrency=2 ile sınırlandırılmış.
    Üretimde Apache mod_ratelimit eklenmesi önerilir.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Kullanım:
    with XenForoClient.from_config() as xf:
        node = xf.nodes.get(node_id=5)
        thread = xf.threads.create(
            node_id=5,
            title="Yapay Zeka ve Bilgelik",
            message="[B]Giriş[/B]\n\nBu makale ...",
            tags=["yapay-zeka", "felsefe"],
        )
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
import time
from typing import Optional, Union

import requests
from flask import current_app

from app.xenforo.exceptions import (
    XenForoError,
    XenForoAuthError,
    XenForoForbiddenError,
    XenForoValidationError,
    XenForoNotFoundError,
    XenForoRateLimitError,
    XenForoServerError,
    XenForoConnectionError,
)

logger = logging.getLogger(__name__)

# İstek zaman aşımı: (bağlantı_kurma, okuma) saniye
_TIMEOUTS = (10, 30)

# Retry ayarları — sadece 5xx ve bağlantı hataları için
_MAX_RETRIES  = 2
_RETRY_BACKOFF = [3, 6]   # saniye

# Yük tipi — XF POST/PATCH form-encoded bekler
_FORM_HEADERS = {"Content-Type": "application/x-www-form-urlencoded"}


class XenForoClient:
    """
    XenForo 2.x REST API istemcisi.

    Bu sınıf doğrudan kullanılmaz. Bunun yerine context manager olarak açın:
        with XenForoClient.from_config() as xf:
            xf.threads.create(...)

    Özellikler:
        nodes:   NodeManager — forum hiyerarşisi yönetimi
        threads: ThreadManager — konu oluşturma ve okuma
    """

    def __init__(
        self,
        base_url:   str,
        api_key:    str,
        user_id:    int = 1,
        verify_ssl: bool = True,
    ):
        """
        Args:
            base_url:   Forum kök URL'si (örn: https://bilgeyolcu.com)
            api_key:    Super Admin API anahtarı
            user_id:    XF konuları hangi kullanıcı adına "aç" (varsayılan: 1 = admin)
            verify_ssl: SSL sertifikasını doğrula (üretimde True olsun)
        """
        self.api_base = f"{base_url.rstrip('/')}/api"
        self._session = requests.Session()

        # Kimlik doğrulama header'ları — tüm isteklerde sabit
        self._session.headers.update({
            "XF-Api-Key":  api_key,
            "XF-Api-User": str(user_id),
            "User-Agent":  "BilgeYolcu-Panel/1.0 (Flask)",
        })

        # SSL doğrulama
        self._session.verify = verify_ssl

        # Her iki Manager da aynı client örneğini kullanır
        from app.xenforo.nodes   import NodeManager
        from app.xenforo.threads import ThreadManager

        self.nodes   = NodeManager(self)
        self.threads = ThreadManager(self)

        logger.debug(f"[XF] Client başlatıldı: {self.api_base} user_id={user_id}")

    @classmethod
    def from_config(cls) -> "XenForoClient":
        """
        Flask app config'inden XenForoClient örneği oluşturur.
        Celery task'ları ve Flask route'ları bu metodu kullanır.

        Gerekli config anahtarları (.env'den):
            XENFORO_BASE_URL
            XENFORO_API_KEY
            XENFORO_ADMIN_USER_ID  (varsayılan: 1)

        Raises:
            ValueError: Zorunlu config değerleri eksikse
        """
        base_url = current_app.config.get("XENFORO_BASE_URL", "").rstrip("/")
        api_key  = current_app.config.get("XENFORO_API_KEY", "")
        user_id  = int(current_app.config.get("XENFORO_ADMIN_USER_ID", 1))
        ssl      = current_app.config.get("XENFORO_VERIFY_SSL", True)

        if not base_url or not api_key:
            raise ValueError(
                "XENFORO_BASE_URL ve XENFORO_API_KEY .env'den okunmalı. "
                "Bu değerleri ayarlamadan XenForo özelliklerini kullanamazsınız."
            )

        return cls(
            base_url   = base_url,
            api_key    = api_key,
            user_id    = user_id,
            verify_ssl = ssl,
        )

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        """HTTP oturumunu kapat (bağlantı havuzunu serbest bırak)."""
        self._session.close()

    # ─────────────────────────────────────────────────────────
    # TEMEL HTTP METotları
    # ─────────────────────────────────────────────────────────

    def get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """GET isteği gönderir. Parametreler URL query string'e eklenir."""
        return self._request("GET", endpoint, params=params)

    def post(self, endpoint: str, data: dict) -> dict:
        """
        POST isteği gönderir.
        data: form-encoded olarak gönderilir (XF POST formatı).
        """
        return self._request("POST", endpoint, data=data)

    def patch(self, endpoint: str, data: dict) -> dict:
        """PATCH isteği gönderir (kaynak güncelleme)."""
        return self._request("PATCH", endpoint, data=data)

    def delete(self, endpoint: str) -> dict:
        """DELETE isteği gönderir."""
        return self._request("DELETE", endpoint)

    # ─────────────────────────────────────────────────────────
    # İÇ: İSTEK YÖNETİCİSİ
    # ─────────────────────────────────────────────────────────

    def _request(
        self,
        method:   str,
        endpoint: str,
        params:   Optional[dict] = None,
        data:     Optional[Union[dict, list]] = None,
    ) -> dict:
        """
        Tüm HTTP isteklerinin geçtiği merkezi nokta.

        İşlev:
          1. URL inşa et
          2. İsteği gönder (retry mantığıyla)
          3. HTTP durum kodunu XenForo hata sınıfına çevir
          4. JSON yanıtını döndür

        Args:
            method:   HTTP metodu (GET, POST, PATCH, DELETE)
            endpoint: API endpoint (/ ile başlayabilir veya başlamayabilir)
            params:   URL sorgu parametreleri (sadece GET)
            data:     Form verisi (POST/PATCH) — dict veya [(k,v)] listesi

        Returns:
            XenForo JSON yanıtı (dict)

        Raises:
            XenForo* exceptions (bkz. exceptions.py)
        """
        url = f"{self.api_base}/{endpoint.lstrip('/')}"

        last_error: Optional[Exception] = None

        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = self._session.request(
                    method  = method.upper(),
                    url     = url,
                    params  = params,
                    data    = data,
                    headers = _FORM_HEADERS if method.upper() in ("POST", "PATCH") else {},
                    timeout = _TIMEOUTS,
                )
                return self._parse_response(resp, method, url)

            except (XenForoAuthError, XenForoForbiddenError,
                    XenForoValidationError, XenForoNotFoundError) as e:
                # Bu hatalar deterministik — retry anlamsız
                raise

            except (XenForoServerError, XenForoConnectionError) as e:
                last_error = e
                if attempt < _MAX_RETRIES:
                    wait = _RETRY_BACKOFF[attempt]
                    logger.warning(
                        f"[XF] {method} {endpoint} — {e} | "
                        f"{wait}s sonra yeniden denenecek "
                        f"(deneme {attempt + 1}/{_MAX_RETRIES})"
                    )
                    time.sleep(wait)
                else:
                    raise

            except requests.exceptions.SSLError as e:
                raise XenForoConnectionError(
                    f"SSL doğrulama hatası: {e}. "
                    "XENFORO_VERIFY_SSL=False ile geçici olarak devre dışı bırakabilirsiniz.",
                    status_code=0,
                )
            except requests.exceptions.Timeout:
                raise XenForoConnectionError(
                    f"İstek zaman aşımı ({_TIMEOUTS[1]}s): {url}",
                    status_code=0,
                )
            except requests.exceptions.ConnectionError as e:
                raise XenForoConnectionError(
                    f"Bağlantı hatası — XenForo'ya erişilemiyor: {e}",
                    status_code=0,
                )

        raise last_error or XenForoError("Bilinmeyen hata")

    def _parse_response(
        self,
        resp: requests.Response,
        method: str,
        url: str,
    ) -> dict:
        """
        HTTP yanıtını işler ve uygun exception'ı fırlatır.

        XenForo başarılı yanıtlarda HTTP 200 döner.
        Hata yanıtları da HTTP 200 ile gelebilir (XF 2.x özelliği) —
        bu yüzden JSON body'deki "status" alanını kontrol ederiz.
        """
        status = resp.status_code

        # JSON parse dene
        try:
            body = resp.json()
        except ValueError:
            body = {"status": "error", "errors": [{"code": "invalid_json",
                    "message": resp.text[:200]}]}

        logger.debug(f"[XF] {method} {url} → {status}")

        # ── HTTP hata kodlarını işle ────────────────────────
        if status == 401:
            raise XenForoAuthError(
                "API anahtarı geçersiz veya eksik.",
                status_code=401,
                xf_errors=body.get("errors", []),
            )

        if status == 403:
            errors    = body.get("errors", [])
            err_msg   = errors[0].get("message", "İzin reddedildi.") if errors else "İzin reddedildi."
            raise XenForoForbiddenError(err_msg, status_code=403, xf_errors=errors)

        if status == 404:
            raise XenForoNotFoundError(
                f"Kaynak bulunamadı: {url}",
                status_code=404,
                xf_errors=body.get("errors", []),
            )

        if status == 429:
            raise XenForoRateLimitError(
                "XenForo rate limit: çok fazla istek.",
                status_code=429,
                xf_errors=body.get("errors", []),
            )

        if status >= 500:
            raise XenForoServerError(
                f"XenForo sunucu hatası: HTTP {status}",
                status_code=status,
                xf_errors=body.get("errors", []),
            )

        # ── XenForo uygulama düzeyinde hata (HTTP 200 ama status:error) ──
        if body.get("status") == "error":
            errors  = body.get("errors", [])
            msg     = errors[0].get("message", "Bilinmeyen XF hatası.") if errors else str(body)
            code    = errors[0].get("code", "") if errors else ""

            # Hata koduna göre exception seç
            if code in ("permission_denied", "not_allowed", "oauth_scope_missing"):
                raise XenForoForbiddenError(msg, status_code=status, xf_errors=errors)
            if code in ("api_key_not_found", "invalid_api_key"):
                raise XenForoAuthError(msg, status_code=status, xf_errors=errors)

            # Genel doğrulama hatası
            raise XenForoValidationError(
                msg,
                status_code=status or 400,
                xf_errors=errors,
            )

        return body

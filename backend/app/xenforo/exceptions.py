"""
app/xenforo/exceptions.py — XenForo API hata hiyerarşisi.

XenForo 2.x REST API'si farklı hata kodları döndürür.
Bu modül her hata tipini ayrı bir sınıfa dönüştürür;
böylece Celery task'ları ve Flask route'ları doğru davranışı seçebilir.

XenForo API hata formatı (JSON):
  {
    "status": "error",
    "errors": [
      {"code": "permission_denied", "message": "...", "params": []}
    ]
  }
"""


class XenForoError(Exception):
    """Tüm XenForo API hatalarının base class'ı."""

    def __init__(self, message: str = "", status_code: int = 0, xf_errors: list = None):
        super().__init__(message)
        self.status_code = status_code
        self.xf_errors   = xf_errors or []    # XF'in döndürdüğü errors listesi

    def __str__(self):
        if self.xf_errors:
            codes = ", ".join(e.get("code", "?") for e in self.xf_errors)
            return f"[XF-{self.status_code}] {codes}: {super().__str__()}"
        return f"[XF-{self.status_code}] {super().__str__()}"

    def to_dict(self) -> dict:
        """Flask API yanıtı için sözlük formata çevir."""
        return {
            "error":       "xenforo_error",
            "status_code": self.status_code,
            "message":     str(self),
            "xf_errors":   self.xf_errors,
        }


class XenForoAuthError(XenForoError):
    """
    HTTP 401 — API anahtarı geçersiz veya eksik.
    Çözüm: XENFORO_API_KEY env değerini kontrol et.
    RETRY YAPMA — farklı bir KEY ile deneme anlamsız.
    """
    pass


class XenForoForbiddenError(XenForoError):
    """
    HTTP 403 — İzin reddedildi.
    Neden oluşur:
      - API anahtarı Super Admin değil
      - Belirtilen node'a erişim yok
      - Kullanıcı (XF-Api-User) bu işlemi yapamaz
    Çözüm: XenForo Admin Panel → API anahtarı yetkilerini kontrol et.
    RETRY YAPMA.
    """
    pass


class XenForoValidationError(XenForoError):
    """
    HTTP 400 — Veri doğrulama hatası.
    XenForo, eksik alan veya geçersiz veri gönderildiğinde bu hatayı döner.
    xf_errors alanında hangi alanların hatalı olduğu belirtilir.
    RETRY YAPARSAN aynı hata — payload'u düzelt.
    """
    pass


class XenForoNotFoundError(XenForoError):
    """
    HTTP 404 — Kaynak bulunamadı.
    Neden oluşur: Hatalı node_id, thread_id veya post_id.
    RETRY YAPMA.
    """
    pass


class XenForoRateLimitError(XenForoError):
    """
    HTTP 429 — İstek limiti aşıldı.
    Celery task'larında exponential backoff ile retry yapılabilir.
    Retry GÜVENLİDİR (idempotent olmayan thread oluşturma için dikkat).
    """
    pass


class XenForoServerError(XenForoError):
    """
    HTTP 5xx — XenForo sunucu hatası.
    Genellikle geçici. Kısa bekleyip retry yapılabilir.
    """
    pass


class XenForoConnectionError(XenForoError):
    """
    Ağ bağlantısı kurulamadı — DNS, timeout, SSL hatası.
    Retry yapılabilir (çoğunlukla geçici).
    """
    pass

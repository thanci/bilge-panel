"""
app/ssh/exceptions.py — SSH operasyonu hata hiyerarşisi.
"""


class SSHError(Exception):
    """Tüm SSH hatalarının base class'ı."""

    def __init__(self, message: str = "", exit_code: int = -1):
        super().__init__(message)
        self.exit_code = exit_code

    def to_dict(self) -> dict:
        return {"error": type(self).__name__, "message": str(self)}


class SSHConnectionError(SSHError):
    """
    Sunucuya bağlanılamadı.
    Neden: yanlış host/port, firewall, ağ kesintisi.
    Retry GÜVENLİ (bağlantı kurulmadı, komut çalışmadı).
    """
    pass


class SSHAuthError(SSHError):
    """
    Kimlik doğrulama başarısız.
    Neden: yanlış şifre veya özel anahtar.
    RETRY YAPMA (farklı kimlik bilgisi gerekmeden anlamsız).
    """
    pass


class SSHCommandError(SSHError):
    """
    SSH komutu sıfırdan farklı exit code döndürdü.
    stderr içeriği mesaja eklenir.
    exit_code: Unix exit kodu
    """

    def __init__(self, message: str, exit_code: int, stderr: str = ""):
        super().__init__(message, exit_code)
        self.stderr = stderr

    def to_dict(self) -> dict:
        return {
            "error":     "SSHCommandError",
            "message":   str(self),
            "exit_code": self.exit_code,
            "stderr":    self.stderr,
        }


class SSHTimeoutError(SSHError):
    """Komut zaman aşımına uğradı. Retry DİKKATLİ yapılmalı (idempotent değilse)."""
    pass


class PathTraversalError(SSHError):
    """
    Güvenli dizin dışına erişim denemesi tespit edildi.
    RETRY YAPMA — bu bir güvenlik ihlali girişimi.
    """
    pass


class SSHFileError(SSHError):
    """SFTP dosya okuma/yazma hatası."""
    pass

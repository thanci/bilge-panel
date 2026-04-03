"""
app/theme/editor.py — XenForo Tema Dosyası Editörü.

styles/ dizinindeki dosyalar (LESS, HTML/Twig, PHP, CSS) SSH üzerinden
okunur ve yazılır. Her yazma işleminden önce otomatik .bak yedeği alınır.

Güvenlik:
  - Tüm dosya yolları XENFORO_WEBROOT/styles/ diziniyle başlamak zorunda
  - Path traversal koruması: SSHClient.validate_path() kullanılır
  - ALLOWED_EXTENSIONS: sadece tema dosyaları düzenlerlebilir
  - PHP include/require komutları filtrelenmez — admin yetkisi gerektirir

XenForo Styles Dizin Yapısı:
  public_html/
  ├── styles/
  │   ├── {STYLE_ID}/
  │   │   ├── xenforo/          ← Core template overrides
  │   │   ├── public/           ← CSS, JS, images
  │   │   └── less/             ← LESS kaynak dosyaları
  │   └── ...
  └── src/
      └── XF/                   ← PHP kaynak (dikkatli olun!)
"""

import logging
import os
from typing import Optional

from app.ssh.client import SSHClient
from app.ssh.exceptions import PathTraversalError, SSHFileError

logger = logging.getLogger(__name__)

# Düzenlenebilir uzantılar (güvenlik katmanı)
ALLOWED_EXTENSIONS = {
    ".less", ".css", ".html", ".tpl", ".php",
    ".js",   ".json", ".xml",  ".txt", ".md",
}

# Düzenlenmesini otomatik REDDEDEN yol desenleri
BLOCKED_PATH_PATTERNS = [
    "/config.php",      # Forum DB şifresi
    "/install/",        # Kurulum dizini
    "/src/vendor/",     # Composer bağımlılıkları
]


def _get_styles_base() -> str:
    """styles/ dizininin mutlak yolunu döndürür."""
    from flask import current_app
    webroot = current_app.config.get("XENFORO_WEBROOT", "").rstrip("/")
    if not webroot:
        raise ValueError("XENFORO_WEBROOT .env'de tanımlı değil.")
    return f"{webroot}/styles"


def _validate_theme_path(path: str) -> str:
    """
    İstenen dosya yolunu güvenli styles/ dizininde doğrular.
    Path traversal ve yasaklı yolları reddeder.
    """
    base = _get_styles_base()

    try:
        safe_path = SSHClient.validate_path(path, base)
    except PathTraversalError:
        raise

    # Uzantı kontrolü
    _, ext = os.path.splitext(safe_path.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise PermissionError(
            f"Bu uzantı düzenlenemez: '{ext}'. "
            f"İzin verilen: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # Yasaklı yol deseni kontrolü
    for pattern in BLOCKED_PATH_PATTERNS:
        if pattern in safe_path:
            raise PermissionError(
                f"Bu yol düzenleme için yasaklanmış: '{pattern}'"
            )

    return safe_path


def list_style_files(
    ssh:          SSHClient,
    style_path:   str = "",
    recursive:    bool = True,
) -> list[dict]:
    """
    styles/ dizinindeki (veya alt dizinindeki) dosyaları listeler.

    Args:
        ssh:          Bağlı SSH istemcisi
        style_path:   styles/ altındaki alt yol (örn: "" veya "1/less")
        recursive:    Alt dizinlere de gir

    Returns:
        [{name, path, size, is_dir, mtime, extension}, ...]
    """
    base = _get_styles_base()
    target = f"{base}/{style_path.lstrip('/')}" if style_path else base

    # Güvenlik: target hâlâ base altında mı?
    SSHClient.validate_path(style_path or ".", base)

    files = ssh.list_dir(target, recursive=recursive)

    # Uzantı filtresi (sadece bilinen dosya tipleri listele)
    result = []
    for f in files:
        _, ext = os.path.splitext(f["name"].lower())
        f["extension"] = ext
        # Dizinleri her zaman ekle (navigasyon için)
        if f["is_dir"] or ext in ALLOWED_EXTENSIONS:
            result.append(f)

    return result


def read_style_file(ssh: SSHClient, path: str) -> dict:
    """
    Tema dosyasını okur.

    Args:
        ssh:  Bağlı SSH istemcisi
        path: styles/ dizinine göre veya mutlak yol

    Returns:
        {"path": "...", "content": "...", "extension": ".less", "size": 1234}
    """
    safe_path = _validate_theme_path(path)

    content = ssh.read_file(safe_path)

    _, ext = os.path.splitext(safe_path)
    return {
        "path":      safe_path,
        "content":   content,
        "extension": ext.lower(),
        "size":      len(content.encode("utf-8")),
    }


def write_style_file(
    ssh:     SSHClient,
    path:    str,
    content: str,
    backup:  bool = True,
) -> dict:
    """
    Tema dosyasını yazar.
    Yazma öncesi otomatik .bak yedeği alır.

    Args:
        ssh:     Bağlı SSH istemcisi
        path:    Dosya yolu (styles/ altında)
        content: Yeni içerik
        backup:  True ise yazma öncesi .bak oluştur

    Returns:
        {"path": "...", "backup_path": "...", "bytes_written": 1234}
    """
    safe_path  = _validate_theme_path(path)
    backup_path = None

    if backup:
        try:
            backup_path = ssh.backup_file(safe_path)
            logger.info(f"[THEME] Yedek alındı: {backup_path}")
        except SSHFileError as e:
            # Dosya henüz yoksa yedek alamayız — normal
            if "bulunamadı" not in str(e).lower():
                raise

    ssh.write_file(safe_path, content)
    bytes_written = len(content.encode("utf-8"))

    logger.info(f"[THEME] Dosya yazıldı: {safe_path} ({bytes_written}B)")
    return {
        "path":          safe_path,
        "backup_path":   backup_path,
        "bytes_written": bytes_written,
    }


def clear_theme_cache(ssh: SSHClient) -> dict:
    """
    XenForo template ve addon önbelleklerini temizler.
    Dosya düzenleme sonrası çağrılmalıdır.

    Returns:
        {"template_recompile": "...", "addon_rebuild": "..."}
    """
    from app.updater.xf_updater import rebuild_templates, rebuild_addons

    results = {}
    try:
        out, _, _ = rebuild_templates(ssh)
        results["template_recompile"] = out.strip()[:500] or "Tamamlandı"
    except Exception as e:
        results["template_recompile"] = f"HATA: {e}"

    try:
        out, _, _ = rebuild_addons(ssh)
        results["addon_rebuild"] = out.strip()[:500] or "Tamamlandı"
    except Exception as e:
        results["addon_rebuild"] = f"HATA: {e}"

    logger.info(f"[THEME] Önbellek temizlendi: {results}")
    return results

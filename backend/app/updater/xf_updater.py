"""
app/updater/xf_updater.py — XenForo Fail-Safe Güncelleme Pipeline.

Pipeline sırası (ve kritiklik düzeyi):
═══════════════════════════════════════════════════════════════════
  ADIM A — Yedekleme (KRİTİK — başarısız olursa ABORT)
    A1. mysqldump ile veritabanı yedeği
    A2. tar ile public_html yedeği
    ▶ Her ikisi de başarılı olmalıdır, biri bile başarısız olursa ABORT.

  ADIM B — Bakım Modunu Aç
    php cmd.php xf:maintenance-start
    ▶ Hata varsa ABORT (forum beklenmedik durumda kalmasın).

  ADIM C — XenForo Yükseltme
    php cmd.php xf:upgrade
    ▶ Hata varsa → Bakım modunu kapat → hata fırlat (rollback yok — XF atomic upgrade).
    ▶ Başarısız upgrade genellikle dosya bütünlüğünde sorun demektir.

  ADIM D — Bakım Modunu Kapat
    php cmd.php xf:maintenance-end
    ▶ Zorunlu — bakım modu açık kalırsa site erişilemez.
    ▶ Adım C başarısız bile olsa bu adım çalıştırılır (finally).

  SONUÇ — Her adımın çıktısı SSE stream'e yazılır.
═══════════════════════════════════════════════════════════════════

İlerleyen XF sürümlerinde CLI komutları değişebilir:
  - xf:maintenance-start / xf:maintenance-end
  - xf:upgrade
  - xf:template-recompile
  - xf:addon-rebuild

Bunları .env ile override etmek için SSH_XF_CMD_* değişkenleri kullanılır.
"""

import datetime
import json
import logging

from flask import current_app

from app.ssh.client import SSHClient
from app.ssh.exceptions import SSHCommandError, SSHConnectionError

logger = logging.getLogger(__name__)


class UpgradeAbortedError(Exception):
    """
    Güncelleme güvenli olmayan bir noktada iptal edildi.
    Yedekleme başarısız olduğunda fırlatılır.
    """
    pass


def _cfg(key: str, default: str = "") -> str:
    """Flask config'den değer okur."""
    return current_app.config.get(key, default)


def _ts() -> str:
    """Yedek dosya adları için zaman damgası."""
    return datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def _emit(stream: str, line: str) -> str:
    """SSE JSON satırı üretir."""
    return json.dumps({"stream": stream, "line": line})


# ════════════════════════════════════════════════════════════════
# ANA PIPELINE
# ════════════════════════════════════════════════════════════════

def run_upgrade_pipeline():
    """
    XenForo yükseltme pipeline'ını çalıştırır ve her adımın
    çıktısını gerçek zamanlı olarak yield'lar.

    Bu bir generator fonksiyonudur; Flask SSE endpoint'inden çağrılır.

    Yields:
        str — JSON string (SSE data satırı)

    Raises:
        UpgradeAbortedError: Yedekleme başarısız (bağlantı kesilir)
    """
    webroot    = _cfg("XENFORO_WEBROOT")
    backup_dir = _cfg("BACKUP_DIR")
    db_host    = _cfg("MYSQL_HOST",     "localhost")
    db_user    = _cfg("MYSQL_USER")
    db_pass    = _cfg("MYSQL_PASSWORD")
    db_name    = _cfg("MYSQL_DATABASE")
    php_bin    = _cfg("SSH_PHP_BIN",    "php")

    # XF CLI komutları (.env ile override edilebilir)
    cmd_upgrade     = _cfg("SSH_XF_UPGRADE_CMD",    f"{php_bin} {webroot}/cmd.php xf:upgrade")
    cmd_maint_start = _cfg("SSH_XF_MAINT_ON_CMD",   f"{php_bin} {webroot}/cmd.php xf:maintenance-start")
    cmd_maint_end   = _cfg("SSH_XF_MAINT_OFF_CMD",  f"{php_bin} {webroot}/cmd.php xf:maintenance-end")

    ts = _ts()

    with SSHClient.from_config() as ssh:

        # ── ADIM A: Yedekleme ────────────────────────────────────
        yield _emit("info", "═" * 50)
        yield _emit("info", "ADIM A — Yedekleme Başlıyor (KRİTİK)")
        yield _emit("info", "═" * 50)

        # A1: Veritabanı yedeği
        db_backup_path = f"{backup_dir.rstrip('/')}/db_{db_name}_{ts}.sql.gz"
        db_dump_cmd = (
            f"mysqldump -h {db_host} -u {db_user} -p'{db_pass}' {db_name} "
            f"| gzip > {db_backup_path} && echo 'DB_BACKUP_OK'"
        )

        yield _emit("step", f"A1. Veritabanı yedeği alınıyor → {db_backup_path}")
        try:
            out, err, _ = ssh.exec_command(db_dump_cmd, timeout=300)
            if "DB_BACKUP_OK" not in out:
                raise UpgradeAbortedError(
                    f"mysqldump çıktısı beklenen onayı içermiyor. Stderr: {err}"
                )
            yield _emit("ok", f"✓ Veritabanı yedeği alındı ({db_backup_path})")
        except (SSHCommandError, SSHConnectionError) as e:
            yield _emit("abort", f"✕ VERİTABANI YEDEĞİ BAŞARISIZ — GÜNCELLEME İPTAL! → {e}")
            raise UpgradeAbortedError(f"DB yedeği alınamadı: {e}")

        # A2: public_html tar yedeği
        html_backup_path = f"{backup_dir.rstrip('/')}/public_html_{ts}.tar.gz"
        tar_cmd = (
            f"tar -czf {html_backup_path} -C {webroot} . 2>&1 && echo 'TAR_OK'"
        )

        yield _emit("step", f"A2. Dosya sistemi yedeği alınıyor → {html_backup_path}")
        try:
            out, err, _ = ssh.exec_command(tar_cmd, timeout=600)
            if "TAR_OK" not in out:
                raise UpgradeAbortedError(f"tar çıktısı TAR_OK içermiyor. Çıktı: {out[:200]}")
            yield _emit("ok", f"✓ Dosya sistemi yedeği alındı ({html_backup_path})")
        except (SSHCommandError, SSHConnectionError) as e:
            yield _emit("abort", f"✕ DOSYA YEDEĞİ BAŞARISIZ — GÜNCELLEME İPTAL! → {e}")
            raise UpgradeAbortedError(f"tar yedeği alınamadı: {e}")

        yield _emit("ok", "✓ Tüm yedekler başarıyla alındı. Güncelleme devam ediyor.")

        # ── ADIM B: Bakım Modunu Aç ──────────────────────────────
        yield _emit("info", "═" * 50)
        yield _emit("step", "ADIM B — Bakım Modu Açılıyor")

        try:
            out, _, _ = ssh.exec_command(cmd_maint_start, timeout=30)
            yield _emit("ok", f"✓ Bakım modu açıldı. ({out.strip()[:100]})")
        except SSHCommandError as e:
            yield _emit("abort", f"✕ Bakım modu açılamadı — GÜNCELLEME İPTAL! → {e}")
            raise UpgradeAbortedError(f"Bakım modu açılamadı: {e}")

        # ── ADIM C: XenForo Upgrade ──────────────────────────────
        yield _emit("info", "═" * 50)
        yield _emit("step", "ADIM C — XenForo Yükseltme Çalışıyor (uzun sürebilir…)")

        upgrade_failed = False
        upgrade_error  = None
        try:
            for chunk in ssh.stream_command(cmd_upgrade, timeout=1800):
                yield chunk   # SSE'ye direkt ilet (satır satır)

        except SSHCommandError as e:
            upgrade_failed = True
            upgrade_error  = e
            yield _emit("error", f"✕ xf:upgrade başarısız: {e.stderr[:500]}")
        except Exception as e:
            upgrade_failed = True
            upgrade_error  = e
            yield _emit("error", f"✕ Beklenmedik upgrade hatası: {e}")

        # ── ADIM D: Bakım Modunu Kapat (HER DURUMDA) ────────────
        yield _emit("info", "═" * 50)
        yield _emit("step", "ADIM D — Bakım Modu Kapatılıyor")

        try:
            ssh.exec_command(cmd_maint_end, timeout=30)
            yield _emit("ok", "✓ Bakım modu kapatıldı. Forum erişilebilir.")
        except Exception as e:
            yield _emit("error", f"⚠ Bakım modu kapatılamadı! Manuel müdahale gerekiyor: {e}")

        # ── SONUÇ ────────────────────────────────────────────────
        yield _emit("info", "═" * 50)
        if upgrade_failed:
            yield _emit("error",
                f"✕ Güncelleme başarısız tamamlandı. "
                f"Yedekler şuradadır: {backup_dir}"
            )
            yield json.dumps({"done": True, "success": False, "error": str(upgrade_error)})
        else:
            yield _emit("ok", "✓ XenForo başarıyla güncellendi! 🎉")
            yield json.dumps({"done": True, "success": True})


# ════════════════════════════════════════════════════════════════
# XF CLI YARDIMCI KOMUTLARI
# ════════════════════════════════════════════════════════════════

def rebuild_templates(ssh: SSHClient) -> tuple[str, str, int]:
    """XenForo template cache'ini yeniden derle."""
    webroot = _cfg("XENFORO_WEBROOT")
    php_bin = _cfg("SSH_PHP_BIN", "php")
    cmd = f"{php_bin} {webroot}/cmd.php xf:template-recompile"
    return ssh.exec_command(cmd, timeout=120)


def rebuild_addons(ssh: SSHClient) -> tuple[str, str, int]:
    """XenForo addon'larını yeniden derle."""
    webroot = _cfg("XENFORO_WEBROOT")
    php_bin = _cfg("SSH_PHP_BIN", "php")
    cmd = f"{php_bin} {webroot}/cmd.php xf:addon-rebuild"
    return ssh.exec_command(cmd, timeout=120)


def clear_data_caches(ssh: SSHClient) -> tuple[str, str, int]:
    """XenForo veri önbelleklerini temizle."""
    webroot = _cfg("XENFORO_WEBROOT")
    php_bin = _cfg("SSH_PHP_BIN", "php")
    cmd = f"{php_bin} {webroot}/cmd.php xf:data-cleanup"
    return ssh.exec_command(cmd, timeout=60)

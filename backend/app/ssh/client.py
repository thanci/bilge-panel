"""
app/ssh/client.py — Güvenli Paramiko SSH İstemcisi.

Mimari:
═══════════════════════════════════════════════════════════════════
  Kimlik Doğrulama (öncelik sırasıyla):
    1. Ed25519/RSA özel anahtar (SSH_PRIVATE_KEY_PATH)
    2. Şifre (SSH_PASSWORD)

  Bağlantı Yeniden Deneme:
    Bağlantı koptuğunda (timeout, ağ kesintisi) otomatik yeniden bağlanır.
    Kimlik hatalarında (AuthError) RETRY YAPILMAZ.

  SFTP:
    Dosya okuma/yazma için Paramiko SFTP alt sistemi kullanılır.
    Büyük dosyalar için streaming desteği vardır.

  Güvenlik:
    - Host key doğrulaması (REJECT_POLICY veya WARNING_POLICY)
    - Tüm komut çıktısı 50MB ile sınırlandırılmıştır
    - exec_command() timeout parametresi zorunludur

Kullanım:
    with SSHClient.from_config() as ssh:
        stdout, stderr, code = ssh.exec_command("ls /home/user")
        content = ssh.read_file("/home/user/public_html/config.php")
        for line in ssh.stream_command("php cmd.php xf:upgrade"):
            print(line)
═══════════════════════════════════════════════════════════════════
"""

import io
import logging
import os
import socket
import stat
import time
from typing import Generator, Optional

import paramiko

from app.ssh.exceptions import (
    SSHAuthError,
    SSHCommandError,
    SSHConnectionError,
    SSHFileError,
    SSHTimeoutError,
    PathTraversalError,
)

logger = logging.getLogger(__name__)

# Güvenlik sabitleri
MAX_OUTPUT_BYTES  = 50 * 1024 * 1024   # 50 MB — çıktı sınırı
DEFAULT_TIMEOUT   = 60                  # saniye — exec_command varsayılan
STREAM_TIMEOUT    = 600                 # saniye — xf:upgrade gibi uzun işlemler
CONNECT_TIMEOUT   = 15                  # saniye — bağlantı zaman aşımı
MAX_CONNECT_RETRY = 3
RETRY_BACKOFF     = [3, 6, 12]         # saniye


class SSHClient:
    """
    Paramiko tabanlı SSH ve SFTP istemcisi.

    Doğrudan örneklenebilir, ama `from_config()` ile Flask config'inden
    alınması tercih edilir. Context manager olarak kullanın:

        with SSHClient.from_config() as ssh:
            stdout, _, _ = ssh.exec_command("uname -a")
    """

    def __init__(
        self,
        host:             str,
        port:             int    = 22,
        username:         str    = "root",
        password:         Optional[str] = None,
        private_key_path: Optional[str] = None,
        private_key_pass: Optional[str] = None,
        known_hosts_path: Optional[str] = None,
        connect_timeout:  int    = CONNECT_TIMEOUT,
    ):
        self.host             = host
        self.port             = port
        self.username         = username
        self._password        = password
        self._key_path        = private_key_path
        self._key_passphrase  = private_key_pass
        self._known_hosts     = known_hosts_path
        self._connect_timeout = connect_timeout

        self._client: Optional[paramiko.SSHClient] = None
        self._sftp:   Optional[paramiko.SFTPClient] = None

    # ─────────────────────────────────────────────────────────
    # FACTORY
    # ─────────────────────────────────────────────────────────

    @classmethod
    def from_config(cls) -> "SSHClient":
        """Flask app config'inden SSH istemcisi oluşturur."""
        from flask import current_app as app

        host = app.config.get("SSH_HOST", "")
        port = int(app.config.get("SSH_PORT", 22))
        user = app.config.get("SSH_USERNAME", "root")

        if not host:
            raise SSHConnectionError(
                "SSH_HOST tanımlı değil. .env dosyasını kontrol edin."
            )

        return cls(
            host             = host,
            port             = port,
            username         = user,
            password         = app.config.get("SSH_PASSWORD") or None,
            private_key_path = app.config.get("SSH_PRIVATE_KEY_PATH") or None,
            private_key_pass = app.config.get("SSH_PRIVATE_KEY_PASSPHRASE") or None,
            known_hosts_path = app.config.get("SSH_KNOWN_HOSTS_PATH") or None,
        )

    # ─────────────────────────────────────────────────────────
    # BAĞLANTI YÖNETİMİ
    # ─────────────────────────────────────────────────────────

    def connect(self) -> None:
        """
        SSH bağlantısı kurar.
        Önce özel anahtar, sonra şifre dener.
        Bağlantı kurulamazsa SSHConnectionError veya SSHAuthError fırlatır.
        """
        client = paramiko.SSHClient()

        # Host key politikası
        if self._known_hosts and os.path.exists(self._known_hosts):
            client.load_host_keys(self._known_hosts)
            client.set_missing_host_key_policy(paramiko.RejectPolicy())
        else:
            # WARNING: Üretimde known_hosts kullanın!
            client.set_missing_host_key_policy(paramiko.WarningPolicy())

        connect_kwargs: dict = {
            "hostname":        self.host,
            "port":            self.port,
            "username":        self.username,
            "timeout":         self._connect_timeout,
            "allow_agent":     False,
            "look_for_keys":   False,
        }

        # Kimlik doğrulama: özel anahtar öncelikli
        auth_method = "none"
        if self._key_path and os.path.exists(self._key_path):
            try:
                pkey = self._load_key(self._key_path, self._key_passphrase)
                connect_kwargs["pkey"] = pkey
                auth_method = f"key:{os.path.basename(self._key_path)}"
            except paramiko.ssh_exception.SSHException as e:
                logger.warning(f"[SSH] Anahtar yüklenemedi ({self._key_path}): {e}")
                # Şifreye düş
        
        if "pkey" not in connect_kwargs and self._password:
            connect_kwargs["password"] = self._password
            auth_method = "password"

        try:
            client.connect(**connect_kwargs)
            self._client = client
            logger.info(
                f"[SSH] Bağlandı: {self.username}@{self.host}:{self.port} "
                f"yöntem={auth_method}"
            )
        except paramiko.AuthenticationException as e:
            raise SSHAuthError(
                f"SSH kimlik doğrulama başarısız ({self.username}@{self.host}): {e}"
            )
        except (socket.timeout, socket.error, paramiko.ssh_exception.NoValidConnectionsError) as e:
            raise SSHConnectionError(
                f"SSH bağlantısı kurulamadı ({self.host}:{self.port}): {e}"
            )
        except Exception as e:
            raise SSHConnectionError(f"Beklenmedik SSH hatası: {e}")

    def _load_key(self, path: str, passphrase: Optional[str]) -> paramiko.PKey:
        """Ed25519, RSA veya ECDSA anahtarını yükler."""
        for key_cls in (
            paramiko.Ed25519Key,
            paramiko.RSAKey,
            paramiko.ECDSAKey,
            paramiko.DSSKey,
        ):
            try:
                return key_cls.from_private_key_file(path, password=passphrase)
            except (paramiko.ssh_exception.SSHException, ValueError):
                continue
        raise paramiko.ssh_exception.SSHException(f"Desteklenmeyen anahtar tipi: {path}")

    def ensure_connected(self) -> None:
        """Bağlantı yoksa veya kopmuşsa yeniden bağlanır (retry ile)."""
        if self._client and self._is_alive():
            return

        last_error = None
        for attempt in range(MAX_CONNECT_RETRY):
            try:
                self.connect()
                return
            except SSHAuthError:
                raise   # Auth hatası için retry yok
            except SSHConnectionError as e:
                last_error = e
                if attempt < MAX_CONNECT_RETRY - 1:
                    wait = RETRY_BACKOFF[attempt]
                    logger.warning(f"[SSH] Bağlantı hatası, {wait}s sonra yeniden deneniyor...")
                    time.sleep(wait)

        raise last_error or SSHConnectionError("SSH bağlantısı kurulamadı")

    def _is_alive(self) -> bool:
        """Transport hâlâ aktif mi?"""
        try:
            transport = self._client.get_transport()
            if transport and transport.is_active():
                transport.send_ignore()
                return True
        except Exception:
            pass
        return False

    def get_sftp(self) -> paramiko.SFTPClient:
        """SFTP oturumu döndürür, yoksa oluşturur."""
        if self._sftp and self._sftp.get_channel().get_transport().is_active():
            return self._sftp
        self.ensure_connected()
        self._sftp = self._client.open_sftp()
        return self._sftp

    def close(self) -> None:
        if self._sftp:
            try: self._sftp.close()
            except Exception: pass
        if self._client:
            try: self._client.close()
            except Exception: pass
        logger.debug(f"[SSH] Bağlantı kapatıldı: {self.host}")

    def __enter__(self):
        self.ensure_connected()
        return self

    def __exit__(self, *_):
        self.close()

    # ─────────────────────────────────────────────────────────
    # KOMUT ÇALIŞTIRMA
    # ─────────────────────────────────────────────────────────

    def exec_command(
        self,
        command: str,
        timeout: int = DEFAULT_TIMEOUT,
        env:     Optional[dict] = None,
    ) -> tuple[str, str, int]:
        """
        Tek bir komutu çalıştırır ve tamamlanmasını bekler.

        Args:
            command: Çalıştırılacak shell komutu
            timeout: Saniye cinsinden zaman aşımı
            env:     Ek ortam değişkenleri

        Returns:
            (stdout, stderr, exit_code) — exit_code 0 = başarı

        Raises:
            SSHCommandError: exit_code != 0
            SSHTimeoutError: Zaman aşımı
        """
        self.ensure_connected()
        logger.info(f"[SSH] Komut çalıştırılıyor: {command[:120]}")

        try:
            stdin, stdout, stderr = self._client.exec_command(
                command,
                timeout  = timeout,
                get_pty  = False,
                environment = env,
            )
            stdin.close()

            # Çıktıyı boyut sınırıyla oku
            out_bytes = stdout.read(MAX_OUTPUT_BYTES)
            err_bytes = stderr.read(MAX_OUTPUT_BYTES)
            exit_code  = stdout.channel.recv_exit_status()

            out = out_bytes.decode("utf-8", errors="replace")
            err = err_bytes.decode("utf-8", errors="replace")

            logger.debug(f"[SSH] exit_code={exit_code} stdout={len(out)}B stderr={len(err)}B")

            if exit_code != 0:
                raise SSHCommandError(
                    f"Komut başarısız (exit={exit_code}): {command[:80]}",
                    exit_code = exit_code,
                    stderr    = err,
                )

            return out, err, exit_code

        except paramiko.ssh_exception.SSHException as e:
            raise SSHConnectionError(f"SSH komut hatası: {e}")
        except socket.timeout:
            raise SSHTimeoutError(f"Komut {timeout}s içinde tamamlanamadı: {command[:80]}")

    def stream_command(
        self,
        command: str,
        timeout: int = STREAM_TIMEOUT,
        env:     Optional[dict] = None,
    ) -> Generator[str, None, None]:
        """
        Komutu çalıştırır ve stdout/stderr satırlarını gerçek zamanlı üretir.
        XenForo upgrade, yedekleme gibi uzun işlemler için kullanılır.

        Yields:
            str — JSON formatında satır: {"stream": "stdout", "line": "..."}
                veya                     {"stream": "stderr", "line": "..."}
                veya son olarak          {"exit_code": 0, "done": true}
        """
        import json
        import select as sel

        self.ensure_connected()
        logger.info(f"[SSH] Stream komutu: {command[:120]}")

        transport = self._client.get_transport()
        channel   = transport.open_session()
        if env:
            for k, v in env.items():
                channel.set_environment_variable(k, v)
        channel.get_pty(width=220)
        channel.exec_command(command)

        channel.settimeout(timeout)
        deadline = time.time() + timeout

        try:
            while not channel.exit_status_ready():
                if time.time() > deadline:
                    channel.close()
                    yield json.dumps({"stream": "error", "line": "Zaman aşımı."})
                    return

                ready = sel.select([channel], [], [], 0.5)[0]
                if ready:
                    data = channel.recv(4096)
                    if data:
                        for line in data.decode("utf-8", errors="replace").splitlines():
                            if line:
                                yield json.dumps({"stream": "stdout", "line": line})

            # Kalan çıktı
            while channel.recv_ready():
                data = channel.recv(4096)
                for line in data.decode("utf-8", errors="replace").splitlines():
                    if line:
                        yield json.dumps({"stream": "stdout", "line": line})

            exit_code = channel.recv_exit_status()
            yield json.dumps({"done": True, "exit_code": exit_code})
            logger.info(f"[SSH] Stream tamamlandı, exit_code={exit_code}")

        finally:
            channel.close()

    # ─────────────────────────────────────────────────────────
    # DOSYA İŞLEMLERİ (SFTP)
    # ─────────────────────────────────────────────────────────

    def read_file(self, remote_path: str) -> str:
        """
        SFTP üzerinden dosya okur.

        Args:
            remote_path: Sunucudaki mutlak dosya yolu

        Returns:
            Dosya içeriği (UTF-8 metin)

        Raises:
            SSHFileError: Dosya bulunamadı veya okuma hatası
        """
        sftp = self.get_sftp()
        try:
            with sftp.open(remote_path, "r") as f:
                content = f.read(MAX_OUTPUT_BYTES)
            return content.decode("utf-8", errors="replace")
        except FileNotFoundError:
            raise SSHFileError(f"Dosya bulunamadı: {remote_path}")
        except PermissionError:
            raise SSHFileError(f"Dosyaya erişim izni yok: {remote_path}")
        except Exception as e:
            raise SSHFileError(f"Dosya okuma hatası ({remote_path}): {e}")

    def write_file(self, remote_path: str, content: str) -> None:
        """
        SFTP üzerinden dosya yazar (atomik: önce .tmp, sonra rename).

        Args:
            remote_path: Sunucudaki mutlak dosya yolu
            content:     Yazılacak içerik

        Raises:
            SSHFileError: Yazma hatası
        """
        sftp = self.get_sftp()
        tmp_path = remote_path + ".tmp_antigravity"

        try:
            with sftp.open(tmp_path, "w") as f:
                f.write(content.encode("utf-8"))
            sftp.rename(tmp_path, remote_path)
            logger.info(f"[SSH] Dosya yazıldı: {remote_path} ({len(content)} karakter)")
        except Exception as e:
            # Başarısız tmp dosyasını temizle
            try: sftp.remove(tmp_path)
            except Exception: pass
            raise SSHFileError(f"Dosya yazma hatası ({remote_path}): {e}")

    def list_dir(self, remote_path: str, recursive: bool = False) -> list[dict]:
        """
        SFTP üzerinden dizin listesi döndürür.

        Returns:
            [{"name": "file.css", "path": "/full/path", "size": 1234,
              "is_dir": False, "mtime": 1234567890}, ...]
        """
        sftp = self.get_sftp()
        results = []
        try:
            attrs = sftp.listdir_attr(remote_path)
            for a in attrs:
                full_path = f"{remote_path.rstrip('/')}/{a.filename}"
                is_dir    = stat.S_ISDIR(a.st_mode)
                results.append({
                    "name":   a.filename,
                    "path":   full_path,
                    "size":   a.st_size,
                    "is_dir": is_dir,
                    "mtime":  a.st_mtime,
                })
                if recursive and is_dir:
                    results.extend(self.list_dir(full_path, recursive=True))
        except FileNotFoundError:
            raise SSHFileError(f"Dizin bulunamadı: {remote_path}")
        return results

    def backup_file(self, remote_path: str) -> str:
        """
        Dosyanın .bak yedeğini alır (üzerine yazma öncesi).
        Returns: yedek dosya yolu
        """
        import datetime
        ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        bak  = f"{remote_path}.{ts}.bak"
        sftp = self.get_sftp()
        try:
            sftp.rename(remote_path, bak)
            # Orijinaline geri yaz (bak + original her ikisi de var)
            content = self.read_file(bak)
            self.write_file(remote_path, content)
        except Exception as e:
            raise SSHFileError(f"Yedekleme hatası ({remote_path}): {e}")
        return bak

    # ─────────────────────────────────────────────────────────
    # YARDIMCI: Yol Güvenliği
    # ─────────────────────────────────────────────────────────

    @staticmethod
    def validate_path(path: str, base: str) -> str:
        """
        Güvenli dizin dışına erişimi (path traversal) önler.
        path mutlaka base altında olmalıdır.

        Args:
            path: İstemciden gelen yol
            base: İzin verilen kök dizin

        Returns:
            Normalize edilmiş güvenli yol

        Raises:
            PathTraversalError: Dizin dışına çıkma girişimi
        """
        # POSIX yol normalizasyonu (sunucu Linux)
        import posixpath
        base_norm  = posixpath.realpath(base)
        path_norm  = posixpath.normpath(
            posixpath.join(base_norm, path.lstrip("/"))
        )
        if not path_norm.startswith(base_norm + "/") and path_norm != base_norm:
            raise PathTraversalError(
                f"Güvenli dizin dışı erişim denemesi: '{path}' (izin: {base})"
            )
        return path_norm

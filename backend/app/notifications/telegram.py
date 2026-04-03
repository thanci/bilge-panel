"""
app/notifications/telegram.py — Telegram Bot Bildirim Modülü.

Bildirimler asenkron değildir: requests.post() ile senkron gönderilir.
Ağ hatası, timeout veya Telegram API hatası ana akışı DURDURMAMALDIR.
Bu yüzden tüm hatalar sadece loglanır, exception fırlatılmaz.

Telegram Bot Kurulumu:
  1. @BotFather'a /newbot komutunu gönderin
  2. Handle: bilgeyolcu_panel_bot (veya istediğiniz bir ad)
  3. Alınan TOKEN'ı .env dosyasına TELEGRAM_BOT_TOKEN olarak kaydedin
  4. Bota bir mesaj gönderin, ardından:
     https://api.telegram.org/bot<TOKEN>/getUpdates
     adresinden CHAT_ID'nizi alın ve .env'e kaydedin
"""

import logging
import threading
import requests
from flask import current_app

logger = logging.getLogger(__name__)

# Telegram API base URL
_TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/sendMessage"

# İstek zaman aşımı (saniye) — uzun beklemeler sistemi bloke etmemeli
_REQUEST_TIMEOUT = 5


def send_telegram_message(
    message: str,
    parse_mode: str = "Markdown",
    blocking: bool = False,
) -> bool:
    """
    Telegram bot üzerinden yönetici chat'ine mesaj gönderir.

    Tasarım İlkesi:
        Bu fonksiyon ASLA exception fırlatmaz.
        Başarı: True döner.
        Herhangi bir hata: loglanır ve False döner.
        Ana uygulama akışı bildirim hatasından etkilenmez.

    Args:
        message:    Gönderilecek mesaj metni (Markdown destekli)
        parse_mode: "Markdown" veya "HTML" (varsayılan: Markdown)
        blocking:   True → senkron gönder, False → arka plan thread'inde gönder

    Returns:
        True → başarılı, False → hata (detay logda)
    """
    if blocking:
        return _send_sync(message, parse_mode)
    else:
        # Arka planda thread olarak gönder — ana akış beklemiyor
        thread = threading.Thread(
            target=_send_sync,
            args=(message, parse_mode),
            daemon=True,   # Ana process kapanırsa bu thread de kapansın
        )
        thread.start()
        return True   # Thread başlatıldı — gerçek sonuç bilinmiyor


def _send_sync(message: str, parse_mode: str = "Markdown") -> bool:
    """
    Telegram mesajını senkron olarak gönderir.
    send_telegram_message() tarafından çağrılır.
    """
    try:
        # Config değerlerini al
        token   = current_app.config.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = current_app.config.get("TELEGRAM_CHAT_ID", "")

        # Yapılandırma eksikse sessizce çık — hata değil, sadece devre dışı
        if not token or not chat_id:
            logger.debug(
                "[TELEGRAM] Token veya Chat ID yapılandırılmamış. "
                "Bildirim atlandı."
            )
            return False

        # Mesajı 4096 karakter ile sınırla (Telegram limiti)
        if len(message) > 4096:
            message = message[:4090] + "\n..."

        url  = _TELEGRAM_API_BASE.format(token=token)
        data = {
            "chat_id":    chat_id,
            "text":       message,
            "parse_mode": parse_mode,
            # Sistem mesajları için bildirim sesini kapat (opsiyonel)
            # "disable_notification": True,
        }

        response = requests.post(url, json=data, timeout=_REQUEST_TIMEOUT)

        if response.status_code == 200:
            logger.debug(f"[TELEGRAM] ✅ Mesaj gönderildi ({len(message)} karakter)")
            return True

        # Telegram API hata döndürdü
        logger.warning(
            f"[TELEGRAM] API hatası: HTTP {response.status_code} | "
            f"Yanıt: {response.text[:200]}"
        )
        return False

    except requests.exceptions.Timeout:
        logger.warning(
            f"[TELEGRAM] Zaman aşımı ({_REQUEST_TIMEOUT}s) — mesaj gönderilemedi."
        )
        return False

    except requests.exceptions.ConnectionError:
        logger.warning("[TELEGRAM] Bağlantı hatası — Telegram API'ye erişilemiyor.")
        return False

    except Exception as e:
        # Beklenmedik hata — ana akışı etkileme
        logger.error(f"[TELEGRAM] Beklenmedik hata: {e}", exc_info=True)
        return False


# ============================================================
# HAZIR BİLDİRİM ŞABLONLARı
# İçerik ve bütçe modülleri bu fonksiyonları çağırır.
# ============================================================

def notify_task_success(task_id: str, task_type: str, result_url: str = "") -> None:
    """Görev başarıyla tamamlandığında bildirim gönderir."""
    type_names = {
        "youtube_summary": "📺 YouTube Özeti",
        "ai_article":      "✍️ AI Makale",
        "xf_sync":         "🔄 XF Senkronizasyon",
        "xf_upgrade":      "⬆️ XF Güncelleme",
    }
    display_name = type_names.get(task_type, f"🔧 {task_type}")
    url_line = f"\n🔗 [Konuya Git]({result_url})" if result_url else ""

    send_telegram_message(
        f"✅ *[GÖREV TAMAMLANDI]*\n\n"
        f"📌 Tür: {display_name}\n"
        f"🆔 ID: `{task_id[:8]}...`"
        f"{url_line}"
    )


def notify_task_failed(task_id: str, task_type: str, error: str) -> None:
    """Görev başarısız olduğunda bildirim gönderir."""
    # Hata mesajını sınırla — Telegram mesajı çok uzun olmasın
    short_error = error[:300] if error else "Bilinmeyen hata"
    send_telegram_message(
        f"❌ *[GÖREV BAŞARISIZ]*\n\n"
        f"🆔 ID: `{task_id[:8]}...`\n"
        f"📌 Tür: {task_type}\n"
        f"⚠️ Hata: `{short_error}`"
    )


def notify_all_models_failed(task_id: str) -> None:
    """Tüm fallback LLM modelleri başarısız olduğunda kritik bildirim gönderir."""
    send_telegram_message(
        f"🆘 *[KRİTİK — TÜM LLM'LER YANIT VERMİYOR]*\n\n"
        f"🆔 Task: `{task_id[:8]}...`\n"
        f"Gemini → Claude → GPT-4o-mini zincirinin tamamı başarısız oldu.\n\n"
        f"Lütfen API durumlarını kontrol edin."
    )


def notify_xf_upgrade_success(from_ver: str, to_ver: str) -> None:
    """Xenforo güncelleme başarıyla tamamlandığında bildirim gönderir."""
    send_telegram_message(
        f"⬆️ *[XENFORO GÜNCELLENDİ]*\n\n"
        f"📦 {from_ver} → {to_ver}\n"
        f"✅ Güncelleme başarıyla tamamlandı."
    )


def notify_xf_upgrade_failed(error: str) -> None:
    """Xenforo güncelleme başarısız olduğunda bildirim gönderir."""
    send_telegram_message(
        f"🚨 *[XENFORO GÜNCELLEME BAŞARISIZ]*\n\n"
        f"⚠️ Hata: `{error[:200]}`\n"
        f"🔄 Yedekten geri yükleme başlatılıyor..."
    )

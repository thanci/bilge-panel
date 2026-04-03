"""
app/xenforo/publisher.py — LLM → XenForo Köprüsü.

Bu modül, Celery task'larından çağrılır.
Sorumluluğu:
  1. XenForo konfigürasyonunun mevcut olup olmadığını sessizce kontrol et
  2. İçeriği forum konusu olarak yayınla
  3. Hataları TaskLog'a anlamlı biçimde yansıt
  4. XenForo hatası LLM görevini başarısız YAPMAZ
     (içerik üretildi, sadece yayın başarısız)

Tasarım Prensibi: "Fail-Soft"
  LLM içerik üretimiyle XenForo yayını bağımsız süreçlerdir.
  Biri başarısız olsa da diğeri bağımsız olarak tamamlanmış kabul edilir.
  Yayın hatası ayrı bir sonuç alanına (xf.status: "error") yazılır.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def publish_to_xenforo(
    task_id:    str,
    content:    str,
    title:      str,
    node_id:    Optional[int],
    tags:       Optional[list] = None,
    prefix_id:  Optional[int] = None,
) -> dict:
    """
    LLM tarafından üretilmiş BB-Code içeriği XenForo'da konu olarak yayınlar.

    Bu fonksiyon Celery task'larından şu şekilde çağrılır:
        xf_result = publish_to_xenforo(
            task_id  = task_id,
            content  = final_content,       # BB-Code
            title    = article_title,
            node_id  = payload.get("xf_node_id"),
            tags     = meta.get("keywords", []),
        )

    Hata Yönetimi — Fail-Soft Mimarisi:
      XenForo hatası, LLM görevini FAILED yapmaz.
      Bunun yerine şunu döner:
        {"status": "error", "error_type": "...", "message": "..."}
      Bu sonuç TaskLog'a xf: {...} olarak kaydedilir.
      Kullanıcı dashboard'da "İçerik üretildi, yayın başarısız" mesajını görür.

    Neden:
      - XenForo sunucu hatası nedeniyle 30 dakikalık transkript işleme kaybedilmemelidir
      - İçerik üretildiyse TaskLog'da BAŞARILI sayılır
      - XenForo hatası ayrıca Telegram'a bildirilir

    Args:
        task_id:    Celery görev ID'si (loglama için)
        content:    BB-Code formatında makale içeriği
        title:      Konu başlığı (150 karakterle sınırlandırılır)
        node_id:    XenForo forum node ID'si (None ise yayın atlanır)
        tags:       Konu etiketleri listesi
        prefix_id:  Konu öneki ID'si

    Returns:
        dict — Yayın sonucu:
          {"status": "success", "thread_id": 123, "url": "...", "title": "..."}
          {"status": "skipped", "reason": "xf_node_id belirtilmedi"}
          {"status": "disabled", "reason": "XenForo konfigürasyonu eksik"}
          {"status": "error", "error_type": "...", "message": "..."}
    """
    from flask import current_app

    # ── Konfigürasyon kontrolü ──────────────────────────────
    xf_enabled = (
        bool(current_app.config.get("XENFORO_BASE_URL")) and
        bool(current_app.config.get("XENFORO_API_KEY"))
    )

    if not xf_enabled:
        logger.info(
            f"[XF-PUBLISHER] task={task_id[:8]} → XenForo konfigürasyonu yok, atlandı."
        )
        return {
            "status": "disabled",
            "reason": "XENFORO_BASE_URL veya XENFORO_API_KEY tanımlı değil.",
        }

    # ── node_id zorunlu ────────────────────────────────────
    if not node_id:
        logger.info(
            f"[XF-PUBLISHER] task={task_id[:8]} → xf_node_id belirtilmedi, atlandı."
        )
        return {
            "status": "skipped",
            "reason": "xf_node_id payload'da belirtilmedi.",
        }

    # ── XenForo yayını ────────────────────────────────────
    try:
        from app.xenforo.client       import XenForoClient
        from app.xenforo.threads      import ThreadManager
        from app.xenforo.exceptions   import (
            XenForoError,
            XenForoForbiddenError,
            XenForoAuthError,
            XenForoValidationError,
        )
        from app.notifications.telegram import _send_async as tg_send   # fail-safe

        # Başlık yoksa içerikten çıkar
        if not title or not title.strip():
            title = ThreadManager.extract_title_from_content(content, "Yeni Makale")

        # Etiketleri temizle
        clean_tags = []
        if tags:
            if isinstance(tags, str):
                clean_tags = [t.strip() for t in tags.split(",") if t.strip()]
            else:
                clean_tags = [t.strip() for t in tags if t and isinstance(t, str)]
        clean_tags = clean_tags[:10]   # XF max ~ 10 etiket

        logger.info(
            f"[XF-PUBLISHER] task={task_id[:8]} → "
            f"node_id={node_id} title='{title[:50]}' "
            f"tags={clean_tags[:3]}"
        )

        with XenForoClient.from_config() as xf:
            resp    = xf.threads.create(
                node_id   = int(node_id),
                title     = title,
                message   = content,
                tags      = clean_tags,
                prefix_id = prefix_id,
            )

        thread  = resp.get("thread", resp)
        t_id    = thread.get("thread_id")
        t_url   = thread.get("view_url", "")

        logger.info(
            f"[XF-PUBLISHER] ✅ Yayınlandı: "
            f"task={task_id[:8]} thread_id={t_id} url={t_url}"
        )
        return {
            "status":    "success",
            "thread_id": t_id,
            "url":       t_url,
            "title":     thread.get("title", title),
        }

    except XenForoAuthError as e:
        # API key hatası — kritik, admin haberdar edilmeli
        msg = f"XenForo API key hatası: {e}"
        logger.error(f"[XF-PUBLISHER] {msg}")
        tg_send(f"🔑 XenForo API Key Hatası\ntask={task_id[:8]}\n{e}")
        return {"status": "error", "error_type": "auth", "message": msg}

    except XenForoForbiddenError as e:
        msg = f"XenForo erişim reddedildi (node_id={node_id}): {e}"
        logger.error(f"[XF-PUBLISHER] {msg}")
        return {"status": "error", "error_type": "forbidden", "message": msg}

    except XenForoValidationError as e:
        # Genellikle boş başlık veya geçersiz node
        msg = f"XenForo doğrulama hatası: {e}"
        logger.warning(f"[XF-PUBLISHER] {msg}")
        return {"status": "error", "error_type": "validation", "message": msg,
                "xf_errors": e.xf_errors}

    except XenForoError as e:
        # Genel XF hatası (5xx, bağlantı vb.)
        msg = f"XenForo yayın hatası: {e}"
        logger.error(f"[XF-PUBLISHER] {msg}", exc_info=True)
        return {"status": "error", "error_type": "xenforo", "message": msg}

    except Exception as e:
        # Beklenmedik hata
        msg = f"Beklenmedik XenForo publisher hatası: {e}"
        logger.error(f"[XF-PUBLISHER] {msg}", exc_info=True)
        return {"status": "error", "error_type": "unexpected", "message": msg}

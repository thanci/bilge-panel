"""
app/xenforo/threads.py — XenForo Konu ve Gönderi Yöneticisi.

Bilge Yolcu → XenForo İçerik Köprüsü:
  Celery task'ları LLM'den BB-Code formatında içerik üretir.
  Bu yönetici, üretilen içeriği forum konusuna dönüştürür.

Konu açma POST endpoint parametreleri (XenForo 2.x):
  node_id           — Hangi forumda konu açılacak
  title             — Konu başlığı (plaintext, max 150 karakter)
  message           — İlk gönderi (BB-Code)
  discussion_type   — "discussion" (standart konu)
                      "question"  (soru-cevap formatı)
  tags[]            — Etiket listesi (her biri ayrı form field)
  prefix_id         — Konu öneki ID'si (opsiyonel)
  watch_thread      — Konuyu takip et (1/0)
  sticky            — Sabit konu (1/0) — admin yetkisi gerekir
  locked            — Kilitli konu (1/0) — admin yetkisi gerekir

Başarılı yanıt:
  {"thread": {"thread_id": 123, "title": "...", "view_url": "...", ...}}
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# XenForo başlık uzunluk sınırı
MAX_TITLE_LENGTH = 150

# Etiket uzunluk sınırı (tekli)
MAX_TAG_LENGTH   = 50

# Konu tipi sabitleri
DISCUSSION_TYPE_DISCUSSION = "discussion"
DISCUSSION_TYPE_QUESTION   = "question"


class ThreadManager:
    """
    XenForo konu ve gönderi yöneticisi.
    XenForoClient örneğine bağlıdır.

    client.threads.xxx() üzerinden erişilir.
    """

    def __init__(self, client):
        self._client = client

    # ─────────────────────────────────────────────────────────
    # KONU OKUMA
    # ─────────────────────────────────────────────────────────

    def get(self, thread_id: int) -> dict:
        """Belirli bir konunun detaylarını döndürür."""
        return self._client.get(f"threads/{thread_id}")

    def list_by_forum(self, node_id: int, page: int = 1) -> dict:
        """
        Belirli bir forumdaki konuları listeler.
        
        Returns:
            {"threads": [...], "pagination": {...}}
        """
        return self._client.get("threads", params={"node_id": node_id, "page": page})

    # ─────────────────────────────────────────────────────────
    # KONU OLUŞTURMA
    # ─────────────────────────────────────────────────────────

    def create(
        self,
        node_id:         int,
        title:           str,
        message:         str,
        tags:            Optional[list[str]] = None,
        prefix_id:       Optional[int]       = None,
        discussion_type: str                 = DISCUSSION_TYPE_DISCUSSION,
        sticky:          bool                = False,
        locked:          bool                = False,
        watch_thread:    bool                = True,
    ) -> dict:
        """
        Yeni bir forum konusu oluşturur.

        Bu metot Celery task'larından (youtube_to_article_task ve ai_article_task)
        çağrılır. LLM'in ürettiği BB-Code içerik direkt olarak `message` alanına girer.

        Args:
            node_id:         Hedef forum ID'si (XenForo node_id)
            title:           Konu başlığı — 150 karakter ile sınırlandırılır
            message:         İlk gönderi içeriği (BB-Code formatında)
            tags:            Konu etiketleri listesi (her biri max 50 karakter)
            prefix_id:       Konu öneki ID'si (opsiyonel, foruma ait prefix)
            discussion_type: "discussion" (standart) veya "question" (soru)
            sticky:          Sabit konu yap
            locked:          Kapalı konu yap
            watch_thread:    Konuyu API kullanıcısı adına takibe al

        Returns:
            {
                "thread": {
                    "thread_id": 123,
                    "thread_hash": "...",
                    "title": "...",
                    "view_url": "https://bilgeyolcu.com/threads/...",
                    "node_id": 5,
                    ...
                }
            }

        Raises:
            XenForoValidationError: Boş başlık, geçersiz node vb.
            XenForoForbiddenError:  Bu foruma erişim yetkisi yok
        """
        # ── Başlık düzenleme ──────────────────────────────────
        title = title.strip()
        if not title:
            from app.xenforo.exceptions import XenForoValidationError
            raise XenForoValidationError(
                "Konu başlığı boş olamaz.",
                status_code=400,
            )
        if len(title) > MAX_TITLE_LENGTH:
            logger.warning(
                f"[XF-THREADS] Başlık {len(title)} karakter — "
                f"{MAX_TITLE_LENGTH} ile sınırlandırıldı."
            )
            title = title[:MAX_TITLE_LENGTH - 3] + "..."

        # ── Form verisi ──────────────────────────────────────
        data: list[tuple] = [
            ("node_id",         str(node_id)),
            ("title",           title),
            ("message",         message),
            ("discussion_type", discussion_type),
            ("watch_thread",    str(int(watch_thread))),
        ]

        # İsteğe bağlı alanlar
        if prefix_id:
            data.append(("prefix_id", str(prefix_id)))
        if sticky:
            data.append(("sticky",    "1"))
        if locked:
            data.append(("locked",    "1"))

        # Etiketler: her biri ayrı tags[] field'ı
        if tags:
            clean_tags = [
                t.strip().lower()[:MAX_TAG_LENGTH]
                for t in tags
                if t and t.strip()
            ]
            for tag in clean_tags[:10]:   # XF max ~ 10-20 etiket
                data.append(("tags[]", tag))

        # ── İsteği gönder ────────────────────────────────────
        resp    = self._client.post("threads", data)
        thread  = resp.get("thread", resp)

        logger.info(
            f"[XF-THREADS] ✅ Konu oluşturuldu: "
            f"thread_id={thread.get('thread_id')} "
            f"node={node_id} title='{title[:50]}'"
        )
        return resp

    # ─────────────────────────────────────────────────────────
    # KONU GÜNCELLEME
    # ─────────────────────────────────────────────────────────

    def add_reply(self, thread_id: int, message: str) -> dict:
        """
        Mevcut bir konuya yanıt ekler.

        Args:
            thread_id: Yanıtlanacak konu ID'si
            message:   Yanıt içeriği (BB-Code)
        """
        data = {
            "thread_id": str(thread_id),
            "message":   message,
        }
        resp = self._client.post("posts", data)
        logger.info(f"[XF-THREADS] Yanıt eklendi: thread_id={thread_id}")
        return resp

    def set_sticky(self, thread_id: int, sticky: bool = True) -> dict:
        """Konuyu sabit yapma / sabitliği kaldırma."""
        return self._client.patch(f"threads/{thread_id}", {
            "sticky": "1" if sticky else "0"
        })

    def lock_thread(self, thread_id: int, locked: bool = True) -> dict:
        """Konuyu kilitle / kilidi aç."""
        return self._client.patch(f"threads/{thread_id}", {
            "discussion_open": "0" if locked else "1"
        })

    def delete_thread(self, thread_id: int, reason: str = "") -> dict:
        """Konuyu sil (Çöp kutusuna gönder)."""
        return self._client.delete(f"threads/{thread_id}")

    # ─────────────────────────────────────────────────────────
    # YARDIMCI: LLM çıktısından konu başlığı türet
    # ─────────────────────────────────────────────────────────

    @staticmethod
    def extract_title_from_content(content: str, fallback: str = "Yeni Makale") -> str:
        """
        LLM çıktısından başlık çıkarmaya çalışır.
        BB-Code'daki ilk [B]...[/B] etiketini başlık olarak kullanır.
        Bulunamazsa fallback döner.

        Kullanım:
            title = ThreadManager.extract_title_from_content(llm_output, topic)
        """
        import re
        # [B]...[/B] veya [HEADING]...[/HEADING] içindeki ilk metni al
        patterns = [
            r'\[HEADING=\d+\](.*?)\[/HEADING\]',
            r'\[B\](.*?)\[/B\]',
        ]
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                candidate = match.group(1).strip()
                # Makul uzunlukta mı?
                if 10 <= len(candidate) <= MAX_TITLE_LENGTH:
                    return candidate

        # BB-Code'dan arındırılmış ilk satır
        first_line = re.sub(r'\[.*?\]', '', content).strip().split('\n')[0].strip()
        if len(first_line) >= 10:
            return first_line[:MAX_TITLE_LENGTH]

        return fallback[:MAX_TITLE_LENGTH]

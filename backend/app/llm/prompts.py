"""
app/llm/prompts.py — Bilge Yolcu sistem prompt'ları ve şablon yöneticisi.

Bu modül, LLM'e gönderilecek tüm sistem directivelerini ve
dinamik prompt şablonlarını tek bir yerde toplar.

Bilge Yolcu Vizyonu:
  bilgeyolcu.com; felsefe, bilim, kültür ve düşünce tarihini
  derinlikli, akıcı ve özgün bir dille Türkçe okuyucuya sunan
  bir içerik platformudur. Sığ "liste makalelerinden" değil,
  bağlamını ve tarihsel kökünü ortaya koyan analizlerden beslenir.

Ton Sınıflandırması:
  "felsefi"  — Spekülatif, soru soran, ağır epistomolojik dil
  "bilimsel" — Kanıt odaklı, kaynak belirten, sober akademik üslup
  "anlatı"   — Hikâye örgüsü kuran, betimleyici, edebi
  "seo"      — İlk paragrafta ana kelime, alt başlıklar H2, liste + paragraf karışımı
"""


# ============================================================
# KİMLİK VE TEMEL KURALLAR
# ============================================================

_BASE_IDENTITY = """
Sen Bilge Yolcu platformunun baş editörü ve içerik uzmanısın.
Platform kimliğin şu ilkeler üzerine kuruludur:

1. DİL KALİTESİ: Türkçeyi doğal, akıcı ve özgün biçimde kullan.
   Tercüme havası veren cümlelerden, gereksiz yabancı sözcük doldurmalarından
   ve kopyalanmış klişelerden kesinlikle kaçın. Her cümle birbiriyle örgülü olsun.

2. DERİNLİK: Her konuyu yalnızca yüzeysel değil, tarihsel arka planı,
   felsefi kökü ve toplumsal bağlamıyla birlikte ele al. "Neden?" sorusunu
   her türde sor.

3. ÖZGÜNLÜK: Oluşturduğun metin, görünen kaynaktan doğrudan alıntı değil,
   sentez ve yorumdur. Okuyucu yeni bir bakış açısı kazansın.

4. SEO UYUMU: Makale arama motorlarında görünür olmalıdır. Ancak SEO,
   içerik kalitesini asla gölgelemez — önce insan okuyucu, sonra algoritma.

5. FORMAT: Çıktını her zaman aşağıdaki XenForo uyumlu BB-Code yapısında sun:
   [B]Başlık[/B] → Bölüm başlıkları
   [I]vurgu[/I] → Kavram, terim veya eser adı
   [QUOTE]...[/QUOTE] → Alıntı cümleleri
   Alt başlıkları [B][HEADING]...[/HEADING][/B] yerine net biçimde belirt.

KESIN YASAK: Hallüsinasyon üretme. Belirsiz bir bilgiyse söyle.
""".strip()


# ============================================================
# YOUTUBE ÖZETİ SİSTEM PROMPTU
# ============================================================

YOUTUBE_SUMMARY_SYSTEM = f"""
{_BASE_IDENTITY}

GÖREVIN — YOUTUBE'DAN MAKALE:
Sana bir video transkripti verilecek. Bu transkripti aşağıdaki adımları izleyerek
eksiksiz ve özgün bir makaleye dönüştür:

ADIM 1 — OKUMA VE ÖZETLEME:
  - Transkripti bütünüyle kavra. Tekrarlayan, dolgu niteliğindeki ifadeleri ayıkla.
  - Videonun ana tezi, destekleyici argümanlar ve sonuç noktasını belirle.

ADIM 2 — ÇERÇEVELEME:
  - Konuyu Türk okuyucusu için bağlama oturtur. Gerekiyorsa kısa tarihsel not ekle.
  - Videonun görüşüyle farklı görüşleri varsa, nötr ama analitik bir dille aktar.

ADIM 3 — YAZI YAPISI (aşağıdaki sırayı koru):
  a) Dikkat çekici, soru soran ya da paradoks barındıran bir AÇILIŞ paragrafı (2-3 cümle)
  b) Videonun bağlamını açıklayan GİRİŞ (1 paragraf)
  c) En az 3, en fazla 6 [B]Bölüm Başlığı[/B] ile yapılandırılmış ANA GÖVDE
  d) Okuyucuyu düşünmeye davet eden SONUÇ paragrafı
  e) --- META --- bölümü: 1 satır meta açıklaması (120-155 karakter) +
     5-8 anahtar kelime (virgülle ayrılmış)

FORMAT KURALLARI:
  - Kelime sayısı: 800-1200
  - Direkt alıntılarda [QUOTE]...[/QUOTE] kullan
  - İlk paragrafta videonun kaynak kanalı/konuşmacısı belirtilsin (varsa biliniyorsa)
""".strip()


# ============================================================
# OTONOM MAKALE YAZARI SİSTEM PROMPTU
# ============================================================

AI_WRITER_SYSTEM = f"""
{_BASE_IDENTITY}

GÖREVIN — OTONOM MAKALE YAZARLIĞI:
Sana bir konu, ton ve parametreler verilecek. Tamamen özgün, araştırılmış
ve akıcı bir makale yaz. Sana verilecek parametreler:

PARAMETRELER VE ANLAMLARI:
  konu       → Makalenin merkezindeki kavram, soru ya da fenomen
  ton        → felsefi | bilimsel | anlatı | seo
  uzunluk    → kısa (400-600 k) | orta (700-1000 k) | uzun (1200-1800 k)
  kategori   → (Opsiyonel) XenForo forum kategorisi — içeriği şekillendirir
  anahtar_kw → (Opsiyonel) SEO için öncelikli anahtar kelimeler

TON AÇIKLAMALARI:
  felsefi  → Spekülatif, soru soran üslup. "Bu doğru mudur?" değil,
              "Bu nasıl doğru olabilir?" diye sor.
  bilimsel → Kanıt önce, yorum sonra. İddia açık, atıf ima edilir.
  anlatı   → Hikâye kurar gibi yaz. Sahne, karakter, gerilim.
  seo      → İlk 100 kelimede anahtar kelime, H2'ler (BB-Code [B]başlık[/B])
              liste + paragraf dengesi.

YAZI YAPISI (her tonda geçerli):
  a) Güçlü AÇILIŞ: İlk cümle okuyucuyu yakalar (soru, paradoks veya çarpıcı gerçek)
  b) ANA GÖVDE: Tona göre yapılandır
  c) SONUÇ: Açık uçlu, okuyucuyu düşündüren bitiş
  d) --- META --- bloğu:
       Açıklama: <120-155 karakter, meta description olarak kullanılacak>
       Anahtar kelimeler: <5-8 kelime/ifade, virgülle>

SEO NOTU: Anahtar kelimeyi makale boyunca doğal biçimde 4-6 kez kullan.
Zorla tekrar etme — bağlama uyuyorsa kullan.
""".strip()


# ============================================================
# DİNAMİK PROMPT OLUŞTURUCULARI
# ============================================================

def build_youtube_prompt(transcript_text: str, video_title: str = "",
                          channel_name: str = "", extra_notes: str = "") -> str:
    """
    LLM'e gönderilecek tam YouTube özeti görev metnini oluşturur.

    Args:
        transcript_text: YouTube transkriptinin birleştirilmiş metni
        video_title:     Video başlığı (varsa, LLM bağlamı için)
        channel_name:    Kanal adı (varsa)
        extra_notes:     Admin'in ek notları (isteğe bağlı yönlendirme)

    Returns:
        LLM'e gönderilecek hazır görev metni (sistem prompt ile değil, sadece
        kullanıcı mesajı — sistem ayrı parameters'ta gönderilir)
    """
    parts = []

    if video_title:
        parts.append(f"VİDEO BAŞLIĞI: {video_title}")
    if channel_name:
        parts.append(f"KANAL: {channel_name}")
    if extra_notes:
        parts.append(f"ADMİN NOTU: {extra_notes}")

    parts.append("")
    parts.append(
        "Aşağıdaki transkripti yukarıdaki talimatlara uygun şekilde "
        "özgün bir makaleye dönüştür:"
    )
    parts.append("")
    parts.append("--- TRANSKRİPT BAŞLANGICI ---")
    parts.append(transcript_text)
    parts.append("--- TRANSKRİPT SONU ---")

    return "\n".join(parts)


def build_article_prompt(
    topic: str,
    tone: str = "felsefi",
    length: str = "orta",
    category: str = "",
    keywords: str = "",
    extra_notes: str = "",
) -> str:
    """
    Otonom makale yazımı için LLM görev metnini oluşturur.

    Args:
        topic:       Makalenin konusu
        tone:        felsefi | bilimsel | anlatı | seo
        length:      kısa | orta | uzun
        category:    XenForo kategori adı (içerik odağını belirler)
        keywords:    Virgülle ayrılmış SEO anahtar kelimeleri
        extra_notes: Admin yönlendirme notları

    Returns:
        LLM kullanıcı mesajı
    """
    # Kelime sayısı hedefi — ton promptunda da yazıyor ama tekrar belirt
    length_map = {
        "kısa": "400-600 kelime",
        "orta": "700-1000 kelime",
        "uzun": "1200-1800 kelime",
    }
    word_target = length_map.get(length, "700-1000 kelime")

    parts = [
        f"KONU: {topic}",
        f"TON: {tone}",
        f"HEDEF UZUNLUK: {word_target}",
    ]

    if category:
        parts.append(f"KATEGORİ: {category}")
    if keywords:
        parts.append(f"ANAHTAR KELİMELER: {keywords}")
    if extra_notes:
        parts.append(f"EK NOT: {extra_notes}")

    parts.append("")
    parts.append(
        "Yukarıdaki parametrelere uygun, XenForo BB-Code formatında "
        "eksiksiz ve özgün bir makale yaz."
    )

    return "\n".join(parts)


def parse_meta_block(llm_output: str) -> dict:
    """
    LLM çıktısındaki --- META --- bloğunu ayrıştırır.

    Returns:
        {
            "content":     <meta bölümü dışındaki makale içeriği>,
            "description": <meta açıklaması>,
            "keywords":    <anahtar kelimeler listesi>
        }
    """
    meta_separator = "--- META ---"
    content, meta_text = (
        llm_output.split(meta_separator, 1)
        if meta_separator in llm_output
        else (llm_output, "")
    )

    description = ""
    keywords    = []

    for line in meta_text.strip().splitlines():
        line = line.strip()
        if line.lower().startswith("açıklama:"):
            description = line.split(":", 1)[-1].strip()
        elif line.lower().startswith("anahtar"):
            kw_raw = line.split(":", 1)[-1].strip()
            keywords = [k.strip() for k in kw_raw.split(",") if k.strip()]

    return {
        "content":     content.strip(),
        "description": description,
        "keywords":    keywords,
    }

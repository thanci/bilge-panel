<script setup>
/**
 * GuideView.vue — Kullanım Rehberi.
 * Accordion yapısında interaktif panel kılavuzu.
 */
import { ref } from 'vue'

const openSection = ref('overview')

const sections = [
  {
    id: 'overview',
    icon: '🏠',
    title: 'Panel Nedir?',
    content: `Bilge Yolcu Kontrol Paneli, bilgeyolcu.com platformu için geliştirilmiş yapay zeka destekli bir içerik yönetim sistemidir. Felsefe, bilim, kültür ve düşünce tarihi üzerine özgün makaleler üretmek, düzenlemek ve XenForo forumuna yayınlamak için tasarlanmıştır.`,
  },
  {
    id: 'workflow',
    icon: '🔄',
    title: 'İş Akışı',
    content: `İçerik üretim süreci 4 adımdan oluşur:

1. <strong>Konu Belirle</strong> — Görev Kuyruğu'ndan AI makale görevi oluştur. Konu, ton, uzunluk ve parametreleri seç.

2. <strong>AI Üretir</strong> — Yapay zeka belirlenen parametrelere göre makaleyi yazar. Bu süreçte bütçe kontrolü yapılır.

3. <strong>Düzenle</strong> — Tamamlanan görevi "Yayına Gönder" ile Yayın Kuyruğu'na aktar. TipTap editörle düzenle, AI araçlarıyla genişlet.

4. <strong>Yayınla</strong> — Hedef forumu seç ve "XenForo'ya Yayınla" ile konu oluştur.`,
  },
  {
    id: 'tasks',
    icon: '⚡',
    title: 'Görev Kuyruğu',
    content: `Görev Kuyruğu, AI içerik üretim görevlerini yönettiğiniz yerdir.

<strong>Görev Oluşturma:</strong> Konu, yazım stili (24 farklı ton), uzunluk hedefi ve ek notlarla görev başlatın.

<strong>Görev İzleme:</strong> Görevler sırasıyla PENDING → RUNNING → SUCCESS/FAILED durumlarından geçer. Tablodaki herhangi bir satıra tıklayarak detay modalını açabilirsiniz.

<strong>Aksiyonlar:</strong> Başarılı görevleri "Yayına Gönder", başarısız olanları "Tekrar Dene" veya "Sil" ile yönetin.`,
  },
  {
    id: 'publish',
    icon: '📝',
    title: 'Yayın Kuyruğu & Editör',
    content: `Yayın Kuyruğu, içerikleri son hallerine getirip XenForo'ya yayınladığınız alandır.

<strong>Editör Modları:</strong>
• <strong>✏️ Editör</strong> — WYSIWYG (Word benzeri) görsel düzenleme
• <strong>📝 BB-Code</strong> — Ham BB-Code metin editörü (gelişmiş kullanıcılar)
• <strong>👁 Önizleme</strong> — İçeriğin yayınlanmış halinin körizlemesi

<strong>AI Araçları (✨ butonu):</strong>
• Genişlet — Seçili paragrafı detaylandır
• Yeniden Yaz — Farklı ifadelerle yeniden oluştur
• Daha Uzun Yap — Tüm makaleyi genişlet
• Özetle — Kısalt
• Devam Et — Metnin devamını yazdır
• Çevir — İngilizce metni Türkçeye çevir

<strong>Yazım Stilleri:</strong> 24 farklı ton seçeneği ile AI'ın üslubunu belirleyebilirsiniz (Felsefi, Bilimsel, Anlatı, Yaratıcı, Haber ve daha fazlası).`,
  },
  {
    id: 'budget',
    icon: '◎',
    title: 'Bütçe Yönetimi',
    content: `Bütçe sayfası, AI API kullanımınıza ilişkin maliyetleri takip eder.

<strong>Günlük Limit:</strong> Her gün belirlenen bütçe sınırı içinde çalışır. Limit aşılırsa yeni görev başlatılamaz.

<strong>Model Maliyetleri:</strong> Gemini, Claude ve GPT modellerinin token başına maliyet karşılaştırması gösterilir.

<strong>Maliyet Grafiği:</strong> Günlük/haftalık harcama trendlerinizi analiz edin.`,
  },
  {
    id: 'xenforo',
    icon: '🏛',
    title: 'XenForo',
    content: `XenForo sayfası, forum yönetim arayüzüdür.

<strong>Forum Listesi:</strong> XenForo node'larını (forum bölümleri) görüntüleyin.
<strong>Konu Yönetimi:</strong> Son konuları listeleyin, detayları görüntüleyin.
<strong>API Durumu:</strong> XenForo API bağlantı sağlığını kontrol edin.`,
  },
  {
    id: 'devops',
    icon: '🖥',
    title: 'Sistem & Tema',
    content: `Bu sayfa 4 sekme içerir:

<strong>📊 Sistem Durumu:</strong> SSH bağlantı durumu, disk kullanımı, bellek, PHP ve XenForo sürümleri.

<strong>⌨️ SSH Terminal:</strong> Sunucuya doğrudan komut gönderin. Hızlı komut butonlarıyla sık kullanılan işlemlere erişin (disk, bellek, süreçler vb.).

<strong>🚀 XF Güncelleyici:</strong> XenForo sürüm güncelleme pipeline'ı. Otomatik yedek → bakım modu → upgrade → açık.

<strong>🎨 Tema Editörü:</strong> XenForo tema dosyalarını (LESS, CSS, HTML) SSH üzerinden düzenleyin. Monaco editör ile syntax highlighting.`,
  },
  {
    id: 'tones',
    icon: '🎨',
    title: 'Yazım Stilleri',
    content: `24 farklı yazım stili mevcuttur:

🔮 <strong>Felsefi</strong> — Spekülatif, soru soran
🔬 <strong>Bilimsel</strong> — Kanıt odaklı, akademik
📖 <strong>Anlatı</strong> — Hikâye kurar gibi, edebi
🔍 <strong>SEO</strong> — Arama motoru uyumlu
💡 <strong>Yaratıcı</strong> — Beklenmedik bakış açıları
📰 <strong>Haber</strong> — 5N1K, nesnel
🎓 <strong>Eğitici</strong> — Adım adım, öğretici
💬 <strong>Sohbet</strong> — Blog tarzı, samimi
⚔️ <strong>Polemik</strong> — Tartışmacı, tez-antitez
🌟 <strong>İlham Verici</strong> — Motivasyonel
🎭 <strong>Satirik</strong> — İronik, eleştirel
⚖️ <strong>Karşılaştırma</strong> — Analiz, fark-benzerlik
🏛️ <strong>Tarihsel</strong> — Kronolojik, dönem analizi
🛠️ <strong>Teknik</strong> — Nasıl yapılır rehberi
🧠 <strong>Psikolojik</strong> — Davranış bilimi
🚀 <strong>Spekülatif</strong> — Gelecek tahminleri
✂️ <strong>Minimalist</strong> — Kısa ve çarpıcı
📋 <strong>Akademik</strong> — Tez formatı, atıf stili
🔎 <strong>Eleştirel</strong> — Eser/film incelemesi
✉️ <strong>Mektup</strong> — Okuyucuya hitap
📣 <strong>Manifesto</strong> — Güçlü çağrı, ideolojik
🎙️ <strong>Diyalog</strong> — Söyleşi formatı
🐉 <strong>Mitolojik</strong> — Sembol ve arketip analizi
✍️ <strong>Deneme</strong> — Serbest düşünce akışı`,
  },
  {
    id: 'faq',
    icon: '❓',
    title: 'Sıkça Sorulan Sorular',
    content: `<strong>S: Görev başarısız olursa ne yapmalıyım?</strong>
C: Görev satırına tıklayıp hata detayını görün. "Tekrar Dene" ile yeniden başlatabilirsiniz. Bütçe doluysa ertesi güne bekleyin.

<strong>S: Makale çok kısa geldi, ne yapabilirim?</strong>
C: Yayın Kuyruğu'nda AI "Daha Uzun Yap" aracını kullanın veya yeni görev oluştururken "uzun" veya "çok_uzun" seçeneğini seçin.

<strong>S: XenForo'ya yayınlanan yazının formatı bozuk mu?</strong>
C: Editör otomatik olarak BB-Code'a dönüştürür. Eğer sorun varsa BB-Code moduna geçerek manuel düzeltme yapabilirsiniz.

<strong>S: Bütçem doldu, ne olur?</strong>
C: Günlük limit sıfırlanana kadar yeni AI görevi başlatılamaz. Mevcut taslaklar üzerinde çalışmaya devam edebilirsiniz.

<strong>S: SSH bağlantısı neden gerekli?</strong>
C: Tema editörü ve XF güncelleme işlemleri doğrudan sunucuya SSH bağlantısı üzerinden yapılır. SSH olmadan bu özellikler kullanılamaz.`,
  },
]

function toggle(id) {
  openSection.value = openSection.value === id ? '' : id
}
</script>

<template>
  <div class="max-w-screen-lg mx-auto space-y-5 animate-fade-in">

    <!-- Başlık -->
    <div>
      <h1 class="text-xl font-bold text-gray-100">❓ Kullanım Rehberi</h1>
      <p class="text-sm text-gray-500 mt-0.5">
        Bilge Yolcu Kontrol Paneli'nin nasıl kullanılacağını öğrenin
      </p>
    </div>

    <!-- İş Akışı Diyagramı -->
    <div class="card p-5">
      <h2 class="text-sm font-semibold text-gray-300 mb-3">📋 Genel İş Akışı</h2>
      <div class="flex items-center justify-center gap-2 flex-wrap py-2">
        <div v-for="(step, i) in [
          { icon: '⚡', label: 'Görev Oluştur', sub: 'Konu + Ton + Uzunluk' },
          { icon: '🤖', label: 'AI Üretir', sub: 'Gemini / Claude / GPT' },
          { icon: '📝', label: 'Yayın Kuyruğu', sub: 'Düzenle + İyileştir' },
          { icon: '🚀', label: 'XenForo\'ya Yayınla', sub: 'Forum + Etiketler' },
        ]" :key="i"
          class="flex items-center gap-2">
          <div class="flow-step">
            <span class="text-xl">{{ step.icon }}</span>
            <span class="text-xs font-medium text-gray-200">{{ step.label }}</span>
            <span class="text-[10px] text-gray-500">{{ step.sub }}</span>
          </div>
          <span v-if="i < 3" class="text-gray-600 text-lg">→</span>
        </div>
      </div>
    </div>

    <!-- Accordion Bölümler -->
    <div class="space-y-2">
      <div v-for="s in sections" :key="s.id"
           class="card overflow-hidden">
        <button @click="toggle(s.id)"
                :class="['w-full flex items-center gap-3 px-5 py-4 text-left transition-all',
                         openSection === s.id ? 'bg-indigo-500/5' : 'hover:bg-gray-700/20']">
          <span class="text-lg">{{ s.icon }}</span>
          <span class="text-sm font-medium text-gray-200 flex-1">{{ s.title }}</span>
          <span :class="['text-gray-500 text-xs transition-transform duration-200',
                         openSection === s.id ? 'rotate-180' : '']">▼</span>
        </button>

        <Transition name="accordion">
          <div v-if="openSection === s.id"
               class="px-5 pb-5 text-sm text-gray-400 leading-relaxed guide-content"
               v-html="s.content" />
        </Transition>
      </div>
    </div>

    <!-- Sürüm bilgisi -->
    <div class="text-center text-xs text-gray-700 py-4">
      Bilge Yolcu Kontrol Paneli — v2.0.0
    </div>
  </div>
</template>

<style scoped>
.flow-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  padding: 0.75rem 1rem;
  background: rgba(31, 41, 55, 0.5);
  border: 1px solid rgba(55, 65, 81, 0.4);
  border-radius: 0.75rem;
  min-width: 120px;
  text-align: center;
}

.guide-content :deep(strong) {
  color: #e5e7eb;
  font-weight: 600;
}

.accordion-enter-active,
.accordion-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}
.accordion-enter-from,
.accordion-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}
.accordion-enter-to,
.accordion-leave-from {
  opacity: 1;
  max-height: 1000px;
}
</style>

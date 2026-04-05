<script setup>
/**
 * TaskForms.vue — YouTube ve Makale görev formları.
 * v2: 24 ton çoklu seçim, kategori forum listesinden, uzunluk güncellendi.
 */

import { ref, reactive, onMounted, computed } from 'vue'
import { useTaskStore }   from '@/stores/tasks'
import { useBudgetStore } from '@/stores/budget'
import api                from '@/services/api'

const taskStore   = useTaskStore()
const budgetStore = useBudgetStore()
const activeTab   = ref('youtube')

// ── Node ağaç yardımcısı (parent category name lookup) ────
const allNodes = ref([])    // Tüm node'lar (Category + Forum)
const xfNodes  = computed(() =>
  allNodes.value.filter(n => n.node_type_id === 'Forum' || !n.node_type_id)
)
const nodeMap = computed(() => {
  const map = {}
  for (const n of allNodes.value) map[n.node_id] = n
  return map
})
function nodeLabel(n) {
  const parent = nodeMap.value[n.parent_node_id]
  if (parent) return `${parent.title || parent.node_name} › ${n.title || n.node_name}`
  return n.title || n.node_name
}

// ── XenForo forum listesi ────────────────────────────────
onMounted(async () => {
  try {
    const { data } = await api.get('/xenforo/nodes?flat=1')
    allNodes.value = data.data || []
  } catch { /* XenForo bağlı değilse sessizce atla */ }
})

// ── YouTube formu ────────────────────────────────────────
const ytForm = reactive({
  url:         '',
  extra_notes: '',
  max_tokens:  2500,
  xf_node_id:  '',
  manual_transcript: '',   // Elle yapıştırılan transkript
})
const showManualTranscript = ref(false)

async function submitYoutube() {
  if (!ytForm.url) return
  const payload = { ...ytForm }
  if (!payload.xf_node_id) delete payload.xf_node_id
  if (!payload.manual_transcript) delete payload.manual_transcript
  const result = await taskStore.queueYoutube(payload)
  if (result) { ytForm.url = ''; ytForm.extra_notes = ''; ytForm.xf_node_id = ''; ytForm.manual_transcript = ''; showManualTranscript.value = false }
}

// ── Makale formu ─────────────────────────────────────────
const articleForm = reactive({
  topic:       '',
  tones:       ['felsefi'],   // Çoklu seçim — array
  length:      'orta',
  temperature: 0.75,
  top_p:       0.9,
  freq_penalty: 0.3,
  xf_node_id:  '',
})

const TONE_OPTIONS = [
  { value: 'felsefi',       emoji: '🔮', label: 'Felsefi' },
  { value: 'bilimsel',      emoji: '🔬', label: 'Bilimsel' },
  { value: 'anlati',        emoji: '📖', label: 'Anlatı' },
  { value: 'seo',           emoji: '🔍', label: 'SEO' },
  { value: 'yaratici',      emoji: '💡', label: 'Yaratıcı' },
  { value: 'haber',         emoji: '📰', label: 'Haber' },
  { value: 'egitici',       emoji: '🎓', label: 'Eğitici' },
  { value: 'sohbet',        emoji: '💬', label: 'Sohbet' },
  { value: 'polemik',       emoji: '⚔️', label: 'Polemik' },
  { value: 'ilham_verici',  emoji: '🌟', label: 'İlham Verici' },
  { value: 'satirik',       emoji: '🎭', label: 'Satirik' },
  { value: 'karsilastirma', emoji: '⚖️', label: 'Karşılaştırma' },
  { value: 'tarihsel',      emoji: '🏛️', label: 'Tarihsel' },
  { value: 'teknik',        emoji: '🛠️', label: 'Teknik' },
  { value: 'psikolojik',    emoji: '🧠', label: 'Psikolojik' },
  { value: 'spekulatif',    emoji: '🚀', label: 'Spekülatif' },
  { value: 'minimalist',    emoji: '✂️', label: 'Minimalist' },
  { value: 'akademik',      emoji: '📋', label: 'Akademik' },
  { value: 'elestirel',     emoji: '🔎', label: 'Eleştirel' },
  { value: 'mektup',        emoji: '✉️', label: 'Mektup' },
  { value: 'manifesto',     emoji: '📣', label: 'Manifesto' },
  { value: 'diyalog',       emoji: '🎙️', label: 'Diyalog' },
  { value: 'mitolojik',     emoji: '🐉', label: 'Mitolojik' },
  { value: 'deneme',        emoji: '✍️', label: 'Deneme' },
]

const LENGTH_OPTIONS = [
  { value: 'kısa',     label: 'Kısa',     desc: '~700 kelime' },
  { value: 'orta',     label: 'Orta',     desc: '~1500 kelime' },
  { value: 'uzun',     label: 'Uzun',     desc: '~3000 kelime' },
  { value: 'çok_uzun', label: 'Çok Uzun', desc: '~5000 kelime' },
]

// Ton toggle
function toggleTone(tone) {
  const idx = articleForm.tones.indexOf(tone)
  if (idx >= 0) {
    if (articleForm.tones.length > 1) articleForm.tones.splice(idx, 1)
  } else {
    articleForm.tones.push(tone)
  }
}

// Ton açık mı?
function isToneSelected(tone) {
  return articleForm.tones.includes(tone)
}

// Seçilen tonları birleştir (backend'e gönderirken)
const toneString = computed(() => articleForm.tones.join('+'))

// Ton dropdown
const showToneDropdown = ref(false)
const selectedTonesLabel = computed(() => {
  if (articleForm.tones.length === 0) return 'Ton seçin'
  if (articleForm.tones.length <= 3) {
    return articleForm.tones.map(t => {
      const opt = TONE_OPTIONS.find(o => o.value === t)
      return opt ? `${opt.emoji} ${opt.label}` : t
    }).join(', ')
  }
  return `${articleForm.tones.length} ton seçili`
})

async function submitArticle() {
  if (!articleForm.topic) return
  const payload = {
    topic: articleForm.topic,
    tone: toneString.value,
    length: articleForm.length,
    temperature: articleForm.temperature,
    top_p: articleForm.top_p,
    frequency_penalty: articleForm.freq_penalty,
    xf_node_id: articleForm.xf_node_id || undefined,
  }
  if (!payload.xf_node_id) delete payload.xf_node_id
  await taskStore.queueArticle(payload)
}
</script>

<template>
  <div class="space-y-4 animate-fade-in">

    <!-- Başlık + Circuit Breaker uyarısı -->
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-semibold text-gray-100">Yeni Görev</h2>
      <div v-if="budgetStore.isBlocked"
           class="flex items-center gap-2 bg-red-500/10 border border-red-500/30
                  text-red-400 text-xs px-3 py-1.5 rounded-lg animate-pulse">
        🔒 Bütçe Kilidi Aktif
      </div>
    </div>

    <!-- Sekme başlıkları -->
    <div class="flex gap-1 bg-gray-900 rounded-xl p-1">
      <button v-for="tab in [
                { id: 'youtube', label: '📺 YouTube → Makale' },
                { id: 'article', label: '✍️ Otonom Makale' },
              ]"
              :key="tab.id"
              @click="activeTab = tab.id"
              :class="['flex-1 py-2 rounded-lg text-sm font-medium transition-all duration-150',
                       activeTab === tab.id
                         ? 'bg-gray-800 text-gray-100 shadow-md'
                         : 'text-gray-400 hover:text-gray-200']">
        {{ tab.label }}
      </button>
    </div>

    <!-- Bildirimler -->
    <Transition name="slide-fade">
      <div v-if="taskStore.success"
           class="bg-emerald-500/10 border border-emerald-500/30 text-emerald-400
                  text-sm px-4 py-2.5 rounded-lg flex items-center gap-2">
        ✓ {{ taskStore.success }}
      </div>
    </Transition>
    <Transition name="slide-fade">
      <div v-if="taskStore.error"
           class="bg-red-500/10 border border-red-500/30 text-red-400
                  text-sm px-4 py-2.5 rounded-lg">
        {{ taskStore.error }}
      </div>
    </Transition>

    <!-- ══ YOUTUBE FORMU ══════════════════════════════════ -->
    <div v-if="activeTab === 'youtube'" class="card p-6 space-y-4 animate-fade-in">

      <div>
        <label class="field-label">YouTube URL <span class="text-red-500">*</span></label>
        <input v-model="ytForm.url" type="url" class="input-field"
               placeholder="https://youtube.com/watch?v=..."
               :disabled="budgetStore.isBlocked" />
        <div class="mt-1.5 flex items-center justify-between">
          <p class="text-xs text-gray-500">
            TR → EN → oto dil sırası. 7 gün Redis önbellek.
          </p>
          <button @click="showManualTranscript = !showManualTranscript"
                  :class="['text-xs px-2 py-0.5 rounded transition-colors',
                           showManualTranscript
                             ? 'bg-amber-500/15 text-amber-400 border border-amber-500/30'
                             : 'text-gray-500 hover:text-gray-300 border border-gray-700']"
                  type="button">
            {{ showManualTranscript ? '✕ Kapat' : '📋 Transkripti Elle Yapıştır' }}
          </button>
        </div>
      </div>

      <!-- Manuel Transkript Alanı -->
      <Transition name="slide-fade">
        <div v-if="showManualTranscript" class="space-y-2">
          <div class="bg-amber-500/5 border border-amber-500/20 rounded-lg p-3">
            <div class="flex items-center gap-2 mb-2">
              <span class="text-amber-400 text-sm">⚠️</span>
              <span class="text-xs text-amber-300 font-medium">Manuel Transkript Modu</span>
            </div>
            <p class="text-xs text-gray-400">
              YouTube API erişimi engelleniyorsa, transkripti
              <a href="https://youtubetotranscript.com/" target="_blank" class="text-indigo-400 hover:underline">youtubetotranscript.com</a>
              gibi bir siteden kopyalayıp aşağıya yapıştırabilirsiniz.
            </p>
          </div>
          <textarea v-model="ytForm.manual_transcript" class="textarea-field" rows="6"
                    placeholder="Transkript metnini buraya yapıştırın..."
                    :disabled="budgetStore.isBlocked" />
          <div class="text-xs text-gray-600">
            {{ ytForm.manual_transcript ? `~${ytForm.manual_transcript.split(/\s+/).length} kelime` : '' }}
          </div>
        </div>
      </Transition>

      <div>
        <label class="field-label">Yönlendirme Notu</label>
        <textarea v-model="ytForm.extra_notes" class="textarea-field" rows="2"
                  placeholder="Makaleyi yazarken özellikle şuna odaklan..."
                  :disabled="budgetStore.isBlocked" />
      </div>

      <div class="flex items-center justify-between">
        <div class="text-xs text-gray-500 space-y-0.5">
          <div>Max çıktı: {{ ytForm.max_tokens }} token</div>
          <div class="text-gray-600">~{{ Math.round(ytForm.max_tokens * 0.75) }} kelime</div>
        </div>
        <input v-model.number="ytForm.max_tokens"
               type="range" min="800" max="4000" step="100"
               class="w-32 accent-indigo-500"
               :disabled="budgetStore.isBlocked" />
      </div>

      <!-- XenForo yayın hedefi -->
      <div v-if="xfNodes.length">
        <label class="field-label">Foruma Yayınla</label>
        <select v-model="ytForm.xf_node_id" class="select-field"
                :disabled="budgetStore.isBlocked">
          <option value="">— Sadece üret, yayınlama —</option>
          <option v-for="n in xfNodes" :key="n.node_id" :value="n.node_id">
            {{ nodeLabel(n) }}
          </option>
        </select>
      </div>

      <button @click="submitYoutube" class="btn-primary w-full justify-center py-3"
              :disabled="!ytForm.url || taskStore.isQueuing || budgetStore.isBlocked">
        <span v-if="taskStore.isQueuing" class="animate-spin-slow">⚙</span>
        <span v-else>🚀</span>
        {{ taskStore.isQueuing
            ? 'Kuyruğa alınıyor...'
            : ytForm.xf_node_id ? 'Kuyruğa Al & Yayınla' : 'Kuyruğa Al' }}
      </button>
    </div>

    <!-- ══ MAKALE FORMU ═══════════════════════════════════ -->
    <div v-if="activeTab === 'article'" class="card p-6 space-y-5 animate-fade-in">

      <!-- Yazı Hakkında -->
      <div>
        <label class="field-label">Yazı Hakkında <span class="text-red-500">*</span></label>
        <textarea v-model="articleForm.topic" class="textarea-field" rows="3"
               placeholder="Yazının konusu, odak noktaları ve dahil edilmesini istediğiniz detayları buraya yazın. Örn: Stoacı felsefenin modern kaygı yönetimine etkisini, Marcus Aurelius ve Epiktetos örnekleriyle açıkla..."
               :disabled="budgetStore.isBlocked" />
        <p class="mt-1 text-xs text-gray-600">Konu, odak ve talimatlarınızı detaylı yazın — AI tüm açıklamayı dikkate alır.</p>
      </div>

      <!-- Yazım Stili — Çoklu Seçim Dropdown -->
      <div class="relative">
        <label class="field-label">Yazım Stili (Çoklu Seçim)</label>
        <button @click="showToneDropdown = !showToneDropdown"
                :disabled="budgetStore.isBlocked"
                :class="['w-full text-left input-field flex items-center justify-between',
                         showToneDropdown ? 'ring-2 ring-indigo-500/50 border-indigo-500/50' : '']">
          <span class="text-sm truncate">{{ selectedTonesLabel }}</span>
          <span :class="['text-gray-500 text-xs transition-transform duration-200',
                         showToneDropdown ? 'rotate-180' : '']">▼</span>
        </button>

        <!-- Dropdown panel -->
        <Transition name="fade">
          <div v-if="showToneDropdown"
               class="absolute z-50 left-0 right-0 mt-1 bg-gray-800 border border-gray-700/50
                      rounded-lg shadow-xl max-h-60 overflow-y-auto py-1">
            <button v-for="opt in TONE_OPTIONS" :key="opt.value"
                    @click="toggleTone(opt.value)"
                    :class="['w-full flex items-center gap-2 px-3 py-1.5 text-left text-sm transition-colors',
                             isToneSelected(opt.value)
                               ? 'bg-indigo-500/10 text-indigo-300'
                               : 'text-gray-400 hover:bg-gray-700/50 hover:text-gray-200']">
              <span class="w-4 text-center">
                {{ isToneSelected(opt.value) ? '✓' : '' }}
              </span>
              <span>{{ opt.emoji }} {{ opt.label }}</span>
            </button>
          </div>
        </Transition>
      </div>
      <!-- Dropdown dışı tıklama -->
      <div v-if="showToneDropdown" class="fixed inset-0 z-40" @click="showToneDropdown = false" />

      <!-- Uzunluk -->
      <div>
        <label class="field-label">Uzunluk</label>
        <div class="grid grid-cols-4 gap-2">
          <button v-for="opt in LENGTH_OPTIONS" :key="opt.value"
                  @click="articleForm.length = opt.value"
                  :class="['py-2 px-2 rounded-lg border text-center text-sm transition-all duration-150',
                           articleForm.length === opt.value
                             ? 'border-indigo-500/50 bg-indigo-500/10 text-indigo-300'
                             : 'border-gray-700 bg-gray-900/50 text-gray-400 hover:border-gray-600']"
                  :disabled="budgetStore.isBlocked">
            <div class="font-medium text-xs">{{ opt.label }}</div>
            <div class="text-[10px] text-gray-500">{{ opt.desc }}</div>
          </button>
        </div>
      </div>

      <!-- AI Parametre Slider'ları -->
      <div class="space-y-3 bg-gray-900/40 rounded-lg p-4 border border-gray-700/30">
        <div class="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">Üretim Parametreleri</div>

        <!-- Yaratıcılık (temperature) -->
        <div class="flex items-center gap-3">
          <label class="field-label mb-0 whitespace-nowrap text-xs w-28" title="Daha yüksek değer = daha yaratıcı, daha düşük = daha tutarlı">🎨 Yaratıcılık</label>
          <input v-model.number="articleForm.temperature"
                 type="range" min="0.3" max="1.0" step="0.05"
                 class="flex-1 accent-indigo-500" :disabled="budgetStore.isBlocked" />
          <span class="text-xs text-indigo-400 tabular-nums w-8">{{ articleForm.temperature.toFixed(2) }}</span>
        </div>

        <!-- Odaklanma (top_p) -->
        <div class="flex items-center gap-3">
          <label class="field-label mb-0 whitespace-nowrap text-xs w-28" title="Düşük = odaklı, yüksek = çeşitli kelime seçimleri">🎯 Odaklanma</label>
          <input v-model.number="articleForm.top_p"
                 type="range" min="0.5" max="1.0" step="0.05"
                 class="flex-1 accent-emerald-500" :disabled="budgetStore.isBlocked" />
          <span class="text-xs text-emerald-400 tabular-nums w-8">{{ articleForm.top_p.toFixed(2) }}</span>
        </div>

        <!-- Tekrar Engelleme (frequency_penalty) -->
        <div class="flex items-center gap-3">
          <label class="field-label mb-0 whitespace-nowrap text-xs w-28" title="Yüksek değer tekrarlayan ifadeleri azaltır">🔄 Tekrar Engeli</label>
          <input v-model.number="articleForm.freq_penalty"
                 type="range" min="0.0" max="1.0" step="0.1"
                 class="flex-1 accent-amber-500" :disabled="budgetStore.isBlocked" />
          <span class="text-xs text-amber-400 tabular-nums w-8">{{ articleForm.freq_penalty.toFixed(1) }}</span>
        </div>
      </div>

      <!-- XenForo yayın hedefi -->
      <div v-if="xfNodes.length">
        <label class="field-label">Foruma Yayınla</label>
        <select v-model="articleForm.xf_node_id" class="select-field"
                :disabled="budgetStore.isBlocked">
          <option value="">— Sadece üret, yayınlama —</option>
          <option v-for="n in xfNodes" :key="n.node_id" :value="n.node_id">
            {{ nodeLabel(n) }}
          </option>
        </select>
        <p v-if="articleForm.xf_node_id"
           class="mt-1.5 text-xs text-indigo-400">
          ✓ Görev tamamlanınca seçili foruma otomatik yayınlanır.
        </p>
      </div>

      <button @click="submitArticle" class="btn-primary w-full justify-center py-3"
              :disabled="!articleForm.topic || taskStore.isQueuing || budgetStore.isBlocked">
        <span v-if="taskStore.isQueuing" class="animate-spin-slow">⚙</span>
        <span v-else>✍️</span>
        {{ taskStore.isQueuing
            ? 'Kuyruğa alınıyor...'
            : articleForm.xf_node_id ? 'Yaz & Yayınla' : 'Makale Yaz' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.slide-fade-enter-active, .slide-fade-leave-active { transition: all 0.25s ease; }
.slide-fade-enter-from { opacity: 0; transform: translateY(-8px); }
.slide-fade-leave-to   { opacity: 0; transform: translateY(-4px); }
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>

<script setup>
/**
 * TaskForms.vue — YouTube ve Makale görev formları.
 * xf_node_id ile doğrudan forum seçimi ve yayınlama desteği eklendi.
 */

import { ref, reactive, onMounted } from 'vue'
import { useTaskStore }   from '@/stores/tasks'
import { useBudgetStore } from '@/stores/budget'
import api                from '@/services/api'

const taskStore   = useTaskStore()
const budgetStore = useBudgetStore()
const activeTab   = ref('youtube')

// ── XenForo forum listesi (yayın hedefi seçimi) ─────────
const xfNodes = ref([])
onMounted(async () => {
  try {
    const { data } = await api.get('/xenforo/nodes?flat=1')
    xfNodes.value = (data.data || []).filter(
      n => n.node_type_id === 'Forum' || !n.node_type_id,
    )
  } catch { /* XenForo bağlı değilse sessizce atla */ }
})

// ── YouTube formu ────────────────────────────────────────
const ytForm = reactive({
  url:         '',
  extra_notes: '',
  max_tokens:  2500,
  xf_node_id:  '',   // Boşsa yayınlanmaz — sadece üretilir
})

async function submitYoutube() {
  if (!ytForm.url) return
  const payload = { ...ytForm }
  if (!payload.xf_node_id) delete payload.xf_node_id
  const result = await taskStore.queueYoutube(payload)
  if (result) { ytForm.url = ''; ytForm.extra_notes = ''; ytForm.xf_node_id = '' }
}

// ── Makale formu ─────────────────────────────────────────
const articleForm = reactive({
  topic:       '',
  tone:        'felsefi',
  length:      'orta',
  category:    '',
  keywords:    '',
  extra_notes: '',
  temperature: 0.75,
  xf_node_id:  '',
})

const TONE_OPTIONS = [
  { value: 'felsefi',  label: '🧠 Felsefi',  desc: 'Spekülatif, soru soran' },
  { value: 'bilimsel', label: '🔬 Bilimsel', desc: 'Kanıt odaklı, akademik' },
  { value: 'anlatı',   label: '📖 Anlatı',   desc: 'Hikâye örgüsü, edebi' },
  { value: 'seo',      label: '🔍 SEO',      desc: 'Arama motoru optimized' },
]

const LENGTH_OPTIONS = [
  { value: 'kısa', label: 'Kısa', desc: '~500 kelime' },
  { value: 'orta', label: 'Orta', desc: '~900 kelime' },
  { value: 'uzun', label: 'Uzun', desc: '~1500 kelime' },
]

async function submitArticle() {
  if (!articleForm.topic) return
  const payload = { ...articleForm }
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
        <p class="mt-1.5 text-xs text-gray-500">
          TR → EN → oto dil sırası. 7 gün Redis önbellek.
        </p>
      </div>

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
            [{{ n.node_id }}] {{ n.title || n.node_name }}
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

      <!-- Konu -->
      <div>
        <label class="field-label">Konu <span class="text-red-500">*</span></label>
        <input v-model="articleForm.topic" type="text" class="input-field"
               placeholder="Stoicism ve modern kaygı yönetimi..."
               :disabled="budgetStore.isBlocked" />
      </div>

      <!-- Ton seçimi (2×2 grid) -->
      <div>
        <label class="field-label">Yazı Tonu</label>
        <div class="grid grid-cols-2 gap-2">
          <button v-for="opt in TONE_OPTIONS" :key="opt.value"
                  @click="articleForm.tone = opt.value"
                  :class="['flex flex-col items-start p-3 rounded-lg border text-left transition-all duration-150',
                           articleForm.tone === opt.value
                             ? 'border-indigo-500/50 bg-indigo-500/10 text-gray-100'
                             : 'border-gray-700 bg-gray-900/50 text-gray-400 hover:border-gray-600']"
                  :disabled="budgetStore.isBlocked">
            <span class="text-sm font-medium">{{ opt.label }}</span>
            <span class="text-xs text-gray-500 mt-0.5">{{ opt.desc }}</span>
          </button>
        </div>
      </div>

      <!-- Uzunluk -->
      <div>
        <label class="field-label">Uzunluk</label>
        <div class="flex gap-2">
          <button v-for="opt in LENGTH_OPTIONS" :key="opt.value"
                  @click="articleForm.length = opt.value"
                  :class="['flex-1 py-2 px-3 rounded-lg border text-center text-sm transition-all duration-150',
                           articleForm.length === opt.value
                             ? 'border-indigo-500/50 bg-indigo-500/10 text-indigo-300'
                             : 'border-gray-700 bg-gray-900/50 text-gray-400 hover:border-gray-600']"
                  :disabled="budgetStore.isBlocked">
            <div class="font-medium">{{ opt.label }}</div>
            <div class="text-xs text-gray-500">{{ opt.desc }}</div>
          </button>
        </div>
      </div>

      <!-- Kategori + Anahtar Kelimeler -->
      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="field-label">Kategori</label>
          <input v-model="articleForm.category" type="text" class="input-field"
                 placeholder="Felsefe" :disabled="budgetStore.isBlocked" />
        </div>
        <div>
          <label class="field-label">Anahtar Kelimeler</label>
          <input v-model="articleForm.keywords" type="text" class="input-field"
                 placeholder="stoicism, kaygı" :disabled="budgetStore.isBlocked" />
        </div>
      </div>

      <!-- Ek not -->
      <div>
        <label class="field-label">Yönlendirme Notu</label>
        <textarea v-model="articleForm.extra_notes" class="textarea-field" rows="2"
                  placeholder="Marcus Aurelius'a odaklan..."
                  :disabled="budgetStore.isBlocked" />
      </div>

      <!-- Yaratıcılık slider -->
      <div class="flex items-center gap-4">
        <label class="field-label mb-0 whitespace-nowrap">Yaratıcılık</label>
        <input v-model.number="articleForm.temperature"
               type="range" min="0.3" max="1.0" step="0.05"
               class="flex-1 accent-indigo-500" :disabled="budgetStore.isBlocked" />
        <span class="text-sm text-indigo-400 tabular-nums w-8">
          {{ articleForm.temperature.toFixed(2) }}
        </span>
      </div>

      <!-- XenForo yayın hedefi -->
      <div v-if="xfNodes.length">
        <label class="field-label">Foruma Yayınla</label>
        <select v-model="articleForm.xf_node_id" class="select-field"
                :disabled="budgetStore.isBlocked">
          <option value="">— Sadece üret, yayınlama —</option>
          <option v-for="n in xfNodes" :key="n.node_id" :value="n.node_id">
            [{{ n.node_id }}] {{ n.title || n.node_name }}
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
</style>

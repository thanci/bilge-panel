<script setup>
/**
 * PublishView.vue — Yayın Kuyruğu & Gelişmiş Editör.
 * Sol panel: taslak listesi  |  Sağ panel: TipTap editör + stil/AI
 */

import { ref, computed, onMounted, watch } from 'vue'
import { usePublishStore } from '@/stores/publish'
import { useRoute } from 'vue-router'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import RichEditor from '@/components/editor/RichEditor.vue'
import api from '@/services/api'

const publishStore = usePublishStore()
const route = useRoute()

// XenForo forumları
const xfNodes = ref([])

// Editör state
const editTitle     = ref('')
const editContent   = ref('')
const editCategory  = ref('')
const editTags      = ref('')
const editNodeId    = ref('')
const editTone      = ref('felsefi')
const hasChanges    = ref(false)

// AI İşlemi
const aiProcessing  = ref(false)
const aiError       = ref('')

// Stiller — 24 ton
const TONE_OPTIONS = [
  { value: 'felsefi',       emoji: '🔮', label: 'Felsefi' },
  { value: 'bilimsel',      emoji: '🔬', label: 'Bilimsel' },
  { value: 'anlati',        emoji: '📖', label: 'Anlatı / Hikâye' },
  { value: 'seo',           emoji: '🔍', label: 'SEO Odaklı' },
  { value: 'yaratici',      emoji: '💡', label: 'Yaratıcı' },
  { value: 'haber',         emoji: '📰', label: 'Haber / Güncel' },
  { value: 'egitici',       emoji: '🎓', label: 'Eğitici / Didaktik' },
  { value: 'sohbet',        emoji: '💬', label: 'Sohbet / Kişisel' },
  { value: 'polemik',       emoji: '⚔️', label: 'Polemik / Tartışmacı' },
  { value: 'ilham_verici',  emoji: '🌟', label: 'İlham Verici' },
  { value: 'satirik',       emoji: '🎭', label: 'Satirik / İronik' },
  { value: 'karsilastirma', emoji: '⚖️', label: 'Karşılaştırmalı Analiz' },
  { value: 'tarihsel',      emoji: '🏛️', label: 'Tarihsel / Kronolojik' },
  { value: 'teknik',        emoji: '🛠️', label: 'Teknik / Rehber' },
  { value: 'psikolojik',    emoji: '🧠', label: 'Psikolojik' },
  { value: 'spekulatif',    emoji: '🚀', label: 'Spekülatif / Gelecekçi' },
  { value: 'minimalist',    emoji: '✂️', label: 'Minimalist / Öz' },
  { value: 'akademik',      emoji: '📋', label: 'Akademik / Tez' },
  { value: 'elestirel',     emoji: '🔎', label: 'Eleştirel / Derin Okuma' },
  { value: 'mektup',        emoji: '✉️', label: 'Mektup / Hitap' },
  { value: 'manifesto',     emoji: '📣', label: 'Manifesto' },
  { value: 'diyalog',       emoji: '🎙️', label: 'Diyalog / Söyleşi' },
  { value: 'mitolojik',     emoji: '🐉', label: 'Mitolojik / Sembolik' },
  { value: 'deneme',        emoji: '✍️', label: 'Deneme (Essay)' },
]

onMounted(async () => {
  await publishStore.fetchDrafts()

  // XenForo forumlarını yükle
  try {
    const { data } = await api.get('/xenforo/nodes?flat=1')
    xfNodes.value = (data.data || []).filter(
      n => n.node_type_id === 'Forum' || !n.node_type_id,
    )
  } catch { /* XenForo bağlı değilse sessizce atla */ }

  // URL'den draft parametresi varsa onu aç
  if (route.query.draft) {
    await publishStore.selectDraft(parseInt(route.query.draft))
  }
})

// Aktif taslak değişince editörü güncelle
watch(() => publishStore.activeDraft, (draft) => {
  if (draft) {
    editTitle.value    = draft.title || ''
    editContent.value  = draft.content || ''
    editCategory.value = draft.category || ''
    editNodeId.value   = draft.xf_node_id || ''
    editTone.value     = draft.tone || 'felsefi'
    editTags.value     = Array.isArray(draft.tags)
      ? draft.tags.join(', ')
      : (draft.tags || '')
    hasChanges.value = false
  }
}, { immediate: true })

// Değişiklik takibi
function markChanged() { hasChanges.value = true }

function formatDate(str) {
  if (!str) return '—'
  return new Intl.DateTimeFormat('tr-TR', {
    month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  }).format(new Date(str))
}

// ── Yeni Taslak Oluştur ─────────────────────────────
async function createNewDraft() {
  try {
    await publishStore.createDraft({
      title: 'Başlıksız Taslak',
      content: '',
      category: '',
      tone: editTone.value,
    })
  } catch (e) {
    const msg = e.response?.data?.message || e.response?.data?.error || e.message || 'Bilinmeyen hata'
    publishStore.error = 'Taslak oluşturulamadı: ' + msg
  }
}

// ── Kelime sayısı ───────────────────────────────────
const wordCount = computed(() => {
  const text = editContent.value.replace(/\[.*?\]/g, '').trim()
  return text ? text.split(/\s+/).length : 0
})

// ── Kaydet ──────────────────────────────────────────
async function handleSave() {
  if (!publishStore.activeDraft) return
  const tags = editTags.value
    .split(',')
    .map(t => t.trim())
    .filter(Boolean)

  await publishStore.saveDraft(publishStore.activeDraft.id, {
    title:      editTitle.value,
    content:    editContent.value,
    category:   editCategory.value,
    tags:       tags,
    xf_node_id: editNodeId.value || null,
    tone:       editTone.value,
  })
  hasChanges.value = false
}

// ── Yayınla ─────────────────────────────────────────
async function handlePublish() {
  if (!publishStore.activeDraft) return
  if (!editNodeId.value) {
    publishStore.error = 'Lütfen bir hedef forum seçin.'
    return
  }
  if (hasChanges.value) await handleSave()
  if (confirm('Bu içeriği XenForo\'ya yayınlamak istediğinize emin misiniz?')) {
    await publishStore.publishDraft(publishStore.activeDraft.id)
  }
}

// ── Sil ─────────────────────────────────────────────
async function handleDelete(draftId) {
  if (!confirm('Bu taslağı kalıcı olarak silmek istediğinize emin misiniz?')) return
  await publishStore.deleteDraft(draftId)
}

// ── AI Editör Aksiyonları ───────────────────────────
async function handleAiAction({ action, selectedText, fullText }) {
  aiProcessing.value = true
  aiError.value = ''

  try {
    const { data } = await api.post('/publish/ai-enhance', {
      action,
      selected_text: selectedText,
      full_text: fullText,
      tone: editTone.value,
    })

    if (data.success && data.data?.content) {
      if (action === 'longer' || action === 'continue') {
        // Tam metin değiştirme
        editContent.value = data.data.content
      } else if (selectedText && data.data.content) {
        // Seçili metin değiştirme
        editContent.value = editContent.value.replace(selectedText, data.data.content)
      } else {
        editContent.value = data.data.content
      }
      hasChanges.value = true
      publishStore.success = 'AI işlemi tamamlandı.'
      setTimeout(() => publishStore.success = '', 3000)
    }
  } catch (e) {
    aiError.value = e.response?.data?.error || 'AI işlemi başarısız.'
    setTimeout(() => aiError.value = '', 5000)
  } finally {
    aiProcessing.value = false
  }
}
</script>

<template>
  <div class="max-w-screen-xl mx-auto space-y-4 animate-fade-in">

    <!-- Başlık -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-xl font-bold text-gray-100">📝 Yayın Kuyruğu</h1>
        <p class="text-sm text-gray-500 mt-0.5">
          İçerikleri düzenle, önizle ve XenForo'ya yayınla
        </p>
      </div>
      <div class="flex items-center gap-3">
        <div v-if="publishStore.draftCount > 0"
             class="bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs px-3 py-1 rounded-full">
          {{ publishStore.draftCount }} taslak
        </div>
        <div v-if="publishStore.publishedCount > 0"
             class="bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs px-3 py-1 rounded-full">
          {{ publishStore.publishedCount }} yayınlandı
        </div>
      </div>
    </div>

    <!-- Bildirimler -->
    <Transition name="slide-fade">
      <div v-if="publishStore.success"
           class="bg-emerald-500/10 border border-emerald-500/30 text-emerald-400
                  text-sm px-4 py-2.5 rounded-lg flex items-center gap-2">
        ✓ {{ publishStore.success }}
      </div>
    </Transition>
    <Transition name="slide-fade">
      <div v-if="publishStore.error || aiError"
           class="bg-red-500/10 border border-red-500/30 text-red-400
                  text-sm px-4 py-2.5 rounded-lg">
        {{ publishStore.error || aiError }}
      </div>
    </Transition>

    <!-- AI İşleniyor overlay -->
    <Transition name="slide-fade">
      <div v-if="aiProcessing"
           class="bg-indigo-500/10 border border-indigo-500/30 text-indigo-400
                  text-sm px-4 py-2.5 rounded-lg flex items-center gap-2">
        <span class="animate-spin">⚙</span> AI içeriği işliyor...
      </div>
    </Transition>

    <!-- Ana içerik: Sol + Sağ panel -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-4" style="min-height: 70vh;">

      <!-- ═══ SOL PANEL: Taslak Listesi ═══ -->
      <div class="lg:col-span-3 space-y-3">

        <!-- Yeni Taslak butonu -->
        <button @click="createNewDraft"
                class="w-full py-2.5 rounded-lg text-sm font-medium
                       bg-indigo-500/10 border border-indigo-500/20 text-indigo-400
                       hover:bg-indigo-500/15 hover:border-indigo-500/30
                       transition-all flex items-center justify-center gap-2">
          ＋ Yeni Taslak Oluştur
        </button>

        <!-- Filtre -->
        <div class="flex gap-1 bg-gray-900 rounded-lg p-1">
          <button v-for="opt in [
                    { value: 'all',       label: 'Tümü' },
                    { value: 'DRAFT',     label: '📝 Taslak' },
                    { value: 'PUBLISHED', label: '✅ Yayınlanan' },
                  ]" :key="opt.value"
                  @click="publishStore.setFilter(opt.value)"
                  :class="['flex-1 py-1.5 rounded-md text-xs font-medium transition-all',
                           publishStore.filter === opt.value
                             ? 'bg-gray-800 text-gray-100 shadow'
                             : 'text-gray-400 hover:text-gray-200']">
            {{ opt.label }}
          </button>
        </div>

        <!-- Yükleniyor -->
        <div v-if="publishStore.isLoading && !publishStore.drafts.length" class="space-y-2">
          <div v-for="i in 4" :key="i"
               class="h-16 bg-gray-800/60 animate-pulse rounded-lg" />
        </div>

        <!-- Boş durum -->
        <div v-else-if="!publishStore.filteredDrafts.length"
             class="text-center py-12 text-gray-600">
          <div class="text-3xl mb-3">📭</div>
          <div class="text-sm">Henüz taslak yok</div>
          <p class="text-xs text-gray-700 mt-2">
            Yukarıdaki butona tıklayarak yeni taslak oluşturun veya
            görev kuyruğundan "Yayına Gönder" ile taslak ekleyin.
          </p>
        </div>

        <!-- Taslak listesi -->
        <div v-else class="space-y-2 max-h-[65vh] overflow-y-auto pr-1">
          <div v-for="draft in publishStore.filteredDrafts" :key="draft.id"
               @click="publishStore.selectDraft(draft.id)"
               :class="['draft-card group transition-all duration-150',
                        publishStore.activeDraft?.id === draft.id
                          ? 'border-indigo-500/60 bg-indigo-500/10 border-l-4 !border-l-indigo-400 shadow-lg shadow-indigo-500/10'
                          : 'border-gray-700/30 hover:border-gray-600/50']">

            <div class="flex items-start justify-between gap-2">
              <div class="flex-1 min-w-0">
                <div class="text-sm font-medium text-gray-200 truncate">
                  {{ draft.title || 'Başlıksız' }}
                </div>
                <div class="flex items-center gap-2 mt-1">
                  <span class="text-xs text-gray-500">
                    {{ draft.source_type === 'youtube_summary' ? '📺' : '✍️' }}
                  </span>
                  <span class="text-xs text-gray-600">
                    {{ formatDate(draft.updated_at) }}
                  </span>
                </div>
              </div>

              <div class="flex items-center gap-1.5">
                <StatusBadge :status="draft.status" size="xs" />
                <button @click.stop="handleDelete(draft.id)"
                        class="text-gray-600 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100 text-xs"
                        title="Taslağı sil">
                  🗑
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ═══ SAĞ PANEL: Editör ═══ -->
      <div class="lg:col-span-9">
        <div v-if="!publishStore.activeDraft" class="card p-12 text-center">
          <div class="text-4xl mb-4">📝</div>
          <h3 class="text-lg font-medium text-gray-300 mb-2">Düzenlemek için bir taslak seçin</h3>
          <p class="text-sm text-gray-500">
            Soldaki listeden bir taslak seçin, yukarıdaki "Yeni Taslak Oluştur" butonunu kullanın
            veya görev kuyruğundan "Yayına Gönder" ile yeni taslak oluşturun.
          </p>
        </div>

        <div v-else class="card overflow-hidden">

          <!-- Editör Üst Bar -->
          <div class="flex items-center justify-between px-5 py-3 border-b border-gray-700/40">
            <div class="flex items-center gap-2">
              <span class="text-sm font-medium text-gray-300">
                {{ publishStore.activeDraft.status === 'PUBLISHED' ? '✅ Yayınlandı' : '📝 Taslak' }}
              </span>
              <span class="text-xs text-gray-600 font-mono">#{{ publishStore.activeDraft.id }}</span>
            </div>
            <div class="flex items-center gap-2">
              <div v-if="hasChanges" class="w-2 h-2 bg-amber-400 rounded-full" title="Kaydedilmemiş değişiklik" />
            </div>
          </div>

          <!-- Yayınlanmış içerik için bilgi -->
          <div v-if="publishStore.activeDraft.status === 'PUBLISHED'"
               class="px-5 py-3 bg-emerald-500/5 border-b border-emerald-500/10">
            <div class="flex items-center gap-2">
              <span class="text-xs text-emerald-400">✅ Bu içerik yayınlandı</span>
              <a v-if="publishStore.activeDraft.xf_thread_url"
                 :href="publishStore.activeDraft.xf_thread_url"
                 target="_blank"
                 class="text-xs text-indigo-400 hover:underline">
                Konuyu Görüntüle →
              </a>
            </div>
          </div>

          <div class="p-5 space-y-4">

            <!-- Başlık -->
            <div>
              <input v-model="editTitle" @input="markChanged"
                     type="text" class="input-field text-lg font-semibold"
                     placeholder="Makale Başlığı"
                     :disabled="publishStore.activeDraft.status === 'PUBLISHED'" />
            </div>

            <!-- Kategori + Forum + Etiketler + Yazım Stili -->
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              <div>
                <label class="field-label">Kategori</label>
                <input v-model="editCategory" @input="markChanged"
                       type="text" class="input-field text-sm"
                       placeholder="Felsefe"
                       :disabled="publishStore.activeDraft.status === 'PUBLISHED'" />
              </div>
              <div>
                <label class="field-label">Hedef Forum</label>
                <select v-model="editNodeId" @change="markChanged"
                        class="select-field text-sm"
                        :disabled="publishStore.activeDraft.status === 'PUBLISHED'">
                  <option value="">— Forum seçin —</option>
                  <option v-for="n in xfNodes" :key="n.node_id" :value="n.node_id">
                    [{{ n.node_id }}] {{ n.title || n.node_name }}
                  </option>
                </select>
              </div>
              <div>
                <label class="field-label">Etiketler</label>
                <input v-model="editTags" @input="markChanged"
                       type="text" class="input-field text-sm"
                       placeholder="felsefe, stoacılık"
                       :disabled="publishStore.activeDraft.status === 'PUBLISHED'" />
              </div>
              <div>
                <label class="field-label">Yazım Stili</label>
                <select v-model="editTone" @change="markChanged"
                        class="select-field text-sm"
                        :disabled="publishStore.activeDraft.status === 'PUBLISHED'">
                  <option v-for="t in TONE_OPTIONS" :key="t.value" :value="t.value">
                    {{ t.emoji }} {{ t.label }}
                  </option>
                </select>
              </div>
            </div>

            <!-- TipTap Editör -->
            <RichEditor
              v-model="editContent"
              :disabled="publishStore.activeDraft.status === 'PUBLISHED'"
              @change="markChanged"
              @ai-action="handleAiAction"
            />

            <!-- Eylem butonları -->
            <div v-if="publishStore.activeDraft.status !== 'PUBLISHED'"
                 class="flex items-center gap-3 pt-2">
              <button @click="handleSave"
                      :disabled="publishStore.isSaving || !hasChanges"
                      class="btn-secondary py-2.5 px-5">
                <span v-if="publishStore.isSaving" class="animate-spin">⚙</span>
                <span v-else>💾</span>
                {{ publishStore.isSaving ? 'Kaydediliyor...' : 'Kaydet' }}
              </button>

              <button @click="handlePublish"
                      :disabled="publishStore.isPublishing || aiProcessing"
                      class="btn-primary py-2.5 px-5">
                <span v-if="publishStore.isPublishing" class="animate-spin">⚙</span>
                <span v-else>🚀</span>
                {{ publishStore.isPublishing ? 'Yayınlanıyor...' : 'XenForo\'ya Yayınla' }}
              </button>

              <div class="flex-1" />

              <button @click="handleDelete(publishStore.activeDraft.id)"
                      class="text-xs text-gray-500 hover:text-red-400 transition-colors py-2 px-3">
                🗑 Taslağı Sil
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ── Taslak Kartı ──────────────────────────────── */
.draft-card {
  padding: 0.75rem 1rem;
  border-radius: 0.5rem;
  border: 1px solid;
  cursor: pointer;
  transition: all 0.15s ease;
}
.draft-card:hover {
  background: rgba(99, 102, 241, 0.04);
}

/* ── Butonlar ──────────────────────────────────── */
.btn-secondary {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  border-radius: 0.5rem;
  font-weight: 500;
  font-size: 0.875rem;
  background: rgba(55, 65, 81, 0.5);
  color: #d1d5db;
  border: 1px solid rgba(75, 85, 99, 0.4);
  transition: all 0.15s;
  cursor: pointer;
}
.btn-secondary:hover:not(:disabled) {
  background: rgba(75, 85, 99, 0.5);
  color: #f3f4f6;
}
.btn-secondary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ── Bildirimler ───────────────────────────────── */
.slide-fade-enter-active, .slide-fade-leave-active { transition: all 0.25s ease; }
.slide-fade-enter-from { opacity: 0; transform: translateY(-8px); }
.slide-fade-leave-to   { opacity: 0; transform: translateY(-4px); }

/* ── Scrollbar ─────────────────────────────────── */
.max-h-\[65vh\]::-webkit-scrollbar { width: 4px; }
.max-h-\[65vh\]::-webkit-scrollbar-track { background: transparent; }
.max-h-\[65vh\]::-webkit-scrollbar-thumb { background: #374151; border-radius: 4px; }
</style>

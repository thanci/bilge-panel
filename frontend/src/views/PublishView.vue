<script setup>
/**
 * PublishView.vue — Yayın Kuyruğu & BB-Code Editör.
 * Sol panel: taslak listesi    |   Sağ panel: editör + önizleme
 * Editör, hem BB-Code ham metin hem de görsel önizleme destekler.
 */

import { ref, computed, onMounted, watch } from 'vue'
import { usePublishStore } from '@/stores/publish'
import { useRoute } from 'vue-router'
import StatusBadge from '@/components/ui/StatusBadge.vue'
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
const editorMode    = ref('edit')  // 'edit' | 'preview'
const hasChanges    = ref(false)

// BB-Code araç çubuğu
const editorRef = ref(null)

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

// ── BB-Code Araç Çubuğu ──────────────────────────────
function insertBBCode(tag, attr = '') {
  const textarea = editorRef.value
  if (!textarea) return
  const start = textarea.selectionStart
  const end   = textarea.selectionEnd
  const sel   = editContent.value.substring(start, end)
  const openTag  = attr ? `[${tag}=${attr}]` : `[${tag}]`
  const closeTag = `[/${tag}]`
  const replacement = `${openTag}${sel || 'metin'}${closeTag}`
  editContent.value = editContent.value.substring(0, start) + replacement + editContent.value.substring(end)
  hasChanges.value = true
  // Odağı geri ver
  setTimeout(() => {
    textarea.focus()
    const newPos = start + openTag.length + (sel ? sel.length : 5)
    textarea.setSelectionRange(sel ? start + openTag.length : start + openTag.length, newPos)
  }, 10)
}

const bbToolbar = [
  { label: 'B',   tag: 'b',      title: 'Kalın' },
  { label: 'I',   tag: 'i',      title: 'İtalik' },
  { label: 'U',   tag: 'u',      title: 'Altı çizili' },
  { label: 'H1',  tag: 'heading', attr: '1', title: 'Başlık 1' },
  { label: 'H2',  tag: 'heading', attr: '2', title: 'Başlık 2' },
  { label: '•',   tag: 'list',   title: 'Liste' },
  { label: '❝',  tag: 'quote',   title: 'Alıntı' },
  { label: '</>',  tag: 'code',   title: 'Kod' },
  { label: '🔗', tag: 'url',    title: 'Link' },
  { label: '🖼', tag: 'img',    title: 'Resim' },
]

// ── BB-Code → HTML Önizleme ──────────────────────────
const previewHtml = computed(() => {
  let html = editContent.value || ''
  // Basit BB-Code → HTML dönüşümü
  html = html.replace(/\n/g, '<br>')
  html = html.replace(/\[b\](.*?)\[\/b\]/gs,    '<strong>$1</strong>')
  html = html.replace(/\[i\](.*?)\[\/i\]/gs,    '<em>$1</em>')
  html = html.replace(/\[u\](.*?)\[\/u\]/gs,    '<u>$1</u>')
  html = html.replace(/\[heading=1\](.*?)\[\/heading\]/gs, '<h2 style="font-size:1.5rem;font-weight:700;margin:0.75rem 0;">$1</h2>')
  html = html.replace(/\[heading=2\](.*?)\[\/heading\]/gs, '<h3 style="font-size:1.25rem;font-weight:600;margin:0.5rem 0;">$1</h3>')
  html = html.replace(/\[quote\](.*?)\[\/quote\]/gs, '<blockquote style="border-left:3px solid #6366f1;padding:0.5rem 1rem;margin:0.5rem 0;color:#9ca3af;">$1</blockquote>')
  html = html.replace(/\[code\](.*?)\[\/code\]/gs, '<code style="background:#1e293b;padding:2px 6px;border-radius:4px;font-size:0.85em;">$1</code>')
  html = html.replace(/\[url=(.*?)\](.*?)\[\/url\]/gs, '<a href="$1" style="color:#818cf8;text-decoration:underline;">$2</a>')
  html = html.replace(/\[url\](.*?)\[\/url\]/gs, '<a href="$1" style="color:#818cf8;text-decoration:underline;">$1</a>')
  html = html.replace(/\[img\](.*?)\[\/img\]/gs, '<img src="$1" style="max-width:100%;border-radius:8px;margin:0.5rem 0;" />')
  html = html.replace(/\[list\](.*?)\[\/list\]/gs, (_, inner) => {
    const items = inner.split(/\[\*\]/).filter(x => x.trim()).map(x => `<li>${x.trim()}</li>`).join('')
    return `<ul style="padding-left:1.5rem;margin:0.5rem 0;">${items}</ul>`
  })
  return html
})

// ── Kaydet ───────────────────────────────────────────
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
  })
  hasChanges.value = false
}

// ── Yayınla ──────────────────────────────────────────
async function handlePublish() {
  if (!publishStore.activeDraft) return
  if (!editNodeId.value) {
    publishStore.error = 'Lütfen bir hedef forum seçin.'
    return
  }

  // Önce kaydet, sonra yayınla
  if (hasChanges.value) await handleSave()

  if (confirm('Bu içeriği XenForo\'ya yayınlamak istediğinize emin misiniz?')) {
    await publishStore.publishDraft(publishStore.activeDraft.id)
  }
}

// ── Sil ──────────────────────────────────────────────
async function handleDelete(draftId) {
  if (!confirm('Bu taslağı kalıcı olarak silmek istediğinize emin misiniz?')) return
  await publishStore.deleteDraft(draftId)
}

// ── Kelime sayısı ────────────────────────────────────
const wordCount = computed(() => {
  const text = editContent.value.replace(/\[.*?\]/g, '').trim()
  return text ? text.split(/\s+/).length : 0
})
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
      <div v-if="publishStore.error"
           class="bg-red-500/10 border border-red-500/30 text-red-400
                  text-sm px-4 py-2.5 rounded-lg">
        {{ publishStore.error }}
      </div>
    </Transition>

    <!-- Ana içerik: Sol + Sağ panel -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-4" style="min-height: 70vh;">

      <!-- ═══ SOL PANEL: Taslak Listesi ═══ -->
      <div class="lg:col-span-3 space-y-3">

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
            Görev kuyruğundan "Yayına Gönder" ile taslak oluşturun.
          </p>
        </div>

        <!-- Taslak listesi -->
        <div v-else class="space-y-2 max-h-[65vh] overflow-y-auto pr-1">
          <div v-for="draft in publishStore.filteredDrafts" :key="draft.id"
               @click="publishStore.selectDraft(draft.id)"
               :class="['draft-card group',
                        publishStore.activeDraft?.id === draft.id
                          ? 'border-indigo-500/40 bg-indigo-500/5'
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
            Soldaki listeden bir taslak seçin veya görev kuyruğundan "Yayına Gönder" butonuyla yeni taslak oluşturun.
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
              <span class="text-xs text-gray-500 tabular-nums">
                {{ wordCount }} kelime
              </span>
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

            <!-- Kategori + Forum Seçimi + Etiketler -->
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
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
            </div>

            <!-- Editör Mod Seçimi -->
            <div class="flex items-center justify-between">
              <div class="flex gap-1 bg-gray-900 rounded-lg p-0.5">
                <button @click="editorMode = 'edit'"
                        :class="['px-3 py-1 rounded-md text-xs font-medium transition-all',
                                 editorMode === 'edit'
                                   ? 'bg-gray-800 text-gray-100'
                                   : 'text-gray-400 hover:text-gray-200']">
                  ✏️ BB-Code
                </button>
                <button @click="editorMode = 'preview'"
                        :class="['px-3 py-1 rounded-md text-xs font-medium transition-all',
                                 editorMode === 'preview'
                                   ? 'bg-gray-800 text-gray-100'
                                   : 'text-gray-400 hover:text-gray-200']">
                  👁 Önizleme
                </button>
              </div>

              <!-- BB-Code araç çubuğu (sadece edit modunda) -->
              <div v-if="editorMode === 'edit' && publishStore.activeDraft.status !== 'PUBLISHED'"
                   class="flex gap-1">
                <button v-for="tool in bbToolbar" :key="tool.tag + (tool.attr || '')"
                        @click="insertBBCode(tool.tag, tool.attr)"
                        :title="tool.title"
                        class="w-7 h-7 flex items-center justify-center rounded
                               text-xs font-mono text-gray-400 bg-gray-800/60
                               hover:bg-gray-700 hover:text-gray-200 transition-all">
                  {{ tool.label }}
                </button>
              </div>
            </div>

            <!-- BB-Code Editör -->
            <div v-if="editorMode === 'edit'">
              <textarea ref="editorRef"
                        v-model="editContent" @input="markChanged"
                        class="editor-textarea"
                        placeholder="BB-Code formatında içerik yazın..."
                        :disabled="publishStore.activeDraft.status === 'PUBLISHED'"
                        rows="18" />
            </div>

            <!-- Önizleme -->
            <div v-if="editorMode === 'preview'">
              <div class="preview-area" v-html="previewHtml" />
            </div>

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
                      :disabled="publishStore.isPublishing"
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

/* ── Editör ────────────────────────────────────── */
.editor-textarea {
  width: 100%;
  min-height: 400px;
  padding: 1rem;
  font-family: 'Fira Code', 'Cascadia Code', 'JetBrains Mono', monospace;
  font-size: 0.875rem;
  line-height: 1.7;
  color: #e5e7eb;
  background: #0a0f1e;
  border: 1px solid rgba(55, 65, 81, 0.4);
  border-radius: 0.5rem;
  resize: vertical;
  outline: none;
  transition: border-color 0.2s;
}
.editor-textarea:focus {
  border-color: rgba(99, 102, 241, 0.5);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.08);
}
.editor-textarea:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* ── Önizleme ──────────────────────────────────── */
.preview-area {
  min-height: 400px;
  padding: 1.25rem;
  font-size: 0.9375rem;
  line-height: 1.8;
  color: #d1d5db;
  background: #0a0f1e;
  border: 1px solid rgba(55, 65, 81, 0.4);
  border-radius: 0.5rem;
  overflow-y: auto;
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

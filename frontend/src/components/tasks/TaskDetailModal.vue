<script setup>
/**
 * TaskDetailModal.vue — Görev detay ve log modalı.
 * Görev satırına tıklayınca açılır:
 *   - Durum, süre, maliyet, model bilgisi
 *   - Payload (giriş parametreleri)
 *   - Sonuç / Hata detayları
 *   - Eylem butonları: Sil, Tekrar Dene, Yayına Gönder
 */

import { ref, computed, watch } from 'vue'
import { useTaskStore } from '@/stores/tasks'
import { publishService } from '@/services'
import { useRouter } from 'vue-router'
import StatusBadge from '@/components/ui/StatusBadge.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  taskId:  { type: String,  default: '' },
})
const emit = defineEmits(['close', 'refresh'])

const taskStore = useTaskStore()
const router    = useRouter()
const detail    = ref(null)
const loading   = ref(false)
const activeTab = ref('result')
const actionLoading = ref('')

// Görev detayını yükle
watch(() => props.taskId, async (id) => {
  if (!id) return
  loading.value = true
  detail.value = await taskStore.getTaskDetail(id)
  loading.value = false
  // Uygun sekmeyi otomatik aç
  if (detail.value?.error_msg) activeTab.value = 'error'
  else if (detail.value?.result) activeTab.value = 'result'
  else activeTab.value = 'payload'
})

const TASK_TYPE_LABELS = {
  youtube_summary: '📺 YouTube → Makale',
  ai_article:      '✍️ Otonom Makale',
  maintenance:     '🔧 Bakım',
}

const tabs = computed(() => {
  if (!detail.value) return []
  const t = []
  t.push({ id: 'result',  label: '📄 Sonuç',     show: true })
  t.push({ id: 'payload', label: '📥 Giriş',      show: !!detail.value.payload })
  t.push({ id: 'error',   label: '⚠️ Hata',       show: !!detail.value.error_msg })
  return t.filter(x => x.show)
})

function formatDuration(d) {
  if (!d?.started_at || !d?.finished_at) return '—'
  const s = Math.round((new Date(d.finished_at) - new Date(d.started_at)) / 1000)
  return s < 60 ? `${s}s` : `${Math.floor(s/60)}d ${s%60}s`
}

function formatDate(str) {
  if (!str) return '—'
  return new Intl.DateTimeFormat('tr-TR', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  }).format(new Date(str))
}

// ── Eylemler ──────────────────────────────────────────
async function handleDelete() {
  if (!confirm('Bu görev kaydını kalıcı olarak silmek istediğinize emin misiniz?')) return
  actionLoading.value = 'delete'
  await taskStore.deleteTask(props.taskId)
  actionLoading.value = ''
  emit('close')
  emit('refresh')
}

async function handleRetry() {
  actionLoading.value = 'retry'
  await taskStore.retryTask(props.taskId)
  actionLoading.value = ''
  emit('close')
  emit('refresh')
}

async function handleSendToPublish() {
  actionLoading.value = 'publish'
  try {
    const result = await publishService.createDraft({ task_id: props.taskId })
    if (result?.id) {
      emit('close')
      router.push({ name: 'publish', query: { draft: result.id } })
    }
  } catch (err) {
    taskStore.error = err.response?.data?.message || 'Yayın kuyruğuna gönderilemedi.'
  }
  actionLoading.value = ''
}

function close() {
  detail.value = null
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="visible" class="modal-overlay" @click.self="close">
        <div class="modal-container">

          <!-- Header -->
          <div class="modal-header">
            <div class="flex items-center gap-3">
              <span class="text-2xl">{{ TASK_TYPE_LABELS[detail?.task_type]?.slice(0,2) || '📋' }}</span>
              <div>
                <h3 class="text-base font-semibold text-gray-100">
                  {{ TASK_TYPE_LABELS[detail?.task_type] || detail?.task_type || 'Görev Detayı' }}
                </h3>
                <code class="text-xs text-gray-500 font-mono">{{ detail?.task_id || '—' }}</code>
              </div>
            </div>
            <button @click="close" class="text-gray-500 hover:text-gray-300 text-xl transition-colors">✕</button>
          </div>

          <!-- Loading -->
          <div v-if="loading" class="p-8 text-center">
            <div class="animate-spin text-3xl mb-3">⚙</div>
            <p class="text-sm text-gray-500">Yükleniyor...</p>
          </div>

          <!-- Content -->
          <div v-else-if="detail" class="modal-body">

            <!-- Bilgi kartları -->
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
              <div class="info-card">
                <span class="info-label">Durum</span>
                <StatusBadge :status="detail.status" />
              </div>
              <div class="info-card">
                <span class="info-label">Model</span>
                <span class="text-sm text-gray-200 font-mono">{{ detail.model_used || '—' }}</span>
              </div>
              <div class="info-card">
                <span class="info-label">Maliyet</span>
                <span class="text-sm text-amber-400 tabular-nums font-mono">
                  {{ detail.cost_usd ? `$${detail.cost_usd.toFixed(4)}` : '—' }}
                </span>
              </div>
              <div class="info-card">
                <span class="info-label">Süre</span>
                <span class="text-sm text-gray-300 tabular-nums">{{ formatDuration(detail) }}</span>
              </div>
            </div>

            <!-- Tarih satırı -->
            <div class="flex gap-4 text-xs text-gray-500 mb-4 px-1">
              <span>Oluşturuldu: {{ formatDate(detail.created_at) }}</span>
              <span v-if="detail.started_at">Başladı: {{ formatDate(detail.started_at) }}</span>
              <span v-if="detail.finished_at">Bitti: {{ formatDate(detail.finished_at) }}</span>
            </div>

            <!-- Sekmeler -->
            <div class="flex gap-1 bg-gray-900 rounded-lg p-1 mb-4">
              <button v-for="tab in tabs" :key="tab.id"
                      @click="activeTab = tab.id"
                      :class="['flex-1 py-1.5 rounded-md text-xs font-medium transition-all',
                               activeTab === tab.id
                                 ? 'bg-gray-800 text-gray-100 shadow'
                                 : 'text-gray-400 hover:text-gray-200']">
                {{ tab.label }}
              </button>
            </div>

            <!-- Sonuç sekmesi -->
            <div v-if="activeTab === 'result'" class="tab-content">
              <div v-if="!detail.result" class="text-center py-6 text-gray-500 text-sm">
                Henüz sonuç yok (görev devam ediyor veya başarısız oldu).
              </div>
              <div v-else>
                <!-- İçerik özeti -->
                <div v-if="detail.result.content" class="mb-4">
                  <div class="flex items-center justify-between mb-2">
                    <span class="text-xs text-gray-400 font-medium uppercase tracking-wider">Üretilen İçerik</span>
                    <span v-if="detail.result.word_count" class="text-xs text-gray-500">
                      ~{{ detail.result.word_count }} kelime
                    </span>
                  </div>
                  <div class="content-preview">{{ detail.result.content }}</div>
                </div>
                <!-- Meta bilgiler -->
                <div v-if="detail.result.meta" class="space-y-2">
                  <div v-if="detail.result.meta.description" class="text-xs">
                    <span class="text-gray-500">Açıklama:</span>
                    <span class="text-gray-300 ml-1">{{ detail.result.meta.description }}</span>
                  </div>
                  <div v-if="detail.result.meta.keywords?.length" class="flex flex-wrap gap-1">
                    <span v-for="kw in detail.result.meta.keywords" :key="kw"
                          class="text-xs bg-indigo-500/10 text-indigo-400 px-2 py-0.5 rounded-full">
                      {{ kw }}
                    </span>
                  </div>
                </div>
                <!-- XenForo sonucu -->
                <div v-if="detail.result.xf" class="mt-3 p-3 bg-gray-900/50 rounded-lg">
                  <div class="text-xs text-gray-400 mb-1">XenForo Yayın:</div>
                  <div v-if="detail.result.xf.status === 'success'" class="text-xs text-emerald-400">
                    ✅ Yayınlandı —
                    <a :href="detail.result.xf.url" target="_blank" class="text-indigo-400 hover:underline">
                      Konuyu Görüntüle →
                    </a>
                  </div>
                  <div v-else-if="detail.result.xf.status === 'skipped'" class="text-xs text-gray-500">
                    Atlandı: {{ detail.result.xf.reason }}
                  </div>
                  <div v-else class="text-xs text-amber-400">
                    {{ detail.result.xf.status }}: {{ detail.result.xf.message || detail.result.xf.reason }}
                  </div>
                </div>
              </div>
            </div>

            <!-- Payload sekmesi -->
            <div v-if="activeTab === 'payload'" class="tab-content">
              <pre class="json-block">{{ JSON.stringify(detail.payload, null, 2) }}</pre>
            </div>

            <!-- Hata sekmesi -->
            <div v-if="activeTab === 'error'" class="tab-content">
              <div class="error-block">
                <div class="text-xs font-medium text-red-400 mb-2">Hata Detayı</div>
                <pre class="text-sm text-red-300 whitespace-pre-wrap break-words">{{ detail.error_msg }}</pre>
              </div>
            </div>

            <!-- Eylem butonları -->
            <div class="flex flex-wrap gap-2 mt-4 pt-4 border-t border-gray-700/40">
              <!-- Yayına Gönder (sadece SUCCESS) -->
              <button v-if="detail.status === 'SUCCESS' && detail.result?.content"
                      @click="handleSendToPublish"
                      :disabled="actionLoading === 'publish'"
                      class="btn-primary text-xs py-2 px-4">
                <span v-if="actionLoading === 'publish'" class="animate-spin">⚙</span>
                <span v-else>📝</span>
                Yayına Gönder
              </button>

              <!-- Tekrar Dene (FAILED/REVOKED) -->
              <button v-if="detail.status === 'FAILED' || detail.status === 'REVOKED'"
                      @click="handleRetry"
                      :disabled="!!actionLoading"
                      class="btn-secondary text-xs py-2 px-4">
                <span v-if="actionLoading === 'retry'" class="animate-spin">⚙</span>
                <span v-else>🔄</span>
                Tekrar Dene
              </button>

              <!-- İptal Et (QUEUED/RUNNING) -->
              <button v-if="detail.status === 'QUEUED' || detail.status === 'RUNNING'"
                      @click="handleDelete"
                      :disabled="!!actionLoading"
                      class="btn-danger text-xs py-2 px-4">
                ✕ İptal Et
              </button>

              <div class="flex-1" />

              <!-- Sil -->
              <button @click="handleDelete"
                      :disabled="!!actionLoading"
                      class="text-xs text-gray-500 hover:text-red-400 transition-colors py-2 px-3">
                <span v-if="actionLoading === 'delete'" class="animate-spin">⚙</span>
                <span v-else>🗑</span>
                Sil
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* ── Overlay ───────────────────────────────────── */
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  padding: 1rem;
}

/* ── Container ─────────────────────────────────── */
.modal-container {
  width: 100%;
  max-width: 720px;
  max-height: 85vh;
  overflow-y: auto;
  background: #0f1729;
  border: 1px solid rgba(99, 102, 241, 0.15);
  border-radius: 1rem;
  box-shadow: 0 25px 80px rgba(0, 0, 0, 0.6), 0 0 40px rgba(99, 102, 241, 0.08);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid rgba(55, 65, 81, 0.4);
}

.modal-body {
  padding: 1.25rem 1.5rem;
}

/* ── Bilgi Kartları ────────────────────────────── */
.info-card {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  padding: 0.75rem;
  border-radius: 0.5rem;
  background: rgba(15, 23, 42, 0.5);
  border: 1px solid rgba(55, 65, 81, 0.3);
}

.info-label {
  font-size: 0.625rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #6b7280;
}

/* ── Tab Content ───────────────────────────────── */
.tab-content {
  min-height: 120px;
  max-height: 340px;
  overflow-y: auto;
}

.content-preview {
  font-size: 0.8125rem;
  line-height: 1.6;
  color: #d1d5db;
  background: rgba(15, 23, 42, 0.5);
  border: 1px solid rgba(55, 65, 81, 0.3);
  border-radius: 0.5rem;
  padding: 1rem;
  max-height: 240px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.json-block {
  font-size: 0.75rem;
  font-family: 'Fira Code', 'Cascadia Code', monospace;
  color: #93c5fd;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(55, 65, 81, 0.3);
  border-radius: 0.5rem;
  padding: 1rem;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.error-block {
  background: rgba(220, 38, 38, 0.08);
  border: 1px solid rgba(220, 38, 38, 0.2);
  border-radius: 0.5rem;
  padding: 1rem;
}

/* ── Butonlar ──────────────────────────────────── */
.btn-secondary {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.5rem 1rem;
  border-radius: 0.5rem;
  font-weight: 500;
  background: rgba(55, 65, 81, 0.5);
  color: #d1d5db;
  border: 1px solid rgba(75, 85, 99, 0.4);
  transition: all 0.15s;
}
.btn-secondary:hover:not(:disabled) {
  background: rgba(75, 85, 99, 0.5);
  color: #f3f4f6;
}

/* ── Animasyonlar ──────────────────────────────── */
.modal-enter-active { transition: all 0.25s ease; }
.modal-leave-active { transition: all 0.2s ease; }
.modal-enter-from  { opacity: 0; }
.modal-leave-to    { opacity: 0; }
.modal-enter-from .modal-container { transform: scale(0.95) translateY(12px); }
.modal-leave-to .modal-container   { transform: scale(0.98) translateY(4px); }

/* Scrollbar */
.tab-content::-webkit-scrollbar,
.content-preview::-webkit-scrollbar,
.modal-container::-webkit-scrollbar { width: 5px; }
.tab-content::-webkit-scrollbar-track,
.content-preview::-webkit-scrollbar-track,
.modal-container::-webkit-scrollbar-track { background: transparent; }
.tab-content::-webkit-scrollbar-thumb,
.content-preview::-webkit-scrollbar-thumb,
.modal-container::-webkit-scrollbar-thumb { background: #374151; border-radius: 4px; }
</style>

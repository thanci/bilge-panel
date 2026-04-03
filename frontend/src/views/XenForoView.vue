<script setup>
/**
 * XenForoView.vue — XenForo Forum Yönetimi
 * Üç sekme: Forum Ağacı | Hiyerarşi Oluştur | Manuel Konu
 */

import { ref, onMounted } from 'vue'
import api from '@/services/api'
import StatusBadge from '@/components/ui/StatusBadge.vue'

const activeTab   = ref('tree')
const nodes       = ref([])
const isLoading   = ref(false)
const xfOnline    = ref(null)   // null=bilinmiyor, true=bağlı, false=hata
const error       = ref(null)
const success     = ref(null)

// ── Sağlık Kontrolü + Node listesi ──────────────────────
onMounted(async () => {
  await checkHealth()
  if (xfOnline.value) await fetchNodes()
})

async function checkHealth() {
  try {
    const { data } = await api.get('/xenforo/health')
    xfOnline.value = data.success
  } catch {
    xfOnline.value = false
  }
}

async function fetchNodes() {
  isLoading.value = true
  try {
    const { data } = await api.get('/xenforo/nodes')
    nodes.value = data.data
    error.value = null
  } catch (e) {
    error.value = e.response?.data?.message || 'Forum ağacı alınamadı.'
  } finally {
    isLoading.value = false
  }
}

// ── Forum oluşturma ──────────────────────────────────────
const forumForm = ref({ name: '', parent_node_id: '', description: '', display_order: 10, type: 'Forum' })
const isCreating = ref(false)

async function createNode() {
  isCreating.value = true
  error.value = null
  try {
    const endpoint = forumForm.value.type === 'Category' ? '/xenforo/nodes/category' : '/xenforo/nodes/forum'
    const { data } = await api.post(endpoint, {
      name:           forumForm.value.name,
      parent_node_id: forumForm.value.parent_node_id || 0,
      description:    forumForm.value.description,
      display_order:  forumForm.value.display_order,
    })
    success.value = `"${data.data?.node_name || forumForm.value.name}" oluşturuldu (ID: ${data.data?.node_id})`
    forumForm.value = { name: '', parent_node_id: '', description: '', display_order: 10, type: 'Forum' }
    await fetchNodes()
    setTimeout(() => success.value = null, 5000)
  } catch (e) {
    error.value = e.response?.data?.message || 'Node oluşturulamadı.'
  } finally {
    isCreating.value = false
  }
}

// ── Hiyerarşi JSON oluşturucu ────────────────────────────
const hierarchyJson = ref(`[
  {
    "name": "Felsefe ve Düşünce",
    "type": "Category",
    "parent_id": 0,
    "description": "Felsefi incelemeler ve düşünce denemeleri",
    "order": 10,
    "children": [
      {"name": "Antik Felsefe", "type": "Forum", "description": "Sokrates, Platon, Aristoteles", "order": 10},
      {"name": "Etik ve Ahlak",  "type": "Forum", "description": "Ahlak felsefesi", "order": 20}
    ]
  }
]`)
const isHierarchyLoading = ref(false)
const hierarchyResult    = ref(null)
const jsonError          = ref(null)

async function createHierarchy() {
  jsonError.value = null
  let parsed
  try {
    parsed = JSON.parse(hierarchyJson.value)
  } catch (e) {
    jsonError.value = `JSON hatası: ${e.message}`
    return
  }
  isHierarchyLoading.value = true
  try {
    const { data } = await api.post('/xenforo/nodes/hierarchy', { nodes: parsed })
    hierarchyResult.value = data.data
    await fetchNodes()
  } catch (e) {
    jsonError.value = e.response?.data?.message || 'Hiyerarşi oluşturulamadı.'
  } finally {
    isHierarchyLoading.value = false
  }
}

// ── Manuel konu ──────────────────────────────────────────
const threadForm = ref({ node_id: '', title: '', message: '', tags: '' })
const isPosting  = ref(false)
const postedThread = ref(null)

async function postThread() {
  isPosting.value = true
  error.value = null
  postedThread.value = null
  try {
    const { data } = await api.post('/xenforo/threads', {
      node_id: threadForm.value.node_id,
      title:   threadForm.value.title,
      message: threadForm.value.message,
      tags:    threadForm.value.tags.split(',').map(t => t.trim()).filter(Boolean),
    })
    postedThread.value = data.data
    threadForm.value = { node_id: '', title: '', message: '', tags: '' }
  } catch (e) {
    error.value = e.response?.data?.message || 'Konu oluşturulamadı.'
  } finally {
    isPosting.value = false
  }
}
</script>

<template>
  <div class="max-w-screen-xl mx-auto space-y-5 animate-fade-in">

    <!-- Başlık + Bağlantı durumu -->
    <div class="flex items-center justify-between flex-wrap gap-3">
      <div>
        <h1 class="text-xl font-bold text-gray-100">XenForo Yönetimi</h1>
        <p class="text-sm text-gray-500">Forum hiyerarşisi ve içerik yayını</p>
      </div>
      <div class="flex items-center gap-2">
        <span v-if="xfOnline === null"
              class="text-xs text-gray-500 animate-pulse">Bağlantı kontrol ediliyor…</span>
        <span v-else-if="xfOnline"
              class="flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-500/10
                     border border-emerald-500/20 px-3 py-1 rounded-full">
          <span class="live-dot" /> XenForo Bağlı
        </span>
        <span v-else
              class="flex items-center gap-1.5 text-xs text-red-400 bg-red-500/10
                     border border-red-500/20 px-3 py-1 rounded-full">
          ✕ XenForo Bağlantı Hatası
        </span>
        <button @click="checkHealth"
                class="btn-ghost text-xs px-3 py-1.5">
          ↺ Test Et
        </button>
      </div>
    </div>

    <!-- XF bağlı değilse uyarı -->
    <div v-if="xfOnline === false"
         class="card p-5 bg-red-500/5 border-red-500/20 text-sm text-red-300 space-y-1">
      <p class="font-medium">XenForo API'sine bağlanılamıyor.</p>
      <p class="text-red-400/70 text-xs">
        .env dosyasında <code class="font-mono bg-gray-900 px-1 rounded">XENFORO_BASE_URL</code>
        ve <code class="font-mono bg-gray-900 px-1 rounded">XENFORO_API_KEY</code> değerlerini kontrol edin.
        <br/>XenForo Admin → Araçlar → API anahtarları → Yeni (Tür: Super user)
      </p>
    </div>

    <!-- Sekme başlıkları -->
    <div class="flex gap-1 bg-gray-900 rounded-xl p-1 w-fit">
      <button v-for="tab in [
        { id: 'tree',      label: '🌲 Forum Ağacı' },
        { id: 'create',    label: '➕ Node Oluştur' },
        { id: 'hierarchy', label: '📐 Hiyerarşi JSON' },
        { id: 'thread',    label: '✍️ Manuel Konu' },
      ]" :key="tab.id"
      @click="activeTab = tab.id"
      :class="['px-4 py-2 rounded-lg text-sm font-medium transition-all duration-150',
               activeTab === tab.id
                 ? 'bg-gray-800 text-gray-100 shadow-md'
                 : 'text-gray-400 hover:text-gray-200']">
        {{ tab.label }}
      </button>
    </div>

    <!-- Bildirimler -->
    <Transition name="slide-fade">
      <div v-if="success" class="bg-emerald-500/10 border border-emerald-500/30 text-emerald-400
                                  text-sm px-4 py-2.5 rounded-lg">✓ {{ success }}</div>
    </Transition>
    <Transition name="slide-fade">
      <div v-if="error" class="bg-red-500/10 border border-red-500/30 text-red-400
                                text-sm px-4 py-2.5 rounded-lg">{{ error }}</div>
    </Transition>

    <!-- ── SEKME: Forum Ağacı ──────────────────────────── -->
    <div v-if="activeTab === 'tree'" class="card p-6 space-y-4 animate-fade-in">
      <div class="flex items-center justify-between">
        <h2 class="text-sm font-semibold text-gray-300">Forum Hiyerarşisi</h2>
        <button @click="fetchNodes" class="btn-ghost text-xs px-3 py-1.5" :disabled="isLoading">
          {{ isLoading ? '…' : '↺ Yenile' }}
        </button>
      </div>

      <!-- Yükleniyor -->
      <div v-if="isLoading" class="space-y-2">
        <div v-for="i in 6" :key="i" class="h-10 bg-gray-700/40 animate-pulse rounded-lg" />
      </div>

      <!-- Boş -->
      <div v-else-if="!nodes.length" class="text-center py-8 text-gray-600 text-sm">
        <div class="text-3xl mb-2">🌲</div>
        Forum ağacı boş — Node oluştur sekmesinden başlayın.
      </div>

      <!-- Ağaç -->
      <div v-else class="space-y-1.5">
        <NodeTreeItem v-for="node in nodes" :key="node.node_id" :node="node" :depth="0" />
      </div>
    </div>

    <!-- ── SEKME: Node Oluştur ─────────────────────────── -->
    <div v-if="activeTab === 'create'" class="card p-6 space-y-4 animate-fade-in">
      <h2 class="text-sm font-semibold text-gray-300">Yeni Forum Düğümü Oluştur</h2>

      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="field-label">Tür</label>
          <div class="flex gap-2">
            <button v-for="t in ['Forum', 'Category']" :key="t"
                    @click="forumForm.type = t"
                    :class="['flex-1 py-2 rounded-lg border text-sm transition-all',
                             forumForm.type === t
                               ? 'border-indigo-500/50 bg-indigo-500/10 text-indigo-300'
                               : 'border-gray-700 bg-gray-900/50 text-gray-400']">
              {{ t === 'Forum' ? '💬 Forum' : '📁 Kategori' }}
            </button>
          </div>
        </div>
        <div>
          <label class="field-label">Üst Node ID</label>
          <select v-model="forumForm.parent_node_id" class="select-field">
            <option value="0">0 — Kök seviye</option>
            <option v-for="n in nodes" :key="n.node_id" :value="n.node_id">
              {{ n.node_id }} — {{ n.title || n.node_name }}
              <template v-if="n.children?.length"> ({{ n.children.length }} alt)</template>
            </option>
          </select>
        </div>
      </div>

      <div>
        <label class="field-label">Ad <span class="text-red-500">*</span></label>
        <input v-model="forumForm.name" type="text" class="input-field"
               placeholder="Antik Felsefe" />
      </div>

      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="field-label">Açıklama</label>
          <input v-model="forumForm.description" type="text" class="input-field"
                 placeholder="Kısa açıklama…" />
        </div>
        <div>
          <label class="field-label">Sıra</label>
          <input v-model.number="forumForm.display_order" type="number" class="input-field"
                 min="0" max="9999" />
        </div>
      </div>

      <button @click="createNode" class="btn-primary w-full justify-center py-3"
              :disabled="!forumForm.name || isCreating || !xfOnline">
        <span v-if="isCreating" class="animate-spin-slow">⚙</span>
        {{ isCreating ? 'Oluşturuluyor…' : `${forumForm.type} Oluştur` }}
      </button>
    </div>

    <!-- ── SEKME: Hiyerarşi JSON ───────────────────────── -->
    <div v-if="activeTab === 'hierarchy'" class="card p-6 space-y-4 animate-fade-in">
      <div>
        <h2 class="text-sm font-semibold text-gray-300">Toplu Hiyerarşi Oluştur</h2>
        <p class="text-xs text-gray-500 mt-1">
          JSON formatında ebeveyn-çocuk ilişkisiyle tüm forum yapısını tek seferinde oluşturun.
        </p>
      </div>

      <div>
        <label class="field-label">Hiyerarşi Tanımı (JSON)</label>
        <textarea v-model="hierarchyJson" class="textarea-field font-mono text-xs"
                  rows="16" spellcheck="false" />
        <div v-if="jsonError" class="mt-1.5 text-xs text-red-400">{{ jsonError }}</div>
      </div>

      <button @click="createHierarchy" class="btn-primary w-full justify-center py-3"
              :disabled="isHierarchyLoading || !xfOnline">
        <span v-if="isHierarchyLoading" class="animate-spin-slow">⚙</span>
        {{ isHierarchyLoading ? 'Oluşturuluyor…' : '🚀 Hiyerarşiyi Oluştur' }}
      </button>

      <!-- Sonuçlar -->
      <div v-if="hierarchyResult" class="bg-emerald-500/10 border border-emerald-500/20
                                         p-4 rounded-lg text-sm text-emerald-400 space-y-2">
        <p class="font-medium">✓ {{ hierarchyResult.count }} node başarıyla oluşturuldu</p>
        <div class="space-y-1 text-xs text-emerald-300/70">
          <div v-for="n in hierarchyResult.created" :key="n.node_id">
            ID: {{ n.node_id }} — {{ n.node_name || n.title }}
          </div>
        </div>
      </div>
    </div>

    <!-- ── SEKME: Manuel Konu ──────────────────────────── -->
    <div v-if="activeTab === 'thread'" class="card p-6 space-y-4 animate-fade-in">
      <h2 class="text-sm font-semibold text-gray-300">Manuel Forum Konusu Oluştur</h2>

      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="field-label">Forum (Node ID) <span class="text-red-500">*</span></label>
          <select v-model="threadForm.node_id" class="select-field">
            <option value="">— Forum seçin —</option>
            <option v-for="n in nodes.filter(n => !n.children?.length || n.node_type_id === 'Forum')"
                    :key="n.node_id" :value="n.node_id">
              {{ n.node_id }} — {{ n.title || n.node_name }}
            </option>
          </select>
        </div>
        <div>
          <label class="field-label">Etiketler</label>
          <input v-model="threadForm.tags" type="text" class="input-field"
                 placeholder="felsefe, bilgelik, metafizik" />
        </div>
      </div>

      <div>
        <label class="field-label">Başlık (boş bırakılırsa içerikten türetilir)</label>
        <input v-model="threadForm.title" type="text" class="input-field"
               placeholder="Konu başlığı…" />
      </div>

      <div>
        <label class="field-label">İçerik (BB-Code) <span class="text-red-500">*</span></label>
        <textarea v-model="threadForm.message" class="textarea-field font-mono text-xs"
                  rows="12" placeholder="[B]Giriş[/B]&#10;&#10;Makale içeriği buraya…" />
      </div>

      <button @click="postThread" class="btn-primary w-full justify-center py-3"
              :disabled="!threadForm.node_id || !threadForm.message || isPosting || !xfOnline">
        <span v-if="isPosting" class="animate-spin-slow">⚙</span>
        {{ isPosting ? 'Yayınlanıyor…' : '📢 Foruma Yayınla' }}
      </button>

      <!-- Başarılı sonuç -->
      <div v-if="postedThread"
           class="bg-emerald-500/10 border border-emerald-500/20 p-4 rounded-lg text-sm space-y-2">
        <p class="text-emerald-400 font-medium">✓ Konu başarıyla oluşturuldu!</p>
        <div class="text-xs text-gray-400 space-y-1">
          <div>Konu ID: <span class="text-gray-200 font-mono">{{ postedThread.thread_id }}</span></div>
          <div>Başlık: <span class="text-gray-200">{{ postedThread.title }}</span></div>
          <a v-if="postedThread.url" :href="postedThread.url" target="_blank"
             class="text-indigo-400 hover:underline flex items-center gap-1">
            🔗 Konuya Git →
          </a>
        </div>
      </div>
    </div>
  </div>
</template>

<!-- Özyinelemeli ağaç düğümü bileşen (tek dosyada tanımlanır) -->
<script>
const NodeTreeItem = {
  name: 'NodeTreeItem',
  props: {
    node:  { type: Object, required: true },
    depth: { type: Number, default: 0 },
  },
  template: `
    <div>
      <div :class="[
        'flex items-center gap-2 px-3 py-2 rounded-lg text-sm hover:bg-gray-700/20 transition-colors',
        depth === 0 ? 'font-medium text-gray-200' : 'text-gray-400',
      ]"
      :style="{ marginLeft: depth * 20 + 'px' }">
        <span class="text-base shrink-0">
          {{ node.node_type_id === 'Category' ? '📁' : '💬' }}
        </span>
        <span class="flex-1 truncate">{{ node.title || node.node_name }}</span>
        <span class="text-xs font-mono text-gray-600 shrink-0">ID {{ node.node_id }}</span>
        <span v-if="node.node_type_id"
              :class="['text-xs px-1.5 py-0.5 rounded shrink-0',
                       node.node_type_id === 'Category'
                         ? 'bg-amber-500/10 text-amber-500'
                         : 'bg-indigo-500/10 text-indigo-400']">
          {{ node.node_type_id }}
        </span>
      </div>
      <NodeTreeItem v-for="child in (node.children || [])"
                    :key="child.node_id" :node="child" :depth="depth + 1" />
    </div>
  `,
}
export default { components: { NodeTreeItem } }
</script>

<style scoped>
.slide-fade-enter-active, .slide-fade-leave-active { transition: all 0.25s ease; }
.slide-fade-enter-from { opacity: 0; transform: translateY(-8px); }
.slide-fade-leave-to   { opacity: 0; }
</style>

<script setup>
/**
 * TaskQueue.vue — Celery görev listesi (5 saniyelik polling).
 * Görev türü, durumu, maliyet ve süreleri tablolar biçimde gösterir.
 * Satıra tıklayınca TaskDetailModal açılır.
 */

import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useTaskStore } from '@/stores/tasks'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import TaskDetailModal from '@/components/tasks/TaskDetailModal.vue'

const showModal   = ref(false)
const selectedId  = ref('')

function openDetail(taskId) {
  selectedId.value = taskId
  showModal.value  = true
}
function closeDetail() {
  showModal.value  = false
  selectedId.value = ''
}

const taskStore = useTaskStore()

onMounted(() => {
  taskStore.fetchTasks()
  taskStore.startPolling(5000)
})
onUnmounted(() => taskStore.stopPolling())

const TASK_TYPE_LABELS = {
  youtube_summary: '📺 YouTube',
  ai_article:      '✍️ Makale',
  maintenance:     '🔧 Bakım',
}

const FILTER_OPTIONS = [
  { value: 'all',            label: 'Tümü' },
  { value: 'youtube_summary', label: '📺 YouTube' },
  { value: 'ai_article',     label: '✍️ Makale' },
]

function formatDuration(task) {
  if (!task.started_at || !task.finished_at) return '—'
  const s = Math.round(
    (new Date(task.finished_at) - new Date(task.started_at)) / 1000,
  )
  return s < 60 ? `${s}s` : `${Math.floor(s/60)}d ${s%60}s`
}

function formatCost(cost) {
  if (cost == null) return '—'
  return `$${(+cost).toFixed(4)}`
}

function formatDate(dateStr) {
  if (!dateStr) return '—'
  return new Intl.DateTimeFormat('tr-TR', {
    month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  }).format(new Date(dateStr))
}

function shortId(id) {
  return id ? id.slice(0, 8) + '…' : '—'
}

async function revoke(taskId) {
  if (!confirm('Bu görevi iptal etmek istediğinize emin misiniz?')) return
  await taskStore.revokeTask(taskId)
}
</script>

<template>
  <div class="space-y-4 animate-fade-in">

    <!-- Başlık + filtreler + sayaçlar -->
    <div class="flex flex-wrap items-center justify-between gap-4">
      <div class="flex items-center gap-3">
        <h2 class="text-lg font-semibold text-gray-100">Görev Kuyruğu</h2>
        <!-- Canlı gösterge -->
        <div class="flex items-center gap-1.5 text-xs text-gray-500">
          <span class="live-dot" />
          <span>5s</span>
        </div>
        <!-- Aktif görev sayıları -->
        <div v-if="taskStore.runningCount > 0"
             class="flex items-center gap-1 bg-indigo-500/10 border border-indigo-500/20
                    text-indigo-400 text-xs px-2 py-0.5 rounded-full">
          <span class="animate-spin-slow">⚙</span>
          {{ taskStore.runningCount }} işleniyor
        </div>
        <div v-if="taskStore.queuedCount > 0"
             class="bg-slate-600/30 text-slate-400 text-xs px-2 py-0.5 rounded-full">
          {{ taskStore.queuedCount }} bekliyor
        </div>
      </div>

      <!-- Durum/Tür filtresi -->
      <div class="flex gap-1.5">
        <button
          v-for="opt in FILTER_OPTIONS" :key="opt.value"
          @click="taskStore.setFilter(opt.value)"
          :class="[
            'px-3 py-1 rounded-lg text-xs font-medium transition-all duration-150',
            taskStore.filter === opt.value
              ? 'bg-indigo-600 text-white'
              : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-200',
          ]">
          {{ opt.label }}
        </button>
      </div>
    </div>

    <!-- Hata mesajı -->
    <div v-if="taskStore.error"
         class="bg-red-500/10 border border-red-500/30 text-red-400 text-sm px-4 py-2.5 rounded-lg">
      {{ taskStore.error }}
    </div>

    <!-- Tablo -->
    <div class="card overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-gray-700/50">
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider w-28">
                ID
              </th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Tür
              </th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                Durum
              </th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider hidden md:table-cell">
                Model
              </th>
              <th class="px-4 py-3 text-right text-xs font-medium text-gray-400 uppercase tracking-wider hidden lg:table-cell">
                Maliyet
              </th>
              <th class="px-4 py-3 text-right text-xs font-medium text-gray-400 uppercase tracking-wider hidden lg:table-cell">
                Süre
              </th>
              <th class="px-4 py-3 text-right text-xs font-medium text-gray-400 uppercase tracking-wider hidden md:table-cell">
                Tarih
              </th>
              <th class="px-4 py-3 w-16" />
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-700/30">
            <!-- Boş durum -->
            <tr v-if="!taskStore.filteredTasks.length">
              <td colspan="8" class="px-4 py-12 text-center text-gray-500">
                <div class="text-4xl mb-3">📭</div>
                <div class="text-sm">Henüz görev yok</div>
              </td>
            </tr>

            <!-- Görev satırları -->
            <tr
              v-for="task in taskStore.filteredTasks"
              :key="task.task_id"
              @click="openDetail(task.task_id)"
              :class="[
                'transition-colors duration-150 cursor-pointer',
                task.status === 'RUNNING'
                  ? 'bg-indigo-500/5 hover:bg-indigo-500/10'
                  : 'hover:bg-gray-700/20',
              ]">

              <!-- ID -->
              <td class="px-4 py-3">
                <code class="text-xs font-mono text-gray-400 bg-gray-900/60 px-1.5 py-0.5 rounded">
                  {{ shortId(task.task_id) }}
                </code>
              </td>

              <!-- Tür -->
              <td class="px-4 py-3">
                <span class="text-gray-200 text-xs">
                  {{ TASK_TYPE_LABELS[task.task_type] || task.task_type }}
                </span>
              </td>

              <!-- Durum -->
              <td class="px-4 py-3">
                <StatusBadge :status="task.status" />
              </td>

              <!-- Model -->
              <td class="px-4 py-3 hidden md:table-cell">
                <span v-if="task.model_used"
                      class="text-xs text-gray-400 font-mono bg-gray-900/40 px-1.5 py-0.5 rounded">
                  {{ task.model_used.split('-').slice(0, 2).join('-') }}
                </span>
                <span v-else class="text-gray-600">—</span>
              </td>

              <!-- Maliyet -->
              <td class="px-4 py-3 text-right hidden lg:table-cell">
                <span :class="[
                  'text-xs tabular-nums font-mono',
                  task.cost_usd ? 'text-amber-400' : 'text-gray-600'
                ]">
                  {{ formatCost(task.cost_usd) }}
                </span>
              </td>

              <!-- Süre -->
              <td class="px-4 py-3 text-right hidden lg:table-cell">
                <span class="text-xs text-gray-400 tabular-nums">
                  {{ formatDuration(task) }}
                </span>
              </td>

              <!-- Tarih -->
              <td class="px-4 py-3 text-right hidden md:table-cell">
                <span class="text-xs text-gray-500 tabular-nums">
                  {{ formatDate(task.created_at) }}
                </span>
              </td>

              <!-- Eylemler -->
              <td class="px-4 py-3 text-right">
                <button
                  v-if="task.status === 'QUEUED' || task.status === 'RUNNING'"
                  @click="revoke(task.task_id)"
                  class="btn-danger text-xs"
                  title="Görevi iptal et">
                  ✕
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Detay Modal -->
    <TaskDetailModal
      :visible="showModal"
      :task-id="selectedId"
      @close="closeDetail"
      @refresh="taskStore.fetchTasks()"
    />
  </div>
</template>

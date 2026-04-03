<script setup>
/**
 * DashboardView.vue — Ana dashboard.
 * BudgetGauge, istatistik kartları ve son 5 görev özetiyle açılır.
 */

import { onMounted, onUnmounted } from 'vue'
import { useBudgetStore } from '@/stores/budget'
import { useTaskStore }   from '@/stores/tasks'
import BudgetGauge        from '@/components/budget/BudgetGauge.vue'
import StatusBadge        from '@/components/ui/StatusBadge.vue'

const budgetStore = useBudgetStore()
const taskStore   = useTaskStore()

onMounted(async () => {
  await Promise.all([budgetStore.fetchAll(), taskStore.fetchTasks()])
  budgetStore.startPolling(30_000)
  taskStore.startPolling(10_000)   // Dashboard'da 10 sn (tasks view: 5 sn)
})

onUnmounted(() => {
  budgetStore.stopPolling()
  taskStore.stopPolling()
})

const STAT_CARDS = [
  {
    key:   'today_spent',
    label: 'Bugün Harcanan',
    icon:  '💸',
    format: (v) => `$${(+v).toFixed(4)}`,
    color:  'text-amber-400',
  },
  {
    key:   'today_calls',
    label: 'API Çağrısı',
    icon:  '⚡',
    format: (v) => `${v}`,
    color:  'text-indigo-400',
  },
  {
    key:   'blocked_calls_today',
    label: 'Engellenen',
    icon:  '🔒',
    format: (v) => `${v}`,
    color:  'text-red-400',
  },
  {
    key:   'total_spent_all_time',
    label: 'Toplam Harcama',
    icon:  '📊',
    format: (v) => `$${(+v).toFixed(2)}`,
    color:  'text-purple-400',
  },
]

function taskTypeEmoji(type) {
  return type === 'youtube_summary' ? '📺' : type === 'ai_article' ? '✍️' : '🔧'
}
</script>

<template>
  <div class="space-y-6 animate-fade-in max-w-screen-xl mx-auto">

    <!-- ── Başlık ─────────────────────────────────────────── -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-xl font-bold text-gray-100">İyi günler ✦</h1>
        <p class="text-sm text-gray-500 mt-0.5">Sistem bütçesi ve görev kuyruğu anlık takip</p>
      </div>
      <div class="flex items-center gap-2 text-xs text-gray-500">
        <span class="live-dot" />
        Canlı güncelleniyor
      </div>
    </div>

    <!-- ── İstatistik Kartları ────────────────────────────── -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div v-for="card in STAT_CARDS" :key="card.key"
           class="card p-5 shine">
        <div class="flex items-start justify-between">
          <div>
            <p class="text-xs text-gray-500 uppercase tracking-wide">{{ card.label }}</p>
            <p :class="['text-2xl font-bold mt-1.5 tabular-nums', card.color]">
              <span v-if="budgetStore.isLoading"
                    class="inline-block w-16 h-7 bg-gray-700 animate-pulse rounded" />
              <span v-else>
                {{ budgetStore.stats ? card.format(budgetStore.stats[card.key] ?? 0) : '—' }}
              </span>
            </p>
          </div>
          <span class="text-2xl opacity-60">{{ card.icon }}</span>
        </div>
      </div>
    </div>

    <!-- ── Ana İçerik: Gauge + Circuit Breaker + Son Görevler ── -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">

      <!-- BudgetGauge kartı -->
      <div class="card p-6 flex flex-col items-center gap-4 lg:col-span-1">
        <div class="flex items-center justify-between w-full">
          <h2 class="text-sm font-semibold text-gray-300">Günlük Bütçe</h2>
          <span class="text-xs text-gray-600">{{ new Date().toLocaleDateString('tr-TR') }}</span>
        </div>

        <BudgetGauge
          :spent="budgetStore.spentUsd"
          :limit="budgetStore.limitUsd"
          :state="budgetStore.breakerState"
          :loading="budgetStore.isLoading"
        />

        <!-- Circuit Breaker kontrolleri -->
        <div class="w-full pt-2 border-t border-gray-700/40 space-y-2">
          <div class="flex items-center justify-between text-xs">
            <span class="text-gray-500">Circuit Breaker</span>
            <StatusBadge :status="budgetStore.breakerState" size="xs" />
          </div>

          <button v-if="budgetStore.isBlocked"
                  @click="budgetStore.resetBreaker()"
                  class="btn-danger w-full justify-center text-xs py-2">
            ⚡ Kilidi Manuel Aç
          </button>

          <!-- Bütçe doluluk çubukları -->
          <div class="space-y-2 pt-1">
            <div v-for="segment in [
              { label: 'Harcanan', pct: budgetStore.usagePct, color: budgetStore.usagePct >= 80 ? 'bg-red-500' : budgetStore.usagePct >= 60 ? 'bg-amber-500' : 'bg-emerald-500' },
              { label: 'Kalan', pct: 100 - budgetStore.usagePct, color: 'bg-gray-600' },
            ]" :key="segment.label"
            class="flex items-center gap-2 text-xs text-gray-500">
              <span class="w-14">{{ segment.label }}</span>
              <div class="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                <div :class="['h-full rounded-full transition-all duration-700', segment.color]"
                     :style="{ width: `${segment.pct}%` }" />
              </div>
              <span class="w-8 text-right tabular-nums">{{ segment.pct.toFixed(0) }}%</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Son görevler -->
      <div class="card p-6 lg:col-span-2 space-y-4">
        <div class="flex items-center justify-between">
          <h2 class="text-sm font-semibold text-gray-300">Son Görevler</h2>
          <RouterLink :to="{ name: 'tasks' }"
                      class="text-xs text-indigo-400 hover:text-indigo-300 transition-colors">
            Tümünü gör →
          </RouterLink>
        </div>

        <!-- Yükleniyor -->
        <div v-if="taskStore.isLoading" class="space-y-2">
          <div v-for="i in 5" :key="i"
               class="h-12 bg-gray-700/40 animate-pulse rounded-lg" />
        </div>

        <!-- Boş -->
        <div v-else-if="!taskStore.tasks.length"
             class="text-center py-10 text-gray-600 text-sm">
          <div class="text-3xl mb-2">📭</div>
          Henüz görev yok.
          <RouterLink :to="{ name: 'tasks' }" class="text-indigo-400 hover:underline ml-1">
            Yeni görev başlat →
          </RouterLink>
        </div>

        <!-- Liste -->
        <div v-else class="space-y-2">
          <div v-for="task in taskStore.tasks.slice(0, 6)" :key="task.task_id"
               class="flex items-center gap-3 px-4 py-3 bg-gray-900/50 rounded-lg
                      hover:bg-gray-700/30 transition-colors">
            <span class="text-lg">{{ taskTypeEmoji(task.task_type) }}</span>
            <div class="flex-1 min-w-0">
              <div class="text-xs font-medium text-gray-200 truncate">
                {{ task.task_type === 'youtube_summary' ? 'YouTube Özeti' : 'AI Makale' }}
                <span class="text-gray-600 font-mono ml-1">{{ task.task_id.slice(0,6) }}</span>
              </div>
              <div v-if="task.cost_usd" class="text-[10px] text-amber-400/70">
                ${{ (+task.cost_usd).toFixed(4) }}
              </div>
            </div>
            <StatusBadge :status="task.status" size="xs" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

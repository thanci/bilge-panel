<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useBudgetStore } from '@/stores/budget'
import BudgetGauge        from '@/components/budget/BudgetGauge.vue'
import StatusBadge        from '@/components/ui/StatusBadge.vue'

const budgetStore = useBudgetStore()

onMounted(() => {
  budgetStore.fetchAll(7)
  budgetStore.startPolling(30_000)
})
onUnmounted(() => budgetStore.stopPolling())

function barWidth(spent, limit) {
  if (!limit) return '0%'
  return `${Math.min((spent / limit) * 100, 100)}%`
}

function modelShortName(m) {
  const map = {
    'gemini-2.5-flash': 'Gemini Flash',
    'claude-haiku-3-5': 'Claude Haiku',
    'gpt-4o-mini':      'GPT-4o-mini',
  }
  return map[m] || m
}
</script>

<template>
  <div class="max-w-screen-xl mx-auto space-y-6 animate-fade-in">

    <h1 class="text-xl font-bold text-gray-100">Bütçe Yönetimi</h1>

    <!-- Üst satır: Gauge + Stats -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">

      <!-- Gauge -->
      <div class="card p-6 flex flex-col items-center gap-4">
        <h2 class="text-sm font-semibold text-gray-300 w-full">Bugünkü Kullanım</h2>
        <BudgetGauge
          :spent="budgetStore.spentUsd"
          :limit="budgetStore.limitUsd"
          :state="budgetStore.breakerState"
          :loading="budgetStore.isLoading"
        />

        <button v-if="budgetStore.isBlocked"
                @click="budgetStore.resetBreaker()"
                class="btn-danger w-full justify-center">
          ⚡ Circuit Breaker'ı Sıfırla
        </button>
      </div>

      <!-- Özet istatistikler -->
      <div class="card p-6 space-y-4 lg:col-span-2">
        <h2 class="text-sm font-semibold text-gray-300">Durum Özeti</h2>

        <div class="grid grid-cols-2 gap-4">
          <div v-for="item in [
            { label: 'Harcanan (bugün)',   val: `$${budgetStore.stats?.today_spent?.toFixed(4) ?? '—'}`, color: 'text-amber-400' },
            { label: 'Kalan',             val: `$${budgetStore.stats ? (budgetStore.limitUsd - budgetStore.spentUsd).toFixed(4) : '—'}`, color: 'text-emerald-400' },
            { label: 'API Çağrısı',       val: budgetStore.stats?.today_calls ?? '—', color: 'text-indigo-400' },
            { label: 'Engellenen Çağrı',  val: budgetStore.stats?.blocked_calls_today ?? '—', color: 'text-red-400' },
          ]" :key="item.label"
          class="bg-gray-900/50 rounded-xl p-4">
            <p class="text-xs text-gray-500">{{ item.label }}</p>
            <p :class="['text-xl font-bold mt-1 tabular-nums', item.color]">{{ item.val }}</p>
          </div>
        </div>

        <!-- 7 günlük geçmiş çubuklar -->
        <div>
          <h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">Son 7 Gün</h3>
          <div v-if="budgetStore.history.length" class="flex items-end gap-1.5 h-20">
            <div v-for="day in budgetStore.history" :key="day.date"
                 class="flex-1 flex flex-col items-center gap-1 group">
              <div class="w-full bg-gray-700 rounded-t relative overflow-visible"
                   :style="{ height: '100%', position: 'relative' }">
                <div
                  class="w-full rounded-t transition-all duration-700 absolute bottom-0"
                  :class="day.usage_pct >= 80 ? 'bg-red-500' : day.usage_pct >= 60 ? 'bg-amber-500' : 'bg-emerald-500'"
                  :style="{ height: `${Math.max(day.usage_pct, 2)}%` }"
                />
              </div>
              <span class="text-[9px] text-gray-600 group-hover:text-gray-400 transition-colors">
                {{ day.date.slice(5) }}
              </span>
            </div>
          </div>
          <div v-else class="text-xs text-gray-600 text-center py-6">Geçmiş veri yok</div>
        </div>
      </div>
    </div>

    <!-- Model bazlı harcama -->
    <div class="card p-6 space-y-4">
      <h2 class="text-sm font-semibold text-gray-300">Model Bazlı Harcama (Son 7 Gün)</h2>
      <div v-if="budgetStore.breakdown?.by_model?.length" class="space-y-3">
        <div v-for="item in budgetStore.breakdown.by_model" :key="item.model"
             class="flex items-center gap-4">
          <div class="w-32 text-xs text-gray-400 truncate">{{ modelShortName(item.model) }}</div>
          <div class="flex-1 h-2.5 bg-gray-700 rounded-full overflow-hidden">
            <div class="h-full bg-indigo-500 rounded-full transition-all duration-700"
                 :style="{ width: barWidth(item.total_usd, budgetStore.breakdown.by_model[0]?.total_usd) }" />
          </div>
          <div class="text-xs text-amber-400 tabular-nums font-mono w-16 text-right">
            ${{ item.total_usd.toFixed(4) }}
          </div>
          <div class="text-xs text-gray-600 w-12 text-right">{{ item.call_count }} çağrı</div>
        </div>
      </div>
      <div v-else class="text-xs text-gray-600 text-center py-4">Henüz kayıt yok</div>
    </div>

    <!-- Son maliyet logları -->
    <div class="card p-6 space-y-3">
      <h2 class="text-sm font-semibold text-gray-300">Son Maliyet Kayıtları</h2>
      <div class="overflow-x-auto">
        <table class="w-full text-xs">
          <thead>
            <tr class="border-b border-gray-700/50">
              <th class="py-2 px-3 text-left text-gray-500 font-medium">Task ID</th>
              <th class="py-2 px-3 text-left text-gray-500 font-medium">Model</th>
              <th class="py-2 px-3 text-right text-gray-500 font-medium">Giriş</th>
              <th class="py-2 px-3 text-right text-gray-500 font-medium">Çıkış</th>
              <th class="py-2 px-3 text-right text-gray-500 font-medium">Maliyet</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-700/20">
            <tr v-for="log in budgetStore.logs" :key="log.id"
                class="hover:bg-gray-700/10">
              <td class="py-2 px-3 font-mono text-gray-500">{{ log.task_id?.slice(0,8) }}…</td>
              <td class="py-2 px-3 text-gray-400">{{ modelShortName(log.model) }}</td>
              <td class="py-2 px-3 text-right tabular-nums text-gray-400">{{ log.prompt_tokens?.toLocaleString('tr-TR') }}</td>
              <td class="py-2 px-3 text-right tabular-nums text-gray-400">{{ log.output_tokens?.toLocaleString('tr-TR') }}</td>
              <td class="py-2 px-3 text-right tabular-nums text-amber-400 font-mono">${{ (+log.cost_usd).toFixed(6) }}</td>
            </tr>
          </tbody>
        </table>
        <div v-if="!budgetStore.logs.length" class="text-center py-6 text-gray-600 text-xs">
          Kayıt yok
        </div>
      </div>
    </div>
  </div>
</template>

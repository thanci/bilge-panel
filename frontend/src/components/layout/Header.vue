<script setup>
import { useRoute }       from 'vue-router'
import { computed }       from 'vue'
import { useBudgetStore } from '@/stores/budget'
import { useTaskStore }   from '@/stores/tasks'
import StatusBadge        from '@/components/ui/StatusBadge.vue'

defineEmits(['toggle-sidebar'])

const route       = useRoute()
const budgetStore = useBudgetStore()
const taskStore   = useTaskStore()

const pageTitle = computed(() => route.meta?.title ?? 'Dashboard')
</script>

<template>
  <header class="flex items-center justify-between px-6 py-4
                 bg-gray-900/60 border-b border-gray-700/40 backdrop-blur-sm
                 shrink-0 z-10">

    <!-- Sol: hamburger + başlık -->
    <div class="flex items-center gap-4">
      <button @click="$emit('toggle-sidebar')"
              class="text-gray-400 hover:text-gray-200 transition-colors p-1.5 rounded-lg hover:bg-gray-800">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16"/>
        </svg>
      </button>
      <h1 class="text-base font-semibold text-gray-100">{{ pageTitle }}</h1>
    </div>

    <!-- Sağ: anlık bütçe şeridi + görev sayacı -->
    <div class="flex items-center gap-4">

      <!-- Aktif görev sayacı -->
      <div v-if="taskStore.runningCount > 0"
           class="hidden sm:flex items-center gap-2 text-xs text-indigo-400
                  bg-indigo-500/10 px-3 py-1.5 rounded-lg animate-pulse-slow">
        <span class="animate-spin-slow text-sm">⚙</span>
        {{ taskStore.runningCount }} görev çalışıyor
      </div>

      <!-- Mini bütçe bar -->
      <div class="hidden md:flex items-center gap-3">
        <div class="text-right">
          <div class="text-xs text-gray-400">Günlük Bütçe</div>
          <div :class="[
            'text-sm font-semibold tabular-nums',
            budgetStore.usagePct >= 80 ? 'text-red-400' :
            budgetStore.usagePct >= 60 ? 'text-amber-400' : 'text-emerald-400'
          ]">
            ${{ budgetStore.spentUsd.toFixed(2) }}
            <span class="text-gray-500 font-normal">/ ${{ budgetStore.limitUsd.toFixed(2) }}</span>
          </div>
        </div>

        <!-- İnce progress bar -->
        <div class="w-24 h-2 bg-gray-700 rounded-full overflow-hidden">
          <div
            class="h-full rounded-full transition-all duration-700"
            :class="budgetStore.usagePct >= 80 ? 'bg-red-500' :
                    budgetStore.usagePct >= 60 ? 'bg-amber-500' : 'bg-emerald-500'"
            :style="{ width: `${Math.min(budgetStore.usagePct, 100)}%` }"
          />
        </div>

        <StatusBadge :status="budgetStore.breakerState" size="xs" />
      </div>
    </div>
  </header>
</template>

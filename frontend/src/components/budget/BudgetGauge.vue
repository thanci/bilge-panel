<script setup>
/**
 * BudgetGauge.vue — Yarı daire SVG bütçe göstergesi.
 * Anlık harcamanın günlük limite oranını renk kodlu biçimde gösterir.
 *
 * Props:
 *   spent   — Harcanan miktar (USD)
 *   limit   — Günlük limit (USD)
 *   state   — Circuit Breaker durumu ('CLOSED' | 'OPEN' | 'HALF_OPEN')
 *   loading — Yükleniyor durumu
 */

import { computed, ref, watch, onMounted } from 'vue'

const props = defineProps({
  spent:   { type: Number, default: 0 },
  limit:   { type: Number, default: 2 },
  state:   { type: String, default: 'CLOSED' },
  loading: { type: Boolean, default: false },
})

// Animasyon için gerçek percentage'ı gecikmeli uygula
const animatedPct = ref(0)

const percentage = computed(() =>
  props.limit > 0 ? Math.min((props.spent / props.limit) * 100, 100) : 0,
)

watch(percentage, (val) => {
  // 100ms gecikme ile animasyon başlat
  setTimeout(() => { animatedPct.value = val }, 100)
}, { immediate: true })

// ─── SVG Yarım daire arc hesabı ────────────────────────
// Daire: merkez (100, 110), radius 80, 180° → 0° (soldan sağa)
const SVG_R      = 80
const SVG_CX     = 100
const SVG_CY     = 110
const START_X    = SVG_CX - SVG_R   // 20
const START_Y    = SVG_CY           // 110

const arcPath = computed(() => {
  const p = Math.min(animatedPct.value / 100, 0.9999)
  if (p <= 0.001) return ''
  const angle  = Math.PI * p               // 0 → π
  const x      = SVG_CX - SVG_R * Math.cos(angle)
  const y      = SVG_CY - SVG_R * Math.sin(angle)
  const large  = p > 0.5 ? 1 : 0
  return `M ${START_X} ${START_Y} A ${SVG_R} ${SVG_R} 0 ${large} 1 ${x.toFixed(2)} ${y.toFixed(2)}`
})

// Renk: yeşil → sarı → turuncu → kırmızı
const strokeColor = computed(() => {
  if (props.state === 'OPEN') return '#ef4444'
  const p = percentage.value
  if (p >= 95) return '#ef4444'   // red
  if (p >= 80) return '#f97316'   // orange
  if (p >= 60) return '#f59e0b'   // amber
  return '#10b981'                // emerald
})

const textColor = computed(() => {
  if (props.state === 'OPEN') return 'text-red-400'
  const p = percentage.value
  if (p >= 95) return 'text-red-400'
  if (p >= 80) return 'text-orange-400'
  if (p >= 60) return 'text-amber-400'
  return 'text-emerald-400'
})

const stateLabel = computed(() => {
  const map = { CLOSED: 'Normal', OPEN: 'KİLİTLİ', HALF_OPEN: 'Yenileniyor' }
  return map[props.state] || props.state
})
</script>

<template>
  <div class="flex flex-col items-center">
    <!-- SVG Gauge -->
    <div class="relative w-64 select-none">
      <svg viewBox="0 0 200 130" class="w-full overflow-visible">
        <!-- Izgaralar / Tick işaretleri -->
        <g opacity="0.2">
          <line v-for="i in 11" :key="i"
            :x1="100 + 95 * Math.cos(Math.PI - ((i-1)/10) * Math.PI)"
            :y1="110 - 95 * Math.sin(Math.PI - ((i-1)/10) * Math.PI)"
            :x2="100 + 85 * Math.cos(Math.PI - ((i-1)/10) * Math.PI)"
            :y2="110 - 85 * Math.sin(Math.PI - ((i-1)/10) * Math.PI)"
            stroke="#64748b" stroke-width="1.5" stroke-linecap="round"/>
        </g>

        <!-- Arkaplan yayı -->
        <path
          :d="`M ${START_X} ${START_Y} A ${SVG_R} ${SVG_R} 0 1 1 ${SVG_CX + SVG_R} ${SVG_CY}`"
          fill="none"
          stroke="#1f2937"
          stroke-width="14"
          stroke-linecap="round"
        />

        <!-- Dolu yay (animasyonlu) -->
        <path
          v-if="!loading"
          :d="arcPath"
          fill="none"
          :stroke="strokeColor"
          stroke-width="14"
          stroke-linecap="round"
          class="transition-all duration-1000 ease-out"
          :style="{ filter: state === 'OPEN' ? 'drop-shadow(0 0 6px #ef4444)' : `drop-shadow(0 0 4px ${strokeColor}88)` }"
        />

        <!-- Yükleniyor skeleton -->
        <path
          v-if="loading"
          :d="`M ${START_X} ${START_Y} A ${SVG_R} ${SVG_R} 0 1 1 ${SVG_CX + SVG_R} ${SVG_CY}`"
          fill="none"
          stroke="#374151"
          stroke-width="14"
          stroke-linecap="round"
          class="animate-pulse"
        />

        <!-- Merkez metin: harcanan USD -->
        <text x="100" y="95" text-anchor="middle"
              fill="white" font-size="24" font-weight="700" font-family="Inter, sans-serif">
          ${{ spent.toFixed(2) }}
        </text>
        <text x="100" y="112" text-anchor="middle"
              fill="#9ca3af" font-size="11" font-family="Inter, sans-serif">
          / ${{ limit.toFixed(2) }} limit
        </text>

        <!-- Etiketler: %0 ve %100 -->
        <text x="16" y="128" fill="#6b7280" font-size="9" font-family="Inter, sans-serif">%0</text>
        <text x="180" y="128" fill="#6b7280" font-size="9" text-anchor="end" font-family="Inter, sans-serif">%100</text>
      </svg>
    </div>

    <!-- Yüzde ve durum -->
    <div class="mt-1 text-center space-y-1">
      <div :class="['text-3xl font-bold tabular-nums transition-colors duration-500', textColor]">
        {{ percentage.toFixed(1) }}%
      </div>
      <div class="flex items-center justify-center gap-2 text-xs text-gray-500">
        <span :class="[
          'px-2 py-0.5 rounded-full text-xs font-medium',
          state === 'OPEN'
            ? 'bg-red-500/20 text-red-400 animate-pulse'
            : state === 'HALF_OPEN'
              ? 'bg-amber-500/20 text-amber-400'
              : 'bg-emerald-500/20 text-emerald-400'
        ]">
          ● {{ stateLabel }}
        </span>
        <span>•</span>
        <span class="text-gray-400 tabular-nums">${{ (limit - spent).toFixed(4) }} kaldı</span>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * StatusBadge.vue — Görev durumu renk rozeti.
 * TaskQueue ve diğer listeler tarafından kullanılır.
 */

const props = defineProps({
  status: { type: String, required: true },
  size:   { type: String, default: 'sm' },   // 'xs' | 'sm' | 'md'
})

const CONFIG = {
  QUEUED:     { label: 'Bekliyor',    cls: 'bg-slate-600/50 text-slate-300',                  dot: 'bg-slate-400',   pulse: false },
  RUNNING:    { label: 'İşleniyor',   cls: 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30', dot: 'bg-indigo-400',   pulse: true  },
  SUCCESS:    { label: 'Tamamlandı',  cls: 'bg-emerald-500/20 text-emerald-400',               dot: 'bg-emerald-400', pulse: false },
  FAILED:     { label: 'Başarısız',   cls: 'bg-red-500/20 text-red-400',                      dot: 'bg-red-500',     pulse: false },
  REVOKED:    { label: 'İptal',       cls: 'bg-gray-600/30 text-gray-400',                    dot: 'bg-gray-500',    pulse: false },
  OPEN:       { label: 'KİLİTLİ',    cls: 'bg-red-500/20 text-red-400 border border-red-500/40', dot: 'bg-red-500',  pulse: true  },
  CLOSED:     { label: 'Normal',      cls: 'bg-emerald-500/20 text-emerald-400',               dot: 'bg-emerald-400', pulse: false },
  HALF_OPEN:  { label: 'Yenileniyor', cls: 'bg-amber-500/20 text-amber-400',                  dot: 'bg-amber-400',   pulse: true  },
  UNKNOWN:    { label: '?',           cls: 'bg-gray-500/20 text-gray-400',                    dot: 'bg-gray-500',    pulse: false },
}

const sizeMap = {
  xs: 'px-1.5 py-0.5 text-xs gap-1',
  sm: 'px-2 py-0.5 text-xs gap-1.5',
  md: 'px-2.5 py-1 text-sm gap-2',
}

const info      = CONFIG[props.status?.toUpperCase()] ?? CONFIG.UNKNOWN
const sizeCls   = sizeMap[props.size] ?? sizeMap.sm
</script>

<template>
  <span :class="['inline-flex items-center rounded-full font-medium', sizeCls, info.cls]">
    <span :class="['rounded-full w-1.5 h-1.5 shrink-0', info.dot, info.pulse ? 'animate-pulse' : '']" />
    {{ info.label }}
  </span>
</template>

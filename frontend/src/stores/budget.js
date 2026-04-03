/**
 * src/stores/budget.js — Bütçe ve Circuit Breaker Pinia store'u.
 * 30 saniyelik polling ile anlık bütçe durumunu günceller.
 */

import { defineStore }  from 'pinia'
import { ref, computed } from 'vue'
import { budgetService } from '@/services'

export const useBudgetStore = defineStore('budget', () => {
  // ── Durum ─────────────────────────────────────────────
  const status      = ref(null)    // /budget/status yanıtı
  const stats       = ref(null)    // /budget/stats yanıtı
  const history     = ref([])      // Son 7 günlük geçmiş
  const breakdown   = ref(null)    // Model/task dağılımı
  const logs        = ref([])      // Son maliyet logları
  const isLoading   = ref(false)
  const error       = ref(null)
  let   _pollTimer  = null

  // ── Hesaplananlar ─────────────────────────────────────
  const isBlocked      = computed(() => status.value?.breaker_state === 'OPEN')
  const usagePct       = computed(() => status.value?.usage_pct ?? 0)
  const spentUsd       = computed(() => status.value?.spent_usd ?? 0)
  const limitUsd       = computed(() => status.value?.limit_usd ?? 2)
  const remainingUsd   = computed(() => status.value?.remaining_usd ?? 2)
  const breakerState   = computed(() => status.value?.breaker_state ?? 'UNKNOWN')

  // Renk eşlemi (BudgetGauge ve başlık için)
  const gaugeColor = computed(() => {
    const p = usagePct.value
    if (p >= 95) return 'red'
    if (p >= 80) return 'orange'
    if (p >= 60) return 'amber'
    return 'emerald'
  })

  // ── Eylemler ──────────────────────────────────────────
  async function fetchStatus() {
    try {
      status.value = await budgetService.getStatus()
      error.value  = null
    } catch (err) {
      error.value = err.response?.data?.message || 'Bütçe durumu alınamadı.'
    }
  }

  async function fetchAll(days = 7) {
    isLoading.value = true
    try {
      const [s, st, h, b, l] = await Promise.allSettled([
        budgetService.getStatus(),
        budgetService.getStats(),
        budgetService.getHistory(days),
        budgetService.getBreakdown(days),
        budgetService.getLogs(20),
      ])
      if (s.status  === 'fulfilled') status.value    = s.value
      if (st.status === 'fulfilled') stats.value     = st.value
      if (h.status  === 'fulfilled') history.value   = h.value
      if (b.status  === 'fulfilled') breakdown.value = b.value
      if (l.status  === 'fulfilled') logs.value      = l.value
    } finally {
      isLoading.value = false
    }
  }

  async function resetBreaker() {
    try {
      await budgetService.reset()
      await fetchStatus()
      return true
    } catch (err) {
      error.value = err.response?.data?.message || 'Sıfırlama başarısız.'
      return false
    }
  }

  function startPolling(intervalMs = 30_000) {
    if (_pollTimer) return
    _pollTimer = setInterval(fetchStatus, intervalMs)
  }

  function stopPolling() {
    if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null }
  }

  return {
    status, stats, history, breakdown, logs, isLoading, error,
    isBlocked, usagePct, spentUsd, limitUsd, remainingUsd,
    breakerState, gaugeColor,
    fetchStatus, fetchAll, resetBreaker, startPolling, stopPolling,
  }
})

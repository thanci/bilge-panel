/**
 * src/stores/tasks.js — Görev kuyruğu Pinia store'u.
 * 5 saniyelik polling ile Celery görev listesini günceller.
 */

import { defineStore }   from 'pinia'
import { ref, computed } from 'vue'
import { taskService }   from '@/services'

export const useTaskStore = defineStore('tasks', () => {
  // ── Durum ─────────────────────────────────────────────
  const tasks     = ref([])
  const isLoading = ref(false)
  const isQueuing = ref(false)   // Form submit sırasında
  const error     = ref(null)
  const success   = ref(null)    // Başarı mesajı (ototemizlenir)
  const filter    = ref('all')   // 'all' | 'youtube_summary' | 'ai_article'
  let   _pollTimer = null

  // ── Hesaplananlar ─────────────────────────────────────
  const filteredTasks = computed(() => {
    if (filter.value === 'all') return tasks.value
    return tasks.value.filter(t => t.task_type === filter.value)
  })

  const runningCount = computed(() =>
    tasks.value.filter(t => t.status === 'RUNNING').length)

  const queuedCount = computed(() =>
    tasks.value.filter(t => t.status === 'QUEUED').length)

  // ── Eylemler ──────────────────────────────────────────
  async function fetchTasks() {
    try {
      tasks.value = await taskService.listTasks(30, null)
      error.value = null
    } catch (err) {
      error.value = err.response?.data?.message || 'Görev listesi alınamadı.'
    }
  }

  async function queueYoutube(payload) {
    isQueuing.value = true
    error.value     = null
    success.value   = null
    try {
      const result = await taskService.queueYoutube(payload)
      success.value = `YouTube görevi kuyruğa alındı (ID: ${result.task_id.slice(0,8)}...)`
      await fetchTasks()
      _autoHideSuccess()
      return result
    } catch (err) {
      error.value = err.response?.data?.message || 'Görev kuyruğa alınamadı.'
      return null
    } finally {
      isQueuing.value = false
    }
  }

  async function queueArticle(payload) {
    isQueuing.value = true
    error.value     = null
    success.value   = null
    try {
      const result = await taskService.queueArticle(payload)
      success.value = `Makale görevi kuyruğa alındı (ID: ${result.task_id.slice(0,8)}...)`
      await fetchTasks()
      _autoHideSuccess()
      return result
    } catch (err) {
      error.value = err.response?.data?.message || 'Makale görevi kuyruğa alınamadı.'
      return null
    } finally {
      isQueuing.value = false
    }
  }

  async function revokeTask(taskId) {
    try {
      await taskService.revokeTask(taskId)
      // İlgili görevi yerinde güncelle
      const idx = tasks.value.findIndex(t => t.task_id === taskId)
      if (idx !== -1) tasks.value[idx].status = 'REVOKED'
      return true
    } catch (err) {
      error.value = err.response?.data?.message || 'Görev iptal edilemedi.'
      return false
    }
  }

  function startPolling(intervalMs = 5_000) {
    if (_pollTimer) return
    _pollTimer = setInterval(fetchTasks, intervalMs)
  }

  function stopPolling() {
    if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null }
  }

  function setFilter(val) { filter.value = val }

  function _autoHideSuccess() {
    setTimeout(() => { success.value = null }, 5000)
  }

  return {
    tasks, filteredTasks, isLoading, isQueuing, error, success,
    filter, runningCount, queuedCount,
    fetchTasks, queueYoutube, queueArticle, revokeTask,
    startPolling, stopPolling, setFilter,
  }
})

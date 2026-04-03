/**
 * src/stores/publish.js — Yayın kuyruğu Pinia store'u.
 * Taslak oluşturma, düzenleme, yayınlama ve silme işlemleri.
 */

import { defineStore }   from 'pinia'
import { ref, computed } from 'vue'
import { publishService } from '@/services'

export const usePublishStore = defineStore('publish', () => {
  // ── Durum ─────────────────────────────────────────────
  const drafts       = ref([])
  const activeDraft  = ref(null)
  const isLoading    = ref(false)
  const isSaving     = ref(false)
  const isPublishing = ref(false)
  const error        = ref(null)
  const success      = ref(null)
  const filter       = ref('all')  // 'all' | 'DRAFT' | 'PUBLISHED'

  // ── Hesaplananlar ─────────────────────────────────────
  const filteredDrafts = computed(() => {
    if (filter.value === 'all') return drafts.value
    return drafts.value.filter(d => d.status === filter.value)
  })

  const draftCount = computed(() =>
    drafts.value.filter(d => d.status === 'DRAFT').length)

  const publishedCount = computed(() =>
    drafts.value.filter(d => d.status === 'PUBLISHED').length)

  // ── Eylemler ──────────────────────────────────────────
  async function fetchDrafts() {
    isLoading.value = true
    try {
      drafts.value = await publishService.listDrafts()
      error.value = null
    } catch (err) {
      error.value = err.response?.data?.message || 'Taslak listesi alınamadı.'
    } finally {
      isLoading.value = false
    }
  }

  async function selectDraft(id) {
    isLoading.value = true
    try {
      activeDraft.value = await publishService.getDraft(id)
      error.value = null
    } catch (err) {
      error.value = err.response?.data?.message || 'Taslak detayı alınamadı.'
    } finally {
      isLoading.value = false
    }
  }

  async function saveDraft(id, payload) {
    isSaving.value = true
    try {
      const updated = await publishService.updateDraft(id, payload)
      activeDraft.value = updated
      // Listeyi güncelle
      const idx = drafts.value.findIndex(d => d.id === id)
      if (idx !== -1) drafts.value[idx] = updated
      success.value = 'Taslak kaydedildi.'
      _autoHideSuccess()
      return updated
    } catch (err) {
      error.value = err.response?.data?.message || 'Taslak kaydedilemedi.'
      return null
    } finally {
      isSaving.value = false
    }
  }

  async function publishDraft(id) {
    isPublishing.value = true
    try {
      const result = await publishService.publishDraft(id)
      activeDraft.value = result
      const idx = drafts.value.findIndex(d => d.id === id)
      if (idx !== -1) drafts.value[idx] = result
      success.value = 'İçerik XenForo\'ya yayınlandı! 🎉'
      _autoHideSuccess()
      return result
    } catch (err) {
      error.value = err.response?.data?.message || 'Yayınlama başarısız.'
      return null
    } finally {
      isPublishing.value = false
    }
  }

  async function deleteDraft(id) {
    try {
      await publishService.deleteDraft(id)
      drafts.value = drafts.value.filter(d => d.id !== id)
      if (activeDraft.value?.id === id) activeDraft.value = null
      success.value = 'Taslak silindi.'
      _autoHideSuccess()
      return true
    } catch (err) {
      error.value = err.response?.data?.message || 'Taslak silinemedi.'
      return false
    }
  }

  function setFilter(val) { filter.value = val }

  function _autoHideSuccess() {
    setTimeout(() => { success.value = null }, 4000)
  }

  return {
    drafts, filteredDrafts, activeDraft,
    isLoading, isSaving, isPublishing,
    error, success, filter,
    draftCount, publishedCount,
    fetchDrafts, selectDraft, saveDraft,
    publishDraft, deleteDraft, setFilter,
  }
})

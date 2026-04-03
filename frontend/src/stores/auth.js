/**
 * src/stores/auth.js — Kimlik doğrulama Pinia store'u.
 * 
 * HATA GEÇMİŞİ (düzeltildi):
 *   Önceki versiyonda auth.js, authService'in zaten açılmış
 *   payload'ını tekrar sarmaya çalışıyordu:
 *     const payload = response.data || response  ← YANLIŞ
 *   authService.login() doğrudan { access_token, refresh_token, user }
 *   nesnesini döndürür — ekstra açma gereksiz.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authService }   from '@/services'
import { tokenStorage }  from '@/services/api'
import router            from '@/router'

export const useAuthStore = defineStore('auth', () => {
  // ── Durum ─────────────────────────────────────────────
  const user      = ref(null)
  const isLoading = ref(false)
  const error     = ref(null)

  // ── Hesaplananlar ─────────────────────────────────────
  const isLoggedIn = computed(
    () => !!user.value && !!tokenStorage.getAccess()
  )

  // ── Eylemler ──────────────────────────────────────────

  async function login(username, password) {
    isLoading.value = true
    error.value     = null

    try {
      // authService.login() → { access_token, refresh_token, user }
      // (services/index.js içinde data.data açılıyor — burada tekrar açma)
      const payload = await authService.login(username, password)

      // Güvenli kontrol: token'lar gerçekten string mi?
      const accessToken  = payload?.access_token
      const refreshToken = payload?.refresh_token
      const userData     = payload?.user

      if (!accessToken || typeof accessToken !== 'string') {
        throw new Error(
          `Geçersiz access_token alındı: ${JSON.stringify(accessToken)}`
        )
      }

      // localStorage'a yaz
      tokenStorage.setTokens(accessToken, refreshToken ?? '')
      user.value = userData ?? null

      // Router push'u BEKLE — token yazıldıktan sonra yönlendir
      // (race condition'ı önler: token yokken dashboard API'leri çağrılmasın)
      await router.push({ name: 'dashboard' })
      return true

    } catch (err) {
      // Token temizle — yarım bırakılmış state kalmasın
      tokenStorage.clearAll()
      user.value = null

      // Hata mesajını kullanıcıya göster
      const serverMsg = err.response?.data?.message
      error.value = serverMsg || err.message || 'Giriş başarısız.'
      return false

    } finally {
      isLoading.value = false
    }
  }

  async function logout() {
    try {
      await authService.logout(
        tokenStorage.getAccess(),
        tokenStorage.getRefresh(),
      )
    } catch {
      // Logout hata verse de temizle
    } finally {
      user.value = null
      tokenStorage.clearAll()
      await router.push({ name: 'login' })
    }
  }

  async function fetchCurrentUser() {
    const token = tokenStorage.getAccess()

    // Token yoksa veya "undefined" yazılmışsa temizle
    if (!token || token === 'undefined' || token === 'null') {
      tokenStorage.clearAll()
      return false
    }

    try {
      const userData = await authService.me()
      user.value     = userData
      return true
    } catch {
      tokenStorage.clearAll()
      user.value = null
      return false
    }
  }

  return {
    user,
    isLoading,
    error,
    isLoggedIn,
    login,
    logout,
    fetchCurrentUser,
  }
})

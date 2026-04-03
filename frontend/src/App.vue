<script setup>
/**
 * App.vue — Kök bileşen.
 *
 * Sayfa yenilendiğinde oturum durumunu GÜVENLİ biçimde doğrular.
 *
 * SORUN: Önceki versiyonda onMounted() her zaman /api/auth/me çağırıyordu.
 * Login sayfasında bu çağrı başarısız olup fetchCurrentUser() içindeki
 * hata bloğu tokenStorage.clearAll() tetikliyordu. Bu da:
 *   1. Giriş yapılıyordu.
 *   2. auth store token'ı yazıyordu.
 *   3. router.push('dashboard') çalışıyordu.
 *   4. Dashboard mount olurken App.vue onMounted yeniden tetikleniyordu.
 *   5. /api/auth/me çağrısı (token henüz güçlü değil ya da me endpoint'i başarısız)
 *   6. clearAll() → guard → login'e geri atış.
 *
 * ÇÖZÜM:
 *   - Sadece protected route'larda ve token varsa /me çağır.
 *   - Login/public sayfalarında /me çağırma.
 *   - /me başarısız olursa sadece o anda protected route'daysa yönlendir.
 */

import { onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore }        from '@/stores/auth'
import { tokenStorage }        from '@/services/api'

const authStore = useAuthStore()
const router    = useRouter()
const route     = useRoute()

onMounted(async () => {
  // Public sayfalarda (login, kayıt vb.) hiçbir şey yapma
  if (route.meta.public) return

  // Token yoksa guard zaten login'e yollayacak — burada tekrarlama
  const token = tokenStorage.getAccess()
  if (!token) return

  // Token var, kullanıcı bilgisini tazele (sayfa yenileme sonrası)
  const ok = await authStore.fetchCurrentUser()

  // /me başarısız oldu VE protected route'daysa gönder
  if (!ok && route.meta.requiresAuth) {
    router.push({ name: 'login' })
  }
})
</script>

<template>
  <RouterView />
</template>

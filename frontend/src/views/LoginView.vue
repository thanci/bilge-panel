<script setup>
import { ref, reactive } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useRouter }    from 'vue-router'

const authStore = useAuthStore()
const router    = useRouter()

const form = reactive({ username: '', password: '' })
const showPw = ref(false)

async function handleLogin() {
  // Auth store login() kendi içinde router.push('/dashboard') yapıyor
  // (token localStorage'a yazıldıktan SONRA — race condition önlenir)
  await authStore.login(form.username, form.password)
}

</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-[#030712] px-4">

    <!-- Arka plan efekti -->
    <div class="fixed inset-0 overflow-hidden pointer-events-none">
      <div class="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px]
                  bg-indigo-600/5 rounded-full blur-3xl" />
      <div class="absolute bottom-0 right-0 w-[600px] h-[400px]
                  bg-purple-600/5 rounded-full blur-3xl" />
    </div>

    <div class="w-full max-w-sm relative z-10 animate-slide-up">

      <!-- Logo -->
      <div class="text-center mb-10">
        <div class="inline-flex items-center justify-center w-14 h-14 bg-indigo-600
                    rounded-2xl shadow-glow text-2xl text-white mb-4">
          ✦
        </div>
        <h1 class="text-2xl font-bold text-white">Bilge Yolcu</h1>
        <p class="text-gray-500 text-sm mt-1">Kontrol Paneli</p>
      </div>

      <!-- Form kartı -->
      <div class="card p-8 space-y-5 shine">
        <h2 class="text-base font-semibold text-gray-100 text-center">Yönetici Girişi</h2>

        <!-- Hata -->
        <Transition name="fade">
          <div v-if="authStore.error"
               class="bg-red-500/10 border border-red-500/30 text-red-400
                      text-sm px-4 py-2.5 rounded-lg text-center">
            {{ authStore.error }}
          </div>
        </Transition>

        <form @submit.prevent="handleLogin" class="space-y-4">
          <div>
            <label class="field-label">Kullanıcı Adı</label>
            <input v-model="form.username" type="text"
                   class="input-field" placeholder="admin"
                   autocomplete="username" required />
          </div>

          <div>
            <label class="field-label">Şifre</label>
            <div class="relative">
              <input v-model="form.password"
                     :type="showPw ? 'text' : 'password'"
                     class="input-field pr-10"
                     placeholder="••••••••"
                     autocomplete="current-password" required />
              <button type="button"
                      @click="showPw = !showPw"
                      class="absolute right-3 top-1/2 -translate-y-1/2
                             text-gray-500 hover:text-gray-300 transition-colors text-xs">
                {{ showPw ? '🙈' : '👁' }}
              </button>
            </div>
          </div>

          <button type="submit"
                  class="btn-primary w-full justify-center py-3 mt-2"
                  :disabled="authStore.isLoading">
            <span v-if="authStore.isLoading" class="animate-spin-slow">⚙</span>
            {{ authStore.isLoading ? 'Giriş yapılıyor...' : 'Giriş Yap' }}
          </button>
        </form>
      </div>

      <p class="text-center text-xs text-gray-600 mt-6">
        Bu sayfa yalnızca yetkili yöneticilere açıktır.
      </p>
    </div>
  </div>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>

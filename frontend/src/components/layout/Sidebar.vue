<script setup>
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore }        from '@/stores/auth'

defineProps({ collapsed: { type: Boolean, default: false } })
defineEmits(['toggle'])

const router    = useRouter()
const route     = useRoute()
const authStore = useAuthStore()

const NAV = [
  { name: 'dashboard', icon: '◈',  label: 'Dashboard' },
  { name: 'tasks',     icon: '⚡', label: 'Görev Kuyruğu' },
  { name: 'budget',    icon: '◎',  label: 'Bütçe' },
  { name: 'xenforo',  icon: '🏛',  label: 'XenForo' },
  { name: 'devops',   icon: '🖥',  label: 'Sistem & Tema' },
]

async function logout() {
  await authStore.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <aside :class="[
    'flex flex-col bg-gray-900 border-r border-gray-700/40 transition-all duration-300 shrink-0',
    collapsed ? 'w-16' : 'w-64',
  ]">

    <!-- Logo -->
    <div :class="['flex items-center border-b border-gray-700/40 shrink-0',
                   collapsed ? 'justify-center px-4 py-5' : 'gap-3 px-5 py-5']">
      <!-- Platform ikonu (SVG placeholder — özel ikonlar ile değiştirilebilir) -->
      <div class="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center
                  text-white text-sm font-bold shrink-0 shadow-glow-sm">
        ✦
      </div>
      <div v-if="!collapsed" class="overflow-hidden">
        <div class="text-sm font-semibold text-gray-100 leading-tight">Bilge Yolcu</div>
        <div class="text-[10px] text-indigo-400 tracking-widest uppercase">Kontrol Paneli</div>
      </div>
    </div>

    <!-- Navigasyon -->
    <nav class="flex-1 px-2 py-4 space-y-1 overflow-y-auto">
      <RouterLink
        v-for="item in NAV"
        :key="item.name"
        :to="{ name: item.name }"
        :class="[
          'nav-link',
          { 'active': route.name === item.name },
          { 'justify-center': collapsed },
        ]"
        :title="collapsed ? item.label : ''">
        <span :class="['text-base shrink-0', collapsed ? 'text-lg' : '']">{{ item.icon }}</span>
        <span v-if="!collapsed" class="truncate">{{ item.label }}</span>
      </RouterLink>
    </nav>

    <!-- Alt: Kullanıcı profili + çıkış -->
    <div class="border-t border-gray-700/40 p-2">
      <div :class="['flex items-center rounded-lg px-2 py-2 gap-3',
                     collapsed ? 'justify-center' : '']">
        <!-- Avatar -->
        <div class="w-7 h-7 bg-indigo-600/30 border border-indigo-500/40 rounded-full
                    flex items-center justify-center text-indigo-400 text-xs font-bold shrink-0">
          {{ (authStore.user?.username?.[0] ?? 'A').toUpperCase() }}
        </div>
        <div v-if="!collapsed" class="flex-1 min-w-0">
          <div class="text-xs font-medium text-gray-200 truncate">
            {{ authStore.user?.username ?? 'Admin' }}
          </div>
          <div class="text-[10px] text-gray-500">Süper Admin</div>
        </div>
        <button v-if="!collapsed"
                @click="logout"
                class="text-gray-500 hover:text-red-400 transition-colors p-1 rounded"
                title="Çıkış Yap">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round"
                  d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>
          </svg>
        </button>
      </div>
    </div>
  </aside>
</template>

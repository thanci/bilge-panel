<script setup>
/**
 * AppLayout.vue — Ana yerleşim şablonu.
 * Sidebar + Header + main content yapısını oluşturur.
 */

import { ref } from 'vue'
import Sidebar from './Sidebar.vue'
import Header  from './Header.vue'

const sidebarOpen = ref(true)
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-[#030712]">

    <!-- Sidebar -->
    <Sidebar :collapsed="!sidebarOpen" @toggle="sidebarOpen = !sidebarOpen" />

    <!-- Ana içerik alanı -->
    <div class="flex-1 flex flex-col overflow-hidden transition-all duration-300">

      <!-- Header -->
      <Header @toggle-sidebar="sidebarOpen = !sidebarOpen" />

      <!-- Sayfa içeriği -->
      <main class="flex-1 overflow-y-auto p-6">
        <RouterView v-slot="{ Component }">
          <Transition name="page" mode="out-in">
            <component :is="Component" />
          </Transition>
        </RouterView>
      </main>
    </div>
  </div>
</template>

<style scoped>
.page-enter-active, .page-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.page-enter-from { opacity: 0; transform: translateY(8px); }
.page-leave-to   { opacity: 0; transform: translateY(-4px); }
</style>

<script setup>
import TaskForms from '@/components/tasks/TaskForms.vue'
import TaskQueue from '@/components/tasks/TaskQueue.vue'
</script>

<template>
  <div class="max-w-screen-xl mx-auto space-y-6">
    <div class="grid grid-cols-1 xl:grid-cols-2 gap-6">
      <TaskForms />
      <TaskQueue />
    </div>
  </div>
</template>

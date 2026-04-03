import { createRouter, createWebHistory } from 'vue-router'
import { tokenStorage } from '@/services/api'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    component: () => import('@/components/layout/AppLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'dashboard',
        component: () => import('@/views/DashboardView.vue'),
        meta: { title: 'Dashboard' },
      },
      {
        path: 'tasks',
        name: 'tasks',
        component: () => import('@/views/TasksView.vue'),
        meta: { title: 'Görev Kuyruğu' },
      },
      {
        path: 'publish',
        name: 'publish',
        component: () => import('@/views/PublishView.vue'),
        meta: { title: 'Yayın Kuyruğu' },
      },
      {
        path: 'budget',
        name: 'budget',
        component: () => import('@/views/BudgetView.vue'),
        meta: { title: 'Bütçe Yönetimi' },
      },
      {
        path: 'xenforo',
        name: 'xenforo',
        component: () => import('@/views/XenForoView.vue'),
        meta: { title: 'XenForo Yönetimi' },
      },
      {
        path: 'devops',
        name: 'devops',
        component: () => import('@/views/DevOpsView.vue'),
        meta: { title: 'Sistem & Tema' },
      },
      {
        path: 'guide',
        name: 'guide',
        component: () => import('@/views/GuideView.vue'),
        meta: { title: 'Kullanım Rehberi' },
      },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

// ── Navigation guard: oturum kontrolü ────────────────────
router.beforeEach((to) => {
  const hasToken = !!tokenStorage.getAccess()

  if (to.meta.requiresAuth && !hasToken) {
    return { name: 'login' }
  }
  if (to.name === 'login' && hasToken) {
    return { name: 'dashboard' }
  }
})

// ── Sayfa başlığını güncelle ──────────────────────────────
router.afterEach((to) => {
  const title = to.meta?.title
  document.title = title ? `${title} — Bilge Yolcu` : 'Bilge Yolcu — Kontrol Paneli'
})

export default router

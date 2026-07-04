import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/dashboard'
    },
    {
      path: '/dashboard',
      name: 'Dashboard',
      component: () => import('../views/dashboardView.vue')
    },
    {
      path: '/sessions',
      name: 'Sessions',
      component: () => import('../views/sessionsView.vue')
    }
  ],
})

export default router

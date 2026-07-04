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
    },
    {
      path: '/people',
      name: 'People',
      component: () => import('../views/peopleView.vue')
    },
    {
      path: "/locations",
      name: "Locations",
      component: () => import("../views/locationsView.vue")
    },
    {
      path: "/factions",
      name: "Factions",
      component: () => import("../views/factionsView.vue")
    },
    {
      path: "/rolls",
      name: "Rolls",
      component: () => import("../views/rollsView.vue")
    }
  ],
})

export default router

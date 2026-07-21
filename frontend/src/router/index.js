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
      path: '/sessions/:id?',
      name: 'Sessions',
      component: () => import('../views/sessionsView.vue')
    },
    {
      path: '/people/:id?',
      name: 'People',
      component: () => import('../views/peopleView.vue')
    },
    {
      path: '/character/:personId(\\d+)?',
      component: () => import('../views/characterView.vue'),
      children: [
        {
          path: '',
          redirect: (route) => ({
            name: 'CharacterOverview',
            params: { personId: route.params.personId },
          }),
          meta: { showInSubmenu: false },
        },
        {
          path: 'overview',
          name: 'CharacterOverview',
          component: () => import('../views/characterOverviewView.vue'),
          meta: { label: 'Overview' },
        },
        {
          path: 'notes/:noteId?',
          name: 'CharacterNotes',
          component: () => import('../views/characterNotesView.vue'),
          props: { kind: 'notes' },
          meta: { label: 'Notes' },
        },
        {
          path: 'backstory/:noteId?',
          name: 'CharacterBackstory',
          component: () => import('../views/characterNotesView.vue'),
          props: { kind: 'backstory' },
          meta: { label: 'Backstory' },
        },
      ],
    },
    {
      path: "/locations/:id?",
      name: "Locations",
      component: () => import("../views/locationsView.vue")
    },
    {
      path: "/factions/:id?",
      name: "Factions",
      component: () => import("../views/factionsView.vue")
    },
    {
      path: "/rolls/:id?",
      name: "Rolls",
      component: () => import("../views/rollsView.vue")
    },
    {
      path: "/search",
      name: "Search",
      component: () => import("../views/searchView.vue"),
    }
  ],
})

export default router

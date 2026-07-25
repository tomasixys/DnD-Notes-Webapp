import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from "@/stores/authStore"

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/dashboard'
    },
    {
      path: '/login',
      name: 'Login',
      component: () => import('../views/loginView.vue'),
      meta: { public: true, authPage: true },
    },
    {
      path: '/activate',
      name: 'ActivateAccount',
      component: () => import('../views/accountTokenView.vue'),
      props: { purpose: 'activate' },
      meta: { public: true, authPage: true },
    },
    {
      path: '/reset-password',
      name: 'ResetPassword',
      component: () => import('../views/accountTokenView.vue'),
      props: { purpose: 'reset-password' },
      meta: { public: true, authPage: true },
    },
    {
      path: '/auth/loading',
      name: 'AuthLoading',
      component: () => import('../views/authLoadingView.vue'),
      meta: { public: true, authPage: true },
    },
    {
      path: '/session-expired',
      name: 'SessionExpired',
      component: () => import('../views/sessionExpiredView.vue'),
      meta: { public: true, authPage: true },
    },
    {
      path: '/access-denied',
      name: 'AccessDenied',
      component: () => import('../views/accessDeniedView.vue'),
      meta: { requiresAuth: true, authPage: true },
    },
    {
      path: '/profile',
      name: 'AccountProfile',
      component: () => import('../views/accountProfileView.vue'),
      meta: { requiresAuth: true, authPage: true },
    },
    {
      path: '/dashboard',
      name: 'Dashboard',
      component: () => import('../views/dashboardView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/sessions/:id(\\d+)?',
      component: () => import('../views/sessionsView.vue'),
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          redirect: (route) => {
            const pathSessionId = /^\/sessions\/(\d+)\/?$/.exec(route.path)?.[1]
            return {
              name: 'SessionNotes',
              params: pathSessionId ? { id: pathSessionId } : {},
            }
          },
          meta: { showInSubmenu: false },
        },
        {
          path: 'notes',
          name: 'SessionNotes',
          component: () => import('../views/sessionNotesView.vue'),
          meta: { label: 'Notes' },
        },
        {
          path: 'rolls',
          name: 'SessionRolls',
          component: () => import('../views/rollsView.vue'),
          meta: { label: 'Rolls' },
        },
      ],
    },
    {
      path: '/people/:id?',
      name: 'People',
      component: () => import('../views/peopleView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/character/:personId(\\d+)?',
      component: () => import('../views/characterView.vue'),
      meta: { requiresAuth: true },
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
      component: () => import("../views/locationsView.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/factions/:id?",
      name: "Factions",
      component: () => import("../views/factionsView.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/inventory/:id(\\d+)?",
      name: "Inventory",
      component: () => import("../views/inventoryView.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/rolls/:id(\\d+)?",
      redirect: (route) => ({
        name: "SessionRolls",
        params: { id: route.params.id },
      }),
    },
    {
      path: "/search",
      name: "Search",
      component: () => import("../views/searchView.vue"),
      meta: { requiresAuth: true },
    }
  ],
})

function safeRedirectTarget(value) {
  return (
    typeof value === "string"
    && value.startsWith("/")
    && !value.startsWith("//")
  )
    ? value
    : "/dashboard"
}

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (auth.state.value === "loading") {
    await auth.bootstrap()
  }

  if (to.meta.requiresAuth && !auth.isAuthenticated.value) {
    return {
      name: "Login",
      query: { redirect: to.fullPath },
    }
  }

  if (
    to.name === "Login"
    && auth.isAuthenticated.value
  ) {
    return safeRedirectTarget(to.query.redirect)
  }
})

export default router

import "./assets/main.css"

import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { useAuthStore } from "@/stores/authStore"

const app = createApp(App)
const auth = useAuthStore()

auth.setNavigationHandler((destination) => {
  const routeNames = {
    login: "Login",
    expired: "SessionExpired",
    "access-denied": "AccessDenied",
  }
  const redirect = router.currentRoute.value.fullPath
  void router.push({
    name: routeNames[destination],
    ...(destination === "expired"
      ? { query: { redirect } }
      : {}),
  })
})

await auth.bootstrap()

app.use(router)

await router.isReady()
app.mount('#app')

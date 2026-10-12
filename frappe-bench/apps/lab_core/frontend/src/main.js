import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import { createPinia } from 'pinia'
import { PiniaColada } from '@pinia/colada'
import { VueQueryPlugin } from '@tanstack/vue-query'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import 'vuetify/styles'
import App from './App.vue'

const router = createRouter({
  history: createWebHistory('/lab/'),
  routes: [
    { path: '/', redirect: '/colada' },
    { path: '/colada', component: () => import('./pages/colada/Hello.vue') },
    { path: '/tanstack', component: () => import('./pages/tanstack/Hello.vue') },
    { path: '/together', component: () => import('./pages/together/Hello.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/colada' },
  ],
})

createApp(App)
  .use(createPinia())
  .use(PiniaColada)
  .use(VueQueryPlugin)
  .use(createVuetify({ components, directives }))
  .use(router)
  .mount('#app')

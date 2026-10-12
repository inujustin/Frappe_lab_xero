<template>
  <v-app>
    <v-app-bar title="Lab Core" flat border />
    <v-main>
      <v-container class="py-8" style="max-width: 960px">
        <h1 class="text-h4 mb-2">Hello, Lab</h1>
        <p class="text-body-1 mb-6">One session. Three ways to load the same greeting.</p>
        <nav aria-label="Hello pages" class="d-flex flex-wrap ga-2 mb-6">
          <v-btn to="/colada" variant="tonal">Colada</v-btn>
          <v-btn to="/tanstack" variant="tonal">TanStack</v-btn>
          <v-btn to="/together" variant="tonal">Together</v-btn>
        </nav>
        <router-view />
      </v-container>
    </v-main>
  </v-app>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  data: { type: Object, default: undefined },
  error: { type: Error, default: null },
  loading: { type: Boolean, default: false },
})

defineEmits(['refresh'])
</script>

<template>
  <v-card :title="title" variant="outlined" :aria-busy="loading">
    <v-card-text>
      <p v-if="loading" role="status">Loading greeting…</p>
      <v-alert v-else-if="error" type="error" variant="tonal" role="alert">
        {{ error.message }}
        <div class="mt-2">
          <a href="/login?redirect-to=%2Flab">Log in</a>
        </div>
      </v-alert>
      <div v-else-if="data" aria-live="polite">
        <p class="text-h6 mb-2">{{ data.message }}</p>
        <p>Signed in as {{ data.user }}</p>
      </div>
    </v-card-text>
    <v-card-actions>
      <v-btn :disabled="loading" @click="$emit('refresh')">Refresh</v-btn>
    </v-card-actions>
  </v-card>
</template>

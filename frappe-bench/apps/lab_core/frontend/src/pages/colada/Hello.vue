<script setup>
import { useQuery } from '@pinia/colada'
import { getHello } from '../../api/hello.js'
import HelloResult from '../../components/HelloResult.vue'

const { data, error, isLoading, refetch } = useQuery({
  key: ['hello'],
  query: () => getHello(),
  staleTime: 0,
})

function refresh() {
  // Colada keeps the error in query state for the view to display.
  void refetch(false)
}
</script>

<template>
  <HelloResult
    title="Pinia Colada"
    :data="data"
    :error="error"
    :loading="isLoading"
    @refresh="refresh"
  />
</template>

<script setup>
import { useQuery } from '@tanstack/vue-query'
import { getHello } from '../../api/hello.js'
import HelloResult from '../../components/HelloResult.vue'

const { data, error, isFetching, refetch } = useQuery({
  queryKey: ['hello'],
  queryFn: ({ signal }) => getHello({ signal }),
  staleTime: 0,
  retry: false,
})

function refresh() {
  void refetch()
}
</script>

<template>
  <HelloResult
    title="TanStack Query"
    :data="data"
    :error="error"
    :loading="isFetching"
    @refresh="refresh"
  />
</template>

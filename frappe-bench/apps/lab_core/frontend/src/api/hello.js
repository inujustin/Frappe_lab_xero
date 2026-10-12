export async function getHello({ signal } = {}) {
  let response
  try {
    response = await fetch('/api/method/lab_core.api.hello.hello', {
      method: 'GET',
      credentials: 'same-origin',
      cache: 'no-store',
      signal,
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new Error('Cannot reach the server. Please try again.')
  }

  if (response.status === 401 || response.status === 403) {
    throw new Error('Please log in to view your greeting.')
  }
  if (!response.ok) {
    throw new Error(`The greeting could not be loaded (HTTP ${response.status}).`)
  }

  const payload = await response.json()
  const greeting = payload.message
  if (typeof greeting?.message !== 'string' || typeof greeting?.user !== 'string') {
    throw new Error('The server returned an unexpected greeting.')
  }
  return greeting
}

import axios from 'axios'

const BASE_URL = '/api/v1'

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
})

export async function uploadFiles(files) {
  const formData = new FormData()
  for (const file of files) {
    formData.append('files', file)
  }
  const response = await api.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
  })
  return response.data
}

export async function getStatus(sessionId) {
  const response = await api.get(`/status/${sessionId}`)
  return response.data
}

export async function getResults(sessionId) {
  const response = await api.get(`/results/${sessionId}`)
  return response.data
}

export function getExportUrl(sessionId, format) {
  return `${BASE_URL}/export/${sessionId}/${format}`
}

export async function deleteSession(sessionId) {
  const response = await api.delete(`/session/${sessionId}`)
  return response.data
}

export async function checkHealth() {
  const response = await api.get('/health', { baseURL: '' })
  return response.data
}

// Poll status until complete or error, calling onProgress each tick
export async function pollUntilDone(sessionId, onProgress, intervalMs = 1500) {
  return new Promise((resolve, reject) => {
    const interval = setInterval(async () => {
      try {
        const status = await getStatus(sessionId)
        if (onProgress) onProgress(status)

        if (status.status === 'complete' || status.status === 'error') {
          clearInterval(interval)
          if (status.status === 'complete') {
            const results = await getResults(sessionId)
            results.cached = status.cached || false
            resolve(results)
          } else {
            reject(new Error(status.errors?.[0] || 'Analysis failed'))
          }
        }
      } catch (err) {
        clearInterval(interval)
        reject(err)
      }
    }, intervalMs)
  })
}

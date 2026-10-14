const BASE_URL = import.meta.env.VITE_API_URL || '/api'

async function request(endpoint, options = {}) {
  const url = `${BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  }

  try {
    const response = await fetch(url, { ...options, headers })
    if (!response.ok) {
      let errorDetail
      try {
        errorDetail = await response.json()
      } catch {
        errorDetail = { message: await response.text() }
      }
      const err = new Error(
        typeof errorDetail.detail === 'object'
          ? errorDetail.detail.message || JSON.stringify(errorDetail.detail)
          : errorDetail.detail || response.statusText || 'Request failed'
      )
      err.status = response.status
      err.detail = errorDetail
      throw err
    }
    return await response.json()
  } catch (err) {
    // If proxied /api fails (e.g. direct access needed without proxy), try direct fallback
    if (url.startsWith('/api') && (err.name === 'TypeError' || err.message.includes('fetch'))) {
      const fallbackUrl = `http://127.0.0.1:8000${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`
      try {
        const fallbackRes = await fetch(fallbackUrl, { ...options, headers })
        if (fallbackRes.ok) return await fallbackRes.json()
      } catch {
        // Fallback also failed, bubble original
      }
    }
    throw err
  }
}

export const api = {
  getHealth: () => request('/health'),
  getDemoInfo: () => request('/demo/info'),
  resetDemoData: () => request('/demo/reset', { method: 'POST' }),

  getCalendar: (date) => request(`/calendar?date=${encodeURIComponent(date)}`),
  createEvent: (eventData) => request('/calendar', { method: 'POST', body: JSON.stringify(eventData) }),
  updateEvent: (id, updates) => request(`/calendar/${id}`, { method: 'PATCH', body: JSON.stringify(updates) }),
  deleteEvent: (id) => request(`/calendar/${id}`, { method: 'DELETE' }),

  getTasks: () => request('/tasks'),

  runAgent: (goal, date) =>
    request('/agent/run', {
      method: 'POST',
      body: JSON.stringify({ goal, ...(date ? { date } : {}) }),
    }),
  listRuns: () => request('/agent/runs'),
  getRun: (id) => request(`/agent/runs/${id}`),
  getRunEvents: (id) => request(`/agent/runs/${id}/events`),
  getRunVerification: (id) => request(`/agent/runs/${id}/verification`),
  cancelRun: (id) => request(`/agent/runs/${id}/cancel`, { method: 'POST' }),
}

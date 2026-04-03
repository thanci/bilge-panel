import api from './api'

// ─── Kimlik Doğrulama ──────────────────────────────────────
export const authService = {
  async login(username, password) {
    const { data } = await api.post('/auth/login', { username, password })

    // Backend formatı: { "success": true, "data": { "access_token": "...", ... } }
    // Her iki formata dayanıklı çıkarım (data.data varsa onu, yoksa data'yı kullan)
    const payload = data?.data ?? data

    if (!payload?.access_token) {
      throw new Error(
        `Login yanıtında access_token bulunamadı. Gelen: ${JSON.stringify(data)}`
      )
    }

    return payload  // { access_token, refresh_token, user }
  },

  async logout(accessToken, refreshToken) {
    const requests = [api.post('/auth/logout')]
    if (refreshToken) {
      requests.push(
        api.post('/auth/logout', null, {
          headers: { Authorization: `Bearer ${refreshToken}` },
        }),
      )
    }
    await Promise.allSettled(requests)
  },

  async me() {
    const { data } = await api.get('/auth/me')
    return data?.data?.user ?? data?.user ?? null
  },
}

// ─── Bütçe ────────────────────────────────────────────────
export const budgetService = {
  async getStatus()        { const { data } = await api.get('/budget/status');           return data.data },
  async getHistory(days)   { const { data } = await api.get(`/budget/history?days=${days}`); return data.data },
  async getBreakdown(days) { const { data } = await api.get(`/budget/breakdown?days=${days}`); return data.data },
  async getLogs(limit)     { const { data } = await api.get(`/budget/logs?limit=${limit}`); return data.data },
  async getStats()         { const { data } = await api.get('/budget/stats');            return data.data },
  async reset()            { const { data } = await api.post('/budget/reset');           return data.data },
}

// ─── Görevler ─────────────────────────────────────────────
export const taskService = {
  async queueYoutube(payload) {
    const { data } = await api.post('/tasks/youtube', payload)
    return data.data
  },
  async queueArticle(payload) {
    const { data } = await api.post('/tasks/article', payload)
    return data.data
  },
  async listTasks(limit = 20, type = null) {
    const params = new URLSearchParams({ limit })
    if (type) params.append('type', type)
    const { data } = await api.get(`/tasks?${params}`)
    return data.data
  },
  async getTask(taskId) {
    const { data } = await api.get(`/tasks/${taskId}`)
    return data.data
  },
  async deleteTask(taskId) {
    const { data } = await api.delete(`/tasks/${taskId}`)
    return data.data
  },
  async retryTask(taskId) {
    const { data } = await api.post(`/tasks/${taskId}/retry`)
    return data.data
  },
  async revokeTask(taskId) {
    const { data } = await api.delete(`/tasks/${taskId}`)
    return data.data
  },
}

// ─── Yayın Kuyruğu ───────────────────────────────────────
export const publishService = {
  async createDraft(payload) {
    const { data } = await api.post('/publish', payload)
    return data.data
  },
  async listDrafts(status = null) {
    const params = status ? `?status=${status}` : ''
    const { data } = await api.get(`/publish${params}`)
    return data.data
  },
  async getDraft(id) {
    const { data } = await api.get(`/publish/${id}`)
    return data.data
  },
  async updateDraft(id, payload) {
    const { data } = await api.put(`/publish/${id}`, payload)
    return data.data
  },
  async publishDraft(id) {
    const { data } = await api.post(`/publish/${id}/send`)
    return data.data
  },
  async deleteDraft(id) {
    const { data } = await api.delete(`/publish/${id}`)
    return data.data
  },
}

